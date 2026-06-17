import json
import re
from datetime import datetime
from pathlib import Path

import openpyxl


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV = PROJECT_ROOT / ".env"
DEFAULT_SOURCE = PROJECT_ROOT / "input" / "stocks.xlsx"
HTML = PROJECT_ROOT / "outputs" / "portfolio_dashboard.html"
TEMPLATE = PROJECT_ROOT / "src" / "portfolio_dashboard.template.html"


SECTOR_RULES = [
    ("Cash", ["CMA", "RP", "CASH"]),
    ("Semiconductors", ["SEMICON", "CHIP"]),
    ("AI/Software", ["AI", "SOFTWARE", "CLOUD", "DATACENTER"]),
    ("Robotics", ["ROBOT", "ROBOTICS"]),
    ("Auto/Mobility", ["AUTO", "MOBILITY", "EV", "BATTERY"]),
    ("Power/Infrastructure", ["POWER", "INFRA", "UTILITY"]),
    ("Consumer/Healthcare", ["CONSUMER", "FOOD", "HEALTH", "BIO"]),
    ("Materials/Commodities", ["STEEL", "MATERIAL", "COMMODITY", "GOLD"]),
    ("Finance/Dividend ETF", ["DIVIDEND", "BANK", "FINANCE"]),
    ("REIT/Infrastructure ETF", ["REIT", "REAL ESTATE", "INFRA"]),
    ("Covered Call ETF", ["COVERED", "WEEKLY"]),
    ("Index ETF", ["KOSPI", "KOSDAQ", "S&P", "NASDAQ", "200", "150"]),
]



ACCOUNT_BY_SHEET = {
    "미래에셋CMA": ("CMA", "미래에셋CMA"),
    "미래에셋ISA": ("ISA", "미래에셋ISA"),
    "미래에셋종합": ("종합", "미래에셋종합"),
    "한국투자RIA": ("RIA", "한국투자RIA"),
}


def load_env(path):
    values = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def source_path():
    configured = load_env(ENV).get("STOCKS_XLSX_PATH", "")
    return Path(configured) if configured else DEFAULT_SOURCE


def num(value, default=0.0):
    if value is None or value == "":
        return default
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "").replace("%", "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def clean_name(value):
    return re.sub(r"\s+", " ", str(value or "").strip())


def normalize_name_for_lookup(name):
    return clean_name(name).replace("(소수)", "")


def load_existing_metadata():
    if not HTML.exists():
        return {}, {}
    text = HTML.read_text(encoding="utf-8")
    match = re.search(r"    const exampleHoldings = (\[.*?\]);\s*    const (?:dartEnrichment|sectorColors)", text, re.S)
    if not match:
        return {}, {}
    try:
        rows = json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}, {}
    symbol_by_name = {}
    sector_by_name = {}
    for row in rows:
        key = normalize_name_for_lookup(row.get("name") or row.get("ticker"))
        if key and row.get("symbol"):
            symbol_by_name[key] = row.get("symbol")
        if key and row.get("sector"):
            sector_by_name[key] = row.get("sector")
    return symbol_by_name, sector_by_name


def classify(name, fallback="기타"):
    text = clean_name(name)
    for sector, tokens in SECTOR_RULES:
        if any(token in text for token in tokens):
            return sector
    if any(token in text for token in ["KODEX", "TIGER", "ACE", "PLUS"]):
        return "ETF"
    return fallback


def sheet_rows(ws):
    return [[cell for cell in row] for row in ws.iter_rows(values_only=True)]


def header_map(header):
    return {clean_name(value): idx for idx, value in enumerate(header)}


def get(row, hmap, name):
    idx = hmap.get(name)
    return row[idx] if idx is not None and idx < len(row) else ""


def parse_holdings_sheet(ws, symbol_by_name, sector_by_name):
    rows = sheet_rows(ws)
    if not rows:
        return []
    hmap = header_map(rows[0])
    account_type, broker = ACCOUNT_BY_SHEET.get(ws.title, ("일반", ws.title))
    parsed = []
    for row in rows[1:]:
        name = clean_name(get(row, hmap, "종목명"))
        if not name or name in {"합계", "총계"}:
            continue
        qty = num(get(row, hmap, "보유량"))
        avg_price = num(get(row, hmap, "평균단가"))
        current_price = num(get(row, hmap, "현재가"), default=None)
        buy_amount = num(get(row, hmap, "매입금액"))
        value_amount = num(get(row, hmap, "평가금액"), default=None)
        if qty <= 0 and value_amount is None:
            continue

        is_cash = "CMA/RP" in str(get(row, hmap, "유형")) or "RP" in name or "예수금" in name
        if is_cash:
            current_price = 1
            avg_price = 1
            qty = value_amount or buy_amount or qty
            value_amount = qty

        lookup = normalize_name_for_lookup(name)
        stock_code = clean_name(get(row, hmap, "종목번호"))
        if stock_code and stock_code.isdigit():
            stock_code = stock_code.zfill(6)
        symbol = symbol_by_name.get(lookup, "")
        if not symbol and re.fullmatch(r"\d{6}", stock_code):
            symbol = f"{stock_code}.KS"
        sector = sector_by_name.get(lookup) or classify(name)
        price_status = "manual" if current_price not in (None, 0) else "missing_symbol"
        parsed.append({
            "ticker": name,
            "symbol": symbol,
            "name": name,
            "accountType": account_type,
            "broker": broker,
            "sector": sector,
            "avgPrice": round(avg_price, 6),
            "shares": round(qty, 6),
            "currentPrice": round(current_price or avg_price, 6),
            "dividendYield": "",
            "annualDividend": "",
            "payoutMonths": "",
            "dayChange": "",
            "rsi": "",
            "bb": "",
            "priceStatus": price_status,
            "priceSource": "XLSX",
        })
    return parsed


def parse_cash_summary(ws):
    rows = sheet_rows(ws)
    if not rows:
        return []
    hmap = header_map(rows[0])
    parsed = []
    for row in rows[1:]:
        account_type = clean_name(get(row, hmap, "계좌유형"))
        cash = num(get(row, hmap, "D+2원화예수금"))
        if not account_type or cash <= 0:
            continue
        broker = f"미래에셋{account_type}"
        name = f"{broker} 원화예수금"
        parsed.append({
            "ticker": name,
            "symbol": "",
            "name": name,
            "accountType": account_type,
            "broker": broker,
            "sector": "현금성",
            "avgPrice": 1,
            "shares": round(cash, 2),
            "currentPrice": 1,
            "dividendYield": "",
            "annualDividend": "",
            "payoutMonths": "",
            "dayChange": 0,
            "rsi": "",
            "bb": "",
            "priceStatus": "manual",
            "priceSource": "XLSX 현금",
        })
    return parsed


def update_html(holdings):
    if not TEMPLATE.exists():
        raise RuntimeError(f"Dashboard template not found: {TEMPLATE}")
    text = TEMPLATE.read_text(encoding="utf-8")
    version = "stocks-xlsx-accounts-cash-" + datetime.now().strftime("%Y%m%d%H%M%S")
    replacement = "    const exampleHoldings = " + json.dumps(holdings, ensure_ascii=False, indent=6) + ";"
    text = re.sub(
        r"    const defaultDataVersion = \"[^\"]+\";",
        f"    const defaultDataVersion = \"{version}\";",
        text,
    )
    text = re.sub(
        r"    const exampleHoldings = \[.*?\];(?=\s*    const (?:dartEnrichment|sectorColors))",
        replacement,
        text,
        flags=re.S,
    )
    text = text.replace(
        "계좌번호, 주문번호, 예수금 등 민감정보는 저장하지 않습니다.",
        "계좌번호, 주문번호 등 민감정보는 저장하지 않고 예수금은 금액만 현금성 자산으로 반영합니다.",
    )
    HTML.parent.mkdir(parents=True, exist_ok=True)
    HTML.write_text(text, encoding="utf-8", newline="")


def main():
    source = source_path()
    if not source.exists():
        raise SystemExit(f"Workbook not found. Set STOCKS_XLSX_PATH in .env or place stocks.xlsx at {DEFAULT_SOURCE}")
    symbol_by_name, sector_by_name = load_existing_metadata()
    wb = openpyxl.load_workbook(source, data_only=True)
    holdings = []
    for ws in wb.worksheets:
        if ws.title == "미래에셋전체":
            holdings.extend(parse_cash_summary(ws))
        elif ws.title in ACCOUNT_BY_SHEET:
            holdings.extend(parse_holdings_sheet(ws, symbol_by_name, sector_by_name))
    holdings.sort(key=lambda r: (r["broker"], r["sector"], r["name"]))
    update_html(holdings)
    cash_count = sum(1 for row in holdings if row["sector"] == "현금성")
    print(json.dumps({
        "rows": len(holdings),
        "cash_rows": cash_count,
        "sheets": [ws.title for ws in wb.worksheets],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
