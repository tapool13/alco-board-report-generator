"""PDF parsing utilities for ALCO board report generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
from typing import Any

import pdfplumber


@dataclass
class SectionData:
    """Structured section payload extracted from the source PDF."""

    title: str
    pages: list[int]
    key_points: list[str]
    metrics: list[dict[str, str]]
    tables: list[dict[str, Any]]


class PDFParser:
    """Parse ALCO PDF reports into structured section-level data."""

    UNKNOWN_REPORT_DATE = "Unknown Date"
    UNKNOWN_REPORT_PERIOD = "UnknownPeriod"
    TABULAR_TOKEN_RATIO_THRESHOLD = 0.45
    MAX_BANK_NAME_LENGTH = 60
    MIN_HIGHLIGHT_LENGTH = 35
    MIN_KEY_POINT_LENGTH = 40

    SECTION_KEYWORDS = {
        "interest_rate_risk": [
            "interest rate risk",
            "nim sensitivity",
            "economic value of equity",
            "eve",
            "shock",
        ],
        "liquidity": [
            "liquidity",
            "liquidity ratio",
            "cashflow",
            "brokered deposits",
            "available borrowing",
        ],
        "investment_portfolio": [
            "investment portfolio",
            "portfolio distribution",
            "unrealized",
            "book value",
            "market value",
            "duration",
        ],
        "loan_portfolio": [
            "loan portfolio",
            "total loans",
            "loan yield",
            "delinquency",
            "credit",
        ],
        "deposit_composition": [
            "deposit",
            "time deposits",
            "non maturity",
            "deposit mix",
            "funding",
        ],
        "net_interest_margin": [
            "net interest margin",
            "nim",
            "net interest income",
            "earnings at risk",
        ],
        "rate_sensitivity_gap": [
            "gap",
            "rate sensitivity",
            "repricing",
            "earnings at risk",
        ],
        "economic_outlook": [
            "economic update",
            "economic calendar",
            "inflation",
            "employment",
            "economic growth",
            "yield projections",
        ],
        "regulatory_summaries": [
            "policy",
            "regulatory",
            "call alert",
            "compliant",
            "cblr",
            "capital ratio",
            "leverage ratio",
        ],
        "balance_sheet": [
            "balance sheet",
            "total assets",
            "total liabilities",
            "equity",
            "asset liability analysis",
        ],
        "key_metrics_ratios": [
            "ratio",
            "roa",
            "roe",
            "capital",
            "margin",
            "yield",
            "policy",
        ],
    }

    SECTION_TITLES = {
        "interest_rate_risk": "Interest Rate Risk",
        "liquidity": "Liquidity",
        "investment_portfolio": "Investment Portfolio",
        "loan_portfolio": "Loan Portfolio",
        "deposit_composition": "Deposit Composition",
        "net_interest_margin": "Net Interest Margin & Earnings",
        "rate_sensitivity_gap": "Rate Sensitivity / Gap Analysis",
        "economic_outlook": "Economic Outlook",
        "regulatory_summaries": "Regulatory / Policy Summary",
        "balance_sheet": "Balance Sheet",
        "key_metrics_ratios": "Key Metrics & Ratios",
    }

    def __init__(self, pdf_path: str | Path):
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {self.pdf_path}")

    def parse(self) -> dict[str, Any]:
        """Parse the entire PDF and return section-organized structured data."""
        pages: list[dict[str, Any]] = []

        with pdfplumber.open(self.pdf_path) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                pages.append(
                    {
                        "page": page_number,
                        "text": text,
                        "tables": self._extract_tables(page),
                    }
                )

        metadata = self._extract_metadata(pages)
        sections = self._extract_sections(pages)
        highlights = self._extract_document_highlights(pages)

        return {
            "metadata": {
                **metadata,
                "source_pdf": str(self.pdf_path),
                "total_pages": len(pages),
            },
            "sections": {
                key: {
                    "title": value.title,
                    "pages": value.pages,
                    "key_points": value.key_points,
                    "metrics": value.metrics,
                    "tables": value.tables,
                }
                for key, value in sections.items()
            },
            "document_highlights": highlights,
            "all_tables": [
                {"page": p["page"], "tables": p["tables"]}
                for p in pages
                if p["tables"]
            ],
        }

    def _extract_tables(self, page: pdfplumber.page.Page) -> list[dict[str, Any]]:
        raw_tables = page.extract_tables() or []
        formatted_tables: list[dict[str, Any]] = []

        for table in raw_tables:
            cleaned_rows = []
            for row in table:
                if not row:
                    continue
                cleaned = [self._clean_text(cell or "") for cell in row]
                if any(cell for cell in cleaned):
                    cleaned_rows.append(cleaned)
            if cleaned_rows:
                formatted_tables.append(
                    {
                        "headers": cleaned_rows[0],
                        "rows": cleaned_rows[1:],
                    }
                )

        return formatted_tables

    def _extract_metadata(self, pages: list[dict[str, Any]]) -> dict[str, str]:
        first_page_lines = [
            self._clean_text(line)
            for line in (pages[0]["text"].splitlines() if pages else [])
            if self._clean_text(line)
        ]

        bank_name = self._infer_bank_name(first_page_lines)
        report_date = self._infer_reporting_date("\n".join(p["text"] for p in pages[:15]))

        dt = self._coerce_date(report_date)
        month_year = dt.strftime("%B%Y") if dt else self.UNKNOWN_REPORT_PERIOD

        return {
            "bank_name": bank_name,
            "report_date": report_date,
            "report_month_year": month_year,
            "bank_code": self._bank_code(bank_name),
        }

    def _extract_sections(self, pages: list[dict[str, Any]]) -> dict[str, SectionData]:
        section_pages = {key: [] for key in self.SECTION_KEYWORDS}

        for page in pages:
            text_lower = (page["text"] or "").lower()
            for section, keywords in self.SECTION_KEYWORDS.items():
                if any(keyword in text_lower for keyword in keywords):
                    section_pages[section].append(page)

        sections: dict[str, SectionData] = {}
        for section_key, matched_pages in section_pages.items():
            page_numbers = sorted({page["page"] for page in matched_pages})
            section_text = "\n".join(page["text"] for page in matched_pages)
            key_points = self._extract_key_points(section_text)
            metrics = self._extract_metrics(section_text)

            section_tables: list[dict[str, Any]] = []
            for page in matched_pages:
                for table in page["tables"]:
                    section_tables.append({"page": page["page"], **table})

            sections[section_key] = SectionData(
                title=self.SECTION_TITLES[section_key],
                pages=page_numbers,
                key_points=key_points,
                metrics=metrics,
                tables=section_tables,
            )

        return sections

    def _extract_document_highlights(self, pages: list[dict[str, Any]]) -> list[str]:
        text = "\n".join(page["text"] for page in pages)
        lines = [self._clean_text(line) for line in text.splitlines() if self._clean_text(line)]

        highlights: list[str] = []
        for line in lines:
            if len(line) < self.MIN_HIGHLIGHT_LENGTH:
                continue
            if self._is_noise_line(line):
                continue
            if re.search(r"\d", line) and re.search(r"%|\$|million|billion|basis", line, re.IGNORECASE):
                highlights.append(line)
            if len(highlights) >= 12:
                break
        return highlights

    @staticmethod
    def _clean_text(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _is_noise_line(text: str) -> bool:
        lowered = text.lower()
        return any(
            marker in lowered
            for marker in (
                "©",
                "all rights reserved",
                "member nyse",
                "confidential and proprietary",
                "table of contents",
                "financial strategies team",
                "disclaimers & disclosures",
            )
        )

    def _infer_bank_name(self, first_page_lines: list[str]) -> str:
        for line in first_page_lines[:6]:
            lowered = line.lower()
            if "bank" in lowered and "alco" not in lowered and len(line) <= self.MAX_BANK_NAME_LENGTH:
                return line.title()
        for line in first_page_lines[:4]:
            if line and line.lower() != "alco":
                return line.title()
        return "Client Bank"

    def _infer_reporting_date(self, text: str) -> str:
        patterns = [
            r"for\s+the\s+month\s+ending\s+([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})",
            r"for\s+the\s+period\s+ended\s+([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})",
            r"as\s+of\s+([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})",
            r"\b([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})\b",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                value = match.group(1)
                dt = self._coerce_date(value)
                if dt:
                    return dt.strftime("%B %d, %Y")
        return self.UNKNOWN_REPORT_DATE

    @staticmethod
    def _coerce_date(value: str | None) -> datetime | None:
        if not value:
            return None
        for fmt in ("%B %d, %Y", "%b %d, %Y"):
            try:
                return datetime.strptime(value.strip(), fmt)
            except ValueError:
                continue
        return None

    def _extract_key_points(self, section_text: str) -> list[str]:
        lines = [self._clean_text(line) for line in section_text.splitlines() if self._clean_text(line)]
        points: list[str] = []
        for line in lines:
            if len(line) < self.MIN_KEY_POINT_LENGTH:
                continue
            if self._is_noise_line(line):
                continue
            if line.count(" ") < 5:
                continue
            if self._looks_tabular(line):
                continue
            if re.search(r"\d", line):
                points.append(line)
            if len(points) >= 8:
                break
        return points

    def _extract_metrics(self, section_text: str) -> list[dict[str, str]]:
        metrics: list[dict[str, str]] = []
        lines = [self._clean_text(line) for line in section_text.splitlines() if self._clean_text(line)]

        for line in lines:
            if self._is_noise_line(line):
                continue
            percent_matches = re.findall(r"\b\d{1,3}(?:\.\d+)?%", line)
            amount_matches = re.findall(r"\$\(?\d[\d,]*(?:\.\d+)?\)?", line)

            if not percent_matches and not amount_matches:
                continue

            metric_name = re.sub(r"\s+", " ", line[:80]).strip(" :.-")
            metric_value = ", ".join((percent_matches + amount_matches)[:3])
            if metric_name and metric_value:
                metrics.append({"metric": metric_name, "value": metric_value})

            if len(metrics) >= 12:
                break

        return metrics

    @staticmethod
    def _looks_tabular(text: str) -> bool:
        lowered = text.lower()
        if re.search(
            r"\b(sector|parcoupon|mod dur|walam|current book value|market value gain|history date|account name)\b",
            lowered,
        ):
            return True
        if "|" in text:
            return True
        if text.count("%") >= 2:
            return True
        if sum(ch.isupper() for ch in text) > (len(text) * 0.5):
            return True

        tokens = text.split()
        if not tokens:
            return True

        short_or_numeric = sum(
            1
            for token in tokens
            if len(token) <= 3 or re.fullmatch(r"[\d,().%+\-/$]+", token)
        )
        return short_or_numeric / len(tokens) > PDFParser.TABULAR_TOKEN_RATIO_THRESHOLD

    @staticmethod
    def _bank_code(bank_name: str) -> str:
        rough_words = [word for word in re.split(r"\W+", bank_name) if word and word.lower() not in {"of", "the", "and"}]
        words: list[str] = []
        for word in rough_words:
            parts = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])", word)
            words.extend(parts or [word])
        if not words:
            return "BANK"
        if len(words) == 1:
            return words[0][:4].upper()
        return "".join(word[0] for word in words[:4]).upper()
