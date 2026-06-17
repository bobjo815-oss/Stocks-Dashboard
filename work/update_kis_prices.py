import json
import re
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path

try:
    import certifi
except ImportError:
    certifi = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HTML = PROJECT_ROOT / "outputs" / "portfolio_dashboard.html"
ENV = PROJECT_ROOT / ".env"
OUT = PROJECT_ROOT / "work" / "kis_price_update.json"
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where()) if certifi else ssl.create_default_context()


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


def request_json(url, method="GET", headers=None, payload=None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    with urllib.request.urlopen(req, timeout=20, context=SSL_CONTEXT) as res:
        return json.loads(res.read().decode("utf-8"))


def kis_base_url(env):
    return "https://openapivts.koreainvestment.com:29443" if env.lower() in {"vts", "paper", "mock"} else "https://openapi.koreainvestment.com:9443"


def get_token(base_url, app_key, app_secret):
    data = request_json(
        f"{base_url}/oauth2/tokenP",
        method="POST",
        headers={"content-type": "application/json; charset=utf-8"},
        payload={"grant_type": "client_credentials", "appkey": app_key, "appsecret": app_secret},
    )
    token = data.get("access_token")
    if not token:
        raise RuntimeError(f"KIS token failed: {data.get('msg1') or data.get('error_description') or data}")
    return token


def load_holdings():
    text = HTML.read_text(encoding="utf-8")
    match = re.search(r"    const exampleHoldings = (\[.*?\]);\s*    const (?:dartEnrichment|sectorColors)", text, re.S)
    if not match:
        raise RuntimeError("exampleHoldings block not found")
    return text, json.loads(match.group(1))


def stock_code(row):
    text = f"{row.get('symbol', '')} {row.get('ticker', '')}"
    match = re.search(r"(\d{6})", text)
    return match.group(1) if match else ""


def fetch_domestic_price(base_url, token, app_key, app_secret, code):
    params = urllib.parse.urlencode({"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code})
    headers = {
        "authorization": f"Bearer {token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": "FHKST01010100",
        "custtype": "P",
        "content-type": "application/json; charset=utf-8",
    }
    data = request_json(f"{base_url}/uapi/domestic-stock/v1/quotations/inquire-price?{params}", headers=headers)
    if data.get("rt_cd") != "0":
        raise RuntimeError(data.get("msg1") or data.get("msg_cd") or "KIS price failed")
    out = data.get("output") or {}
    price = float(str(out.get("stck_prpr") or "0").replace(",", ""))
    prev = float(str(out.get("stck_sdpr") or "0").replace(",", ""))
    change = (price / prev - 1) * 100 if price and prev else None
    return {
        "price": price,
        "dayChange": change,
        "name": out.get("hts_kor_isnm", ""),
        "volume": out.get("acml_vol", ""),
    }


def update_html(text, holdings):
    replacement = "    const exampleHoldings = " + json.dumps(holdings, ensure_ascii=False, indent=6) + ";"
    text = re.sub(
        r"    const exampleHoldings = \[.*?\];(?=\s*    const (?:dartEnrichment|sectorColors))",
        replacement,
        text,
        flags=re.S,
    )
    HTML.write_text(text, encoding="utf-8", newline="")


def main():
    env = load_env(ENV)
    app_key = env.get("KIS_APP_KEY", "")
    app_secret = env.get("KIS_APP_SECRET", "")
    if not app_key or not app_secret:
        raise SystemExit("KIS_APP_KEY or KIS_APP_SECRET is missing in .env")
    base_url = kis_base_url(env.get("KIS_ENV", "prod"))
    token = get_token(base_url, app_key, app_secret)
    text, holdings = load_holdings()
    codes = sorted({code for row in holdings for code in [stock_code(row)] if code})
    price_by_code = {}
    failures = {}
    for code in codes:
        try:
            price_by_code[code] = fetch_domestic_price(base_url, token, app_key, app_secret, code)
            time.sleep(0.06)
        except Exception as exc:
            failures[code] = type(exc).__name__
    updated = 0
    for row in holdings:
        code = stock_code(row)
        info = price_by_code.get(code)
        if not info:
            continue
        row["currentPrice"] = round(info["price"], 4)
        if info["dayChange"] is not None:
            row["dayChange"] = round(info["dayChange"], 4)
        row["priceStatus"] = "market"
        row["priceSource"] = "KIS"
        updated += 1
    update_html(text, holdings)
    OUT.write_text(json.dumps({"updated_rows": updated, "codes": len(price_by_code), "failures": failures}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"updated_rows": updated, "codes": len(price_by_code), "failures": len(failures)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
