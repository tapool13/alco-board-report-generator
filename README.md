# ALCO Board Report Generator

Generate two repeatable board-facing Word outputs from an ALCO PDF package:

1. **Board Report** (financial summary format)
2. **ALCO Board Analysis** (sectioned narrative + metrics format)

## What the tool does

- Parses all pages in an ALCO PDF with `pdfplumber`
- Extracts text and tables across key sections (interest rate risk, liquidity, investments, loans, deposits, NIM, gap/rate sensitivity, economic outlook, regulatory/policy, balance sheet, metrics/ratios)
- Builds a structured dataset from keyword + positional heuristics
- Generates uniformly structured `.docx` outputs with `python-docx`
- Auto-names output files from extracted bank and reporting period metadata

## Installation

```bash
pip install -r requirements.txt
```

## Usage

Generate both reports:

```bash
python src/main.py "KeySavings Bank - April 2026 ALCO.pdf"
```

Generate only the board report:

```bash
python src/main.py "KeySavings Bank - April 2026 ALCO.pdf" --report-type board
```

Generate only the ALCO analysis into a custom directory:

```bash
python src/main.py "KeySavings Bank - April 2026 ALCO.pdf" --report-type analysis --output-dir ./output
```

## Output structure

### Board Report

- Title + reporting period
- At-a-glance highlights table
- Revenue & Earnings
- Liquidity & Funding
- Balance Sheet & Capital
- Interest Rate Risk
- Economic Outlook
- Board Considerations

### ALCO Board Analysis

- Cover header lines (board + institution + period)
- Sectioned analysis (I–X): executive summary, performance, capital, liquidity, IRR, investments, loans, comparative metrics, economic environment, action items
- Section metrics tables and risk-focused board actions

## Source files

- `src/pdf_parser.py` — PDF extraction + section classification
- `src/report_generator.py` — Word document generation
- `src/main.py` — CLI orchestration
