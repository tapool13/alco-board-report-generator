"""Main entry point for ALCO Board Report Generator."""

from __future__ import annotations

import argparse
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config import DEFAULT_OUTPUT_FILENAME_TEMPLATE
from pdf_parser import PDFParser
from report_generator import ReportGenerator


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip()).strip("_") or "Institution"


def _build_default_output_path(input_path: Path, institution: str) -> Path:
    filename = DEFAULT_OUTPUT_FILENAME_TEMPLATE.format(
        institution=_safe_name(institution),
        date=datetime.now().strftime("%Y%m%d"),
    )
    return input_path.parent / filename


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate ALCO Board Report from ALCO PDF input")
    parser.add_argument("--input", required=True, help="Path to source ALCO PDF")
    parser.add_argument("--output", help="Output path for generated .docx report")
    parser.add_argument("--institution", help="Optional institution name override")
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()

    try:
        print("ALCO Board Report Generator")
        print("=" * 40)
        print(f"[1/3] Parsing PDF: {input_path}")

        parser = PDFParser()
        data = parser.parse(str(input_path))

        institution = args.institution or data.get("metadata", {}).get("institution", "Institution")
        data.setdefault("metadata", {})["institution"] = institution

        output_path = Path(args.output).expanduser().resolve() if args.output else _build_default_output_path(input_path, institution)

        print("[2/3] Generating Word report")
        generator = ReportGenerator(institution=institution)
        generator.generate(data, str(output_path))

        print(f"[3/3] Done. Report saved to: {output_path}")
        return 0
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pylint: disable=broad-except
        print(f"Error generating report: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
