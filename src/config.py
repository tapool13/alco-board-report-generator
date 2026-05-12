"""Configuration constants for ALCO board report generation."""

DEFAULT_OUTPUT_FILENAME_TEMPLATE = "{institution}_ALCO_Board_Report_{date}.docx"

SECTION_HEADERS = {
    "executive_summary": "Executive Summary",
    "interest_rate_risk": "Interest Rate Risk",
    "liquidity": "Liquidity",
    "balance_sheet": "Balance Sheet Summary",
    "net_interest_margin": "Net Interest Margin",
    "investment_portfolio": "Investment Portfolio",
    "policy_compliance": "Policy Compliance Summary",
    "appendix": "Appendix",
}

POLICY_LIMIT_DEFAULTS = {
    "NET INTEREST MARGIN": "> 2.75%",
    "LIQUIDITY": "> 20.00%",
    "LEVERAGE RATIO": "> 8.00%",
    "CAPITAL RATIO": "> 8.00%",
    "EVE CHANGE +300": "> -35.00%",
    "NII CHANGE +300": "> -25.00%",
}
