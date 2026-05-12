"""Main entry point for ALCO Board Report Generator"""

import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent))

from pdf_parser import PDFParser
from report_generator import ReportGenerator


def main():
    """
    Main function to orchestrate PDF parsing and report generation.
    """
    print("ALCO Board Report Generator")
    print("=" * 40)
    
    # TODO: Implement main logic
    # 1. Parse input PDF
    # 2. Extract data
    # 3. Generate Word document
    
    print("Waiting for example files to begin implementation...")


if __name__ == "__main__":
    main()
