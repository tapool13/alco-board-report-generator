"""Main entry point for ALCO Board Report Generator."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent))

from pdf_parser import PDFParser
from report_generator import ReportGenerator


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate ALCO board report documents from a source PDF.")
    parser.add_argument("pdf_path", help="Path to source ALCO PDF")
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory where generated report(s) will be written (default: output)",
    )
    parser.add_argument(
        "--report-type",
        choices=["both", "board", "analysis"],
        default="both",
        help="Choose which report(s) to generate (default: both)",
    )
    return parser


def main() -> None:
    args = build_argument_parser().parse_args()

    print("ALCO Board Report Generator")
    print("=" * 40)
    print(f"Loading PDF: {args.pdf_path}")

    parser = PDFParser(args.pdf_path)
    print("Parsing PDF pages, text, and tables...")
    parsed_data = parser.parse()

    generator = ReportGenerator(parsed_data, args.output_dir)

    generated_files: list[Path] = []
    if args.report_type in ("both", "board"):
        print("Generating board report document...")
        generated_files.append(generator.generate_board_report())

    if args.report_type in ("both", "analysis"):
        print("Generating ALCO board analysis document...")
        generated_files.append(generator.generate_alco_analysis())

    print("Done. Generated files:")
    for generated in generated_files:
        print(f"- {generated}")


if __name__ == "__main__":
    main()
