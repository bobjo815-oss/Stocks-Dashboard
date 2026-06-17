import json
import re
import ssl
import urllib.parse
import urllib.request
import zipfile
from datetime import date
from html import unescape
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET

try:
    import certifi
except ImportError:
    certifi = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HTML = PROJECT_ROOT / "outputs" / "portfolio_dashboard.html"
ENV = PROJECT_ROOT / ".env"
OUT = PROJECT_ROOT / "work" / "dart_enrichment.json"
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where()) if certifi else ssl.create_default_context()


REPORT_SIGNALS = [
    ("risk", "수요 둔화", ("수요 둔화", "수요 감소", "판매 감소", "경기 둔화", "업황 부진")),
    ("risk", "경쟁 심화", ("경쟁 심화", "가격 경쟁", "시장 경쟁", "경쟁이 심화")),
    ("risk", "원가/환율 부담", ("원재료", "원가 상승", "환율 변동", "환율 상승", "운임", "물류비")),
    ("risk", "재무/차입 부담", ("차입금", "부채", "이자비용", "유동성", "손상차손", "재고자산")),
    ("risk", "규제/소송", ("규제", "소송", "제재", "과징금", "분쟁", "우발부채")),
    ("opportunity", "수주/백로그", ("수주", "수주잔고", "공급계약", "장기계약", "납품")),
    ("opportunity", "투자/CAPEX", ("시설투자", "설비투자", "CAPEX", "증설", "생산능력")),
    ("opportunity", "성장 테마", ("AI", "인공지능", "반도체", "로봇", "전력기기", "데이터센터")),
    ("opportunity", "해외 확장", ("해외시장", "북미", "유럽", "중국", "동남아", "글로벌")),
    ("opportunity", "주주환원", ("배당", "자사주", "주주환원", "분기배당", "현금배당")),
]

DIVIDEND_KEYWORDS = ("1주당", "주당", "배당금", "배당기준일", "지급", "지급예정", "배당금총액", "시가배당률")


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


def request_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "PortfolioDashboard/1.0"})
    with urllib.request.urlopen(req, timeout=20, context=SSL_CONTEXT) as res:
        return json.loads(res.read().decode("utf-8"))


def request_bytes(url):
    req = urllib.request.Request(url, headers={"User-Agent": "PortfolioDashboard/1.0"})
    with urllib.request.urlopen(req, timeout=30, context=SSL_CONTEXT) as res:
        return res.read()


def decode_bytes(payload):
    for encoding in ("utf-8", "cp949", "euc-kr"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8", errors="ignore")


def load_holdings():
    text = HTML.read_text(encoding="utf-8")
    match = re.search(r"    const exampleHoldings = (\[.*?\]);\s*    const (?:dartEnrichment|sectorColors)", text, re.S)
    if not match:
        raise RuntimeError("exampleHoldings block not found")
    return json.loads(match.group(1))


def inject_dart_enrichment(result):
    text = HTML.read_text(encoding="utf-8")
    block = "    const dartEnrichment = " + json.dumps(result, ensure_ascii=False, indent=6) + ";"
    if re.search(r"    const dartEnrichment = .*?;\n\n    const sectorColors", text, re.S):
        text = re.sub(
            r"    const dartEnrichment = .*?;\n\n    const sectorColors",
            block + "\n\n    const sectorColors",
            text,
            flags=re.S,
        )
    else:
        text = text.replace("\n    const sectorColors", "\n" + block + "\n\n    const sectorColors")
    HTML.write_text(text, encoding="utf-8", newline="")


def stock_code_from_symbol(row):
    text = f"{row.get('symbol', '')} {row.get('ticker', '')}"
    match = re.search(r"(\d{6})", text)
    return match.group(1) if match else ""


def fetch_corp_codes(api_key):
    url = "https://opendart.fss.or.kr/api/corpCode.xml?" + urllib.parse.urlencode({"crtfc_key": api_key})
    payload = request_bytes(url)
    with zipfile.ZipFile(BytesIO(payload)) as zf:
        root = ET.fromstring(zf.read(zf.namelist()[0]))
    corp_by_stock = {}
    for item in root.findall("list"):
        stock_code = (item.findtext("stock_code") or "").strip()
        if not stock_code:
            continue
        corp_by_stock[stock_code] = {
            "corp_code": (item.findtext("corp_code") or "").strip(),
            "corp_name": (item.findtext("corp_name") or "").strip(),
            "stock_code": stock_code,
            "modify_date": (item.findtext("modify_date") or "").strip(),
        }
    return corp_by_stock


def fetch_recent_reports(api_key, corp_code):
    today = date.today()
    params = {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bgn_de": f"{today.year - 2}0101",
        "end_de": today.strftime("%Y%m%d"),
        "page_count": "100",
    }
    url = "https://opendart.fss.or.kr/api/list.json?" + urllib.parse.urlencode(params)
    data = request_json(url)
    if data.get("status") not in {"000", "013"}:
        raise RuntimeError(data.get("message") or data.get("status") or "DART request failed")
    return data.get("list") or []


def pick_reports(reports, words, limit=5):
    return [
        {
            "rcept_no": report.get("rcept_no", ""),
            "rcept_dt": report.get("rcept_dt", ""),
            "report_nm": report.get("report_nm", ""),
        }
        for report in reports
        if any(word in (report.get("report_nm") or "") for word in words)
    ][:limit]


def fetch_report_text(api_key, rcept_no):
    if not rcept_no:
        return ""
    url = "https://opendart.fss.or.kr/api/document.xml?" + urllib.parse.urlencode({
        "crtfc_key": api_key,
        "rcept_no": rcept_no,
    })
    payload = request_bytes(url)
    if not payload.startswith(b"PK"):
        return ""
    chunks = []
    with zipfile.ZipFile(BytesIO(payload)) as zf:
        for name in zf.namelist():
            if not name.lower().endswith((".xml", ".html", ".htm", ".txt")):
                continue
            raw = zf.read(name)
            text = decode_bytes(raw)
            text = re.sub(r"<[^>]+>", " ", text)
            chunks.append(unescape(text))
    text = clean_report_text(" ".join(chunks))
    return text[:350000]


def clean_report_text(text):
    text = unescape(text or "")
    text = re.sub(r"[-_=─━]{4,}", " ", text)
    text = re.sub(r"[ㆍ·.]{6,}", " ", text)
    text = re.sub(r"\b\d+\s*/\s*\d+\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def looks_like_toc(snippet):
    if not snippet:
        return True
    toc_words = ("목 차", "I. 회사의 개요", "II. 사업의 내용", "III. 재무에 관한 사항", "표지", "대표이사 등의 확인")
    if any(word in snippet for word in toc_words):
        return True
    section_hits = len(re.findall(r"\b[IVX]+\.\s|[0-9]+\.\s", snippet))
    return section_hits >= 5


def signal_snippet(text, keywords):
    lowered = text.lower()
    candidates = []
    for keyword in keywords:
        start = 0
        needle = keyword.lower()
        while True:
            idx = lowered.find(needle, start)
            if idx < 0:
                break
            start = idx + len(needle)
            before = max(0, idx - 110)
            after = min(len(text), idx + len(keyword) + 150)
            snippet = clean_report_text(text[before:after])
            if not looks_like_toc(snippet):
                candidates.append((idx, snippet))
            if len(candidates) >= 8:
                break
    if not candidates:
        return ""
    return sorted(candidates)[0][1]


def analyze_report_text(text):
    if not text:
        return []
    signals = []
    for signal_type, title, keywords in REPORT_SIGNALS:
        count = sum(len(re.findall(re.escape(keyword), text, re.I)) for keyword in keywords)
        if count <= 0:
            continue
        snippet = signal_snippet(text, keywords)
        signals.append({
            "type": signal_type,
            "title": title,
            "count": count,
            "snippet": snippet[:220],
        })
    return sorted(signals, key=lambda item: item["count"], reverse=True)[:6]


def fetch_report_analysis(api_key, periodic_reports):
    for report in periodic_reports[:2]:
        rcept_no = report.get("rcept_no", "")
        try:
            text = fetch_report_text(api_key, rcept_no)
            signals = analyze_report_text(text)
        except Exception as exc:
            return {"rcept_no": rcept_no, "error": type(exc).__name__, "signals": []}
        if signals:
            return {
                "rcept_no": rcept_no,
                "rcept_dt": report.get("rcept_dt", ""),
                "report_nm": report.get("report_nm", ""),
                "signals": signals,
            }
    return {"signals": []}


def extract_dividend_analysis(api_key, dividend_reports):
    if not dividend_reports:
        return {}
    report = dividend_reports[0]
    rcept_no = report.get("rcept_no", "")
    result = {
        "rcept_no": rcept_no,
        "rcept_dt": report.get("rcept_dt", ""),
        "report_nm": report.get("report_nm", ""),
        "facts": [],
    }
    try:
        text = fetch_report_text(api_key, rcept_no)
    except Exception as exc:
        result["error"] = type(exc).__name__
        return result
    facts = []
    for keyword in DIVIDEND_KEYWORDS:
        snippet = signal_snippet(text, (keyword,))
        if snippet and snippet not in facts:
            facts.append(snippet[:180])
        if len(facts) >= 4:
            break
    money = sorted(set(re.findall(r"(?<![\d.])\d{1,3}(?:,\d{3})*\s*원", text)))[:5]
    dates = sorted(set(re.findall(r"20\d{2}[.\-/년]\s*\d{1,2}[.\-/월]\s*\d{1,2}\s*일?", text)))[:6]
    result["facts"] = facts
    result["money_candidates"] = money
    result["date_candidates"] = dates
    return result


def parse_amount(value):
    text = str(value or "").replace(",", "").strip()
    try:
        return float(text)
    except ValueError:
        return None


def summarize_financials(year, rows):
    aliases = {
        "revenue": ("매출액", "영업수익", "수익(매출액)"),
        "operating_income": ("영업이익",),
        "net_income": ("당기순이익", "연결당기순이익"),
        "assets": ("자산총계",),
        "liabilities": ("부채총계",),
        "equity": ("자본총계",),
    }
    result = {"year": year}
    for key, names in aliases.items():
        for row in rows:
            account = row.get("account_nm") or ""
            if any(name == account or name in account for name in names):
                amount = parse_amount(row.get("thstrm_amount"))
                if amount is not None:
                    result[key] = amount
                    break
    if result.get("assets"):
        result["debt_ratio"] = result.get("liabilities", 0) / result["assets"] * 100
    if result.get("revenue"):
        result["op_margin"] = result.get("operating_income", 0) / result["revenue"] * 100
    return result


def fetch_financial_snapshot(api_key, corp_code):
    for year in range(date.today().year - 1, date.today().year - 4, -1):
        params = {
            "crtfc_key": api_key,
            "corp_code": corp_code,
            "bsns_year": str(year),
            "reprt_code": "11011",
            "fs_div": "CFS",
        }
        url = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json?" + urllib.parse.urlencode(params)
        data = request_json(url)
        if data.get("status") == "000" and data.get("list"):
            return summarize_financials(year, data.get("list") or [])
    return {}


def build_guide_flags(company_name, dividend_reports, periodic_reports, financials, report_analysis, dividend_analysis):
    flags = []
    if dividend_analysis:
        report_name = dividend_analysis.get("report_nm") or "배당 관련 공시"
        report_date = dividend_analysis.get("rcept_dt") or ""
        facts = dividend_analysis.get("facts") or []
        money = ", ".join(dividend_analysis.get("money_candidates") or [])
        dates = ", ".join(dividend_analysis.get("date_candidates") or [])
        details = facts[0] if facts else "주당배당금, 기준일, 지급일 후보를 원문에서 추가 확인해야 합니다."
        extras = " / ".join(part for part in [f"금액 후보: {money}" if money else "", f"일자 후보: {dates}" if dates else ""] if part)
        flags.append({
            "type": "opportunity",
            "title": "배당/주주환원 세부 확인",
            "text": f"{company_name}: {report_date} {report_name}. {details}{' ' + extras if extras else ''}",
        })
    if periodic_reports:
        flags.append({
            "type": "watch",
            "title": "정기보고서 업데이트",
            "text": f"{company_name}의 최신 정기보고서가 DART에 있습니다. 실적 시즌 전후로 비중과 손익 구간을 재점검하십시오.",
        })
    opportunity_signals = [signal for signal in (report_analysis.get("signals") or []) if signal.get("type") == "opportunity"]
    risk_signals = [signal for signal in (report_analysis.get("signals") or []) if signal.get("type") == "risk"]
    ordered_signals = opportunity_signals[:3] + risk_signals[:2]
    for signal in ordered_signals:
        if not signal.get("snippet"):
            continue
        snippet = signal.get("snippet") or "본문 키워드가 반복 확인됩니다."
        prefix = "본문 리스크" if signal.get("type") == "risk" else "본문 기회"
        flags.append({
            "type": signal.get("type") or "watch",
            "title": f"{prefix}: {signal.get('title', '공시 신호')}",
            "text": f"{company_name} 보고서 본문에서 '{signal.get('title', '공시 신호')}' 신호가 확인됩니다. 문맥: {snippet}",
        })
    debt_ratio = financials.get("debt_ratio")
    op_margin = financials.get("op_margin")
    if debt_ratio is not None and debt_ratio > 70:
        flags.append({
            "type": "risk",
            "title": "재무 레버리지 점검",
            "text": f"{company_name}의 최근 공시 기준 부채/자산 비율이 {debt_ratio:.1f}%입니다. 금리와 경기 둔화에 민감한 포지션으로 관리하십시오.",
        })
    if op_margin is not None and op_margin < 5:
        flags.append({
            "type": "risk",
            "title": "마진 방어력 낮음",
            "text": f"{company_name}의 최근 공시 영업이익률이 {op_margin:.1f}%입니다. 매출 성장보다 이익률 회복 여부가 핵심입니다.",
        })
    elif op_margin is not None and op_margin > 15:
        flags.append({
            "type": "opportunity",
            "title": "수익성 우위",
            "text": f"{company_name}의 최근 공시 영업이익률이 {op_margin:.1f}%입니다. 조정 시 우량 수익성 포지션으로 분류할 수 있습니다.",
        })
    if not flags:
        flags.append({
            "type": "watch",
            "title": "공시 신호 제한",
            "text": f"{company_name}은 자동 추출된 배당/재무 신호가 제한적입니다. 현재가와 계좌 비중 중심으로 관리하십시오.",
        })
    return flags[:5]


def main():
    api_key = load_env(ENV).get("DART_API_KEY", "")
    if not api_key:
        raise SystemExit("DART_API_KEY is missing in .env")

    holdings = load_holdings()
    corp_by_stock = fetch_corp_codes(api_key)
    unique_codes = sorted({code for row in holdings for code in [stock_code_from_symbol(row)] if code})
    result = {"source": "OPENDART", "matched": 0, "unmatched": [], "companies": {}}

    for stock_code in unique_codes:
        corp = corp_by_stock.get(stock_code)
        if not corp:
            result["unmatched"].append(stock_code)
            continue
        result["matched"] += 1
        try:
            reports = fetch_recent_reports(api_key, corp["corp_code"])
            dividend_reports = pick_reports(reports, ("배당", "분배", "현금ㆍ현물배당", "현금·현물배당"))
            periodic_reports = pick_reports(reports, ("사업보고서", "반기보고서", "분기보고서"))
            financials = fetch_financial_snapshot(api_key, corp["corp_code"])
            report_analysis = fetch_report_analysis(api_key, periodic_reports)
            dividend_analysis = extract_dividend_analysis(api_key, dividend_reports)
        except Exception as exc:
            dividend_reports = [{"error": type(exc).__name__}]
            periodic_reports = []
            financials = {}
            report_analysis = {"error": type(exc).__name__, "signals": []}
            dividend_analysis = {"error": type(exc).__name__}
        result["companies"][stock_code] = {
            **corp,
            "recent_dividend_reports": dividend_reports,
            "recent_periodic_reports": periodic_reports,
            "financials": financials,
            "report_analysis": report_analysis,
            "dividend_analysis": dividend_analysis,
            "guide_flags": build_guide_flags(corp["corp_name"], dividend_reports, periodic_reports, financials, report_analysis, dividend_analysis),
        }

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    inject_dart_enrichment(result)
    print(json.dumps({"matched": result["matched"], "unmatched": len(result["unmatched"]), "output": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
