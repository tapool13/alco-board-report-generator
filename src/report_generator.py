"""Word report generation logic for ALCO board reports."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH

from config import BALANCE_SHEET_FALLBACK_FIELDS, SECTION_HEADERS


class ReportGenerator:
    """Generate formatted board report .docx files from parsed ALCO data."""

    def __init__(self, institution: str | None = None) -> None:
        self.institution = institution

    def generate(self, data: Dict, output_path: str) -> None:
        document = Document()

        metadata = data.get("metadata", {})
        institution = self.institution or metadata.get("institution", "Institution")
        report_date = metadata.get("report_date", datetime.now().strftime("%B %d, %Y"))

        self._add_cover_page(document, institution, report_date)
        self._add_executive_summary(document, data)

        self._add_metrics_table_section(
            document,
            SECTION_HEADERS["interest_rate_risk"],
            data.get("interest_rate_risk", {}).get("metrics", []),
            columns=[("Metric", "metric"), ("Actual", "actual"), ("Policy Limit", "policy_limit"), ("Status", "status")],
        )
        self._add_metrics_table_section(
            document,
            SECTION_HEADERS["liquidity"],
            data.get("liquidity", {}).get("metrics", []),
            columns=[("Metric", "metric"), ("Value", "value"), ("Policy Limit", "policy_limit"), ("Status", "status")],
        )

        balance_sheet = data.get("balance_sheet", {})
        balance_metrics = self._coerce_balance_sheet_metrics(balance_sheet)
        self._add_metrics_table_section(
            document,
            SECTION_HEADERS["balance_sheet"],
            balance_metrics,
            columns=[("Metric", "metric"), ("Value", "value")],
        )

        nim = data.get("net_interest_margin", {})
        nim_heading = document.add_heading(SECTION_HEADERS["net_interest_margin"], level=1)
        nim_heading.alignment = WD_ALIGN_PARAGRAPH.LEFT
        nim_paragraph = document.add_paragraph()
        nim_paragraph.add_run("Current NIM: ").bold = True
        nim_paragraph.add_run(nim.get("nim") or "Not available")
        self._add_table(document, nim.get("metrics", []), [("Metric", "metric"), ("Value", "value")])

        self._add_metrics_table_section(
            document,
            SECTION_HEADERS["investment_portfolio"],
            data.get("investment_portfolio", {}).get("metrics", []),
            columns=[("Metric", "metric"), ("Value", "value")],
        )

        self._add_metrics_table_section(
            document,
            SECTION_HEADERS["policy_compliance"],
            data.get("policy_compliance", {}).get("items", []),
            columns=[("Metric", "metric"), ("Actual", "actual"), ("Policy Limit", "policy_limit"), ("Status", "status")],
        )

        document.add_heading(SECTION_HEADERS["appendix"], level=1)
        document.add_paragraph("Additional schedules, assumptions, and backup analysis can be added here.")

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        document.save(str(output))

    def _add_cover_page(self, document: Document, institution: str, report_date: str) -> None:
        title = document.add_paragraph()
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title.add_run("ALCO Board Report").bold = True

        inst = document.add_paragraph()
        inst.alignment = WD_ALIGN_PARAGRAPH.CENTER
        inst.add_run(institution)

        date_p = document.add_paragraph()
        date_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        date_p.add_run(report_date)

        document.add_page_break()

    def _add_executive_summary(self, document: Document, data: Dict) -> None:
        document.add_heading(SECTION_HEADERS["executive_summary"], level=1)

        institution = data.get("metadata", {}).get("institution", "the institution")
        policy_summary = data.get("policy_compliance", {}).get("summary", {})
        green = policy_summary.get("green", 0)
        yellow = policy_summary.get("yellow", 0)
        red = policy_summary.get("red", 0)

        summary = (
            f"This report summarizes ALCO trends for {institution}, including interest rate risk, "
            f"liquidity, balance sheet condition, net interest margin, and investment performance. "
            f"Policy monitoring currently shows {green} green, {yellow} yellow, and {red} red indicators."
        )
        document.add_paragraph(summary)

    def _add_metrics_table_section(
        self,
        document: Document,
        title: str,
        rows: List[Dict],
        columns: Iterable[tuple[str, str]],
    ) -> None:
        document.add_heading(title, level=1)
        if not rows:
            document.add_paragraph("No data available for this section.")
            return
        self._add_table(document, rows, columns)

    def _add_table(self, document: Document, rows: List[Dict], columns: Iterable[tuple[str, str]]) -> None:
        columns = list(columns)
        table = document.add_table(rows=1, cols=len(columns))
        table.style = "Table Grid"

        headers = table.rows[0].cells
        for idx, (label, _) in enumerate(columns):
            headers[idx].text = label

        for row_data in rows:
            row_cells = table.add_row().cells
            for idx, (_, key) in enumerate(columns):
                value = row_data.get(key, "")
                row_cells[idx].text = str(value) if value is not None else ""

    def _coerce_balance_sheet_metrics(self, balance_sheet: Dict) -> List[Dict]:
        metrics = list(balance_sheet.get("metrics", []))
        if metrics:
            return metrics

        fallback = []
        for label, key in BALANCE_SHEET_FALLBACK_FIELDS:
            value = balance_sheet.get(key)
            if value:
                fallback.append({"metric": label, "value": value})
        return fallback
