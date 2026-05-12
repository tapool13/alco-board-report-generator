"""PDF parsing logic for ALCO reports."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

import pdfplumber

from config import POLICY_LIMIT_DEFAULTS


class PDFParser:
    """Parse ALCO PDF documents into structured section data."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    def parse(self, pdf_path: str) -> Dict:
        """Parse an ALCO PDF and return structured data for report generation."""
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"Input PDF not found: {pdf_path}")

        pages: List[Dict] = []
        with pdfplumber.open(str(path)) as pdf:
            for index, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                tables = page.extract_tables() or []
                pages.append({"page_number": index, "text": text, "tables": tables})

        metadata = self._extract_metadata(pages, path)
        parsed = {
            "metadata": metadata,
            "interest_rate_risk": self._extract_interest_rate_risk(pages),
            "liquidity": self._extract_liquidity(pages),
            "balance_sheet": self._extract_balance_sheet(pages),
            "net_interest_margin": self._extract_nim(pages),
            "investment_portfolio": self._extract_investment_portfolio(pages),
            "rate_sensitivity_gap": self._extract_rate_sensitivity_gap(pages),
            "policy_compliance": self._extract_policy_compliance(pages),
        }
        return parsed

    def _extract_metadata(self, pages: List[Dict], path: Path) -> Dict:
        first_text = "\n".join([pages[0]["text"] if pages else "", pages[1]["text"] if len(pages) > 1 else ""])

        institution = "Unknown Institution"
        upper_lines = [line.strip() for line in first_text.splitlines() if line.strip()]
        for line in upper_lines[:6]:
            if "ALCO" not in line.upper() and "TABLE OF CONTENTS" not in line.upper() and len(line) > 3:
                institution = line.title()
                break

        date_match = re.search(
            r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\b",
            first_text,
            re.IGNORECASE,
        )
        report_date = date_match.group(0) if date_match else "Unknown Date"

        return {
            "institution": institution,
            "report_date": report_date,
            "source_file": path.name,
            "total_pages": len(pages),
        }

    def _extract_interest_rate_risk(self, pages: List[Dict]) -> Dict:
        rows = self._collect_rows_by_keywords(
            pages,
            ["% Chg in Net Interest Income", "NET INTEREST MARGIN", "EVE", "Economic Value of Equity"],
            section_keywords=["INTEREST RATE RISK", "Policy Comparison", "Policy Compared to Actual"],
        )

        if not rows:
            self.logger.warning("Interest rate risk section not found")

        scenarios = []
        for row in rows:
            metric = row[0]
            policy = row[1] if len(row) > 1 else ""
            actual = row[2] if len(row) > 2 else ""
            status = self._status_from_row(row)
            scenarios.append(
                {
                    "metric": metric,
                    "policy_limit": policy or POLICY_LIMIT_DEFAULTS.get(metric.upper(), ""),
                    "actual": actual,
                    "status": status,
                }
            )

        return {"metrics": scenarios}

    def _extract_liquidity(self, pages: List[Dict]) -> Dict:
        rows = self._collect_rows_by_keywords(
            pages,
            ["Liquidity", "Brokered Deposits", "FHLBC Advances", "Loans to Total Funding", "Cash And Equivalents"],
            section_keywords=["LIQUIDITY", "Policy Comparison", "Exhibit 1"],
        )
        if not rows:
            self.logger.warning("Liquidity section not found")

        metrics = []
        for row in rows:
            metrics.append(
                {
                    "metric": row[0],
                    "value": row[2] if len(row) > 2 and row[2] else (row[1] if len(row) > 1 else ""),
                    "policy_limit": row[1] if len(row) > 1 and (">" in row[1] or "<" in row[1]) else "",
                    "status": self._status_from_row(row),
                }
            )
        return {"metrics": metrics}

    def _extract_balance_sheet(self, pages: List[Dict]) -> Dict:
        rows = self._collect_rows_by_keywords(
            pages,
            ["TOTAL Assets", "Total Deposits", "Total Loans", "Common Equity", "Capital"],
            section_keywords=["Balance Sheet", "Policy Comparison", "Historical Shock"],
        )
        if not rows:
            self.logger.warning("Balance sheet section not found")

        metrics = []
        key_values: Dict[str, str] = {"total_assets": "", "loans": "", "deposits": "", "capital": ""}
        for row in rows:
            name = row[0]
            value = row[2] if len(row) > 2 else ""
            metrics.append({"metric": name, "value": value})
            normalized = name.upper()
            if "TOTAL ASSETS" in normalized and not key_values["total_assets"]:
                key_values["total_assets"] = value
            elif "LOAN" in normalized and not key_values["loans"]:
                key_values["loans"] = value
            elif "DEPOSIT" in normalized and not key_values["deposits"]:
                key_values["deposits"] = value
            elif any(token in normalized for token in ["CAPITAL", "EQUITY"]) and not key_values["capital"]:
                key_values["capital"] = value

        return {**key_values, "metrics": metrics}

    def _extract_nim(self, pages: List[Dict]) -> Dict:
        full_text = "\n".join(page["text"] for page in pages)
        nim_match = re.search(r"net interest margin[^\d]*(\d+(?:\.\d+)?)%", full_text, re.IGNORECASE)
        nim_value = nim_match.group(1) + "%" if nim_match else ""

        rows = self._collect_rows_by_keywords(
            pages,
            ["NET INTEREST MARGIN", "Yield", "Cost"],
            section_keywords=["Policy Comparison", "Narrative", "Accounting Measurement"],
        )
        if not nim_value and not rows:
            self.logger.warning("NIM section not found")

        metrics = [{"metric": row[0], "value": row[2] if len(row) > 2 else ""} for row in rows]
        return {"nim": nim_value, "metrics": metrics}

    def _extract_investment_portfolio(self, pages: List[Dict]) -> Dict:
        rows = self._collect_rows_by_keywords(
            pages,
            ["Investments", "Portfolio", "Market Value", "Book Value", "Gain (Loss)"],
            section_keywords=["INVESTMENT PORTFOLIO", "Portfolio Distribution", "Portfolio History"],
        )
        if not rows:
            self.logger.warning("Investment portfolio section not found")

        metrics = []
        for row in rows:
            metrics.append({"metric": row[0], "value": row[2] if len(row) > 2 else ""})
        return {"metrics": metrics}

    def _extract_rate_sensitivity_gap(self, pages: List[Dict]) -> Dict:
        rows = self._collect_rows_by_keywords(
            pages,
            ["Gap", "% Chg in Net Interest Income", "Immediate Risk", "Structural Net Interest Income"],
            section_keywords=["INTEREST RATE RISK", "New and Renewed", "Risk Impact"],
        )
        if not rows:
            self.logger.warning("Rate sensitivity / gap section not found")

        metrics = [{"metric": row[0], "value": row[2] if len(row) > 2 else ""} for row in rows]
        return {"metrics": metrics}

    def _extract_policy_compliance(self, pages: List[Dict]) -> Dict:
        rows = self._collect_rows_by_keywords(
            pages,
            ["Policy", "Comply", "NET INTEREST MARGIN", "Liquidity", "Leverage Ratio", "Capital Ratio"],
            section_keywords=["Policy Compared to Actual", "Policy Comparison"],
        )
        if not rows:
            self.logger.warning("Policy compliance section not found")

        items = []
        for row in rows:
            metric = row[0]
            policy = row[1] if len(row) > 1 else POLICY_LIMIT_DEFAULTS.get(metric.upper(), "")
            actual = row[2] if len(row) > 2 else ""
            compliant = self._is_compliant(actual, policy)

            explicit_status = self._status_from_row(row)
            if explicit_status != "Yellow":
                status = explicit_status
                compliant = status == "Green"
            else:
                status = "Green" if compliant else ("Red" if compliant is False else "Yellow")

            items.append(
                {
                    "metric": metric,
                    "policy_limit": policy,
                    "actual": actual,
                    "compliant": compliant,
                    "status": status,
                }
            )

        summary = {
            "green": sum(1 for item in items if item["status"] == "Green"),
            "yellow": sum(1 for item in items if item["status"] == "Yellow"),
            "red": sum(1 for item in items if item["status"] == "Red"),
            "total": len(items),
        }
        return {"items": items, "summary": summary}

    def _collect_rows_by_keywords(
        self,
        pages: List[Dict],
        row_keywords: List[str],
        section_keywords: Optional[List[str]] = None,
    ) -> List[List[str]]:
        section_keywords = section_keywords or []
        collected: List[List[str]] = []
        seen = set()

        for page in pages:
            text_upper = page["text"].upper()
            if section_keywords and not any(keyword.upper() in text_upper for keyword in section_keywords):
                continue

            for table in page["tables"]:
                for raw_row in table:
                    row = [str(cell).strip() if cell is not None else "" for cell in raw_row]
                    joined = " ".join(row)
                    if not joined.strip():
                        continue
                    if any(keyword.lower() in joined.lower() for keyword in row_keywords):
                        dedupe_key = tuple(row)
                        if dedupe_key in seen:
                            continue
                        seen.add(dedupe_key)
                        collected.append(row)

        return collected

    def _status_from_row(self, row: List[str]) -> str:
        text = " ".join(row).upper()
        if re.search(r"\bYES\b", text):
            return "Green"
        if re.search(r"\bNO\b", text) or "*" in text:
            return "Red"
        return "Yellow"

    def _is_compliant(self, actual: str, policy: str) -> Optional[bool]:
        if not actual or not policy:
            return None

        actual_value = self._to_float(actual)
        operator_match = re.search(r"(>=|<=|>|<)", policy)
        policy_value = self._to_float(policy)
        if actual_value is None or policy_value is None:
            return None

        operator = operator_match.group(1) if operator_match else None
        if operator == ">=":
            return actual_value >= policy_value
        if operator == "<=":
            return actual_value <= policy_value
        if operator == ">":
            return actual_value > policy_value
        if operator == "<":
            return actual_value < policy_value
        return None

    def _to_float(self, value: str) -> Optional[float]:
        clean = value.replace(",", "").replace("%", "").strip()
        if clean.startswith("(") and clean.endswith(")"):
            clean = "-" + clean[1:-1]
        clean = re.sub(r"[^0-9+\-.]", "", clean)
        if not clean or clean in {"-", "+", "."}:
            return None
        try:
            return float(clean)
        except ValueError:
            return None
