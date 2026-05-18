"""
update-financials.py
DART OpenAPI → EPS, BPS, ROE 수집
PER / PBR 는 실시간 주가 / EPS / BPS 로 계산해서 financials.json 에 저장.
GitHub Actions: 매월 1일 실행 (분기 공시 이후 자동 반영).
"""
import requests, json, os
from datetime import datetime, timezone, timedelta

KST      = timezone(timedelta(hours=9))
DART_KEY = os.environ.get("DART_API_KEY", "")

# 주식코드 (티커에서 .KS/.KQ 제거)
HOLDINGS = [
    {"name": "SK하이닉스",   "stock_code": "000660"},
    {"name": "삼성전자",      "stock_code": "005930"},
    {"name": "현대차",        "stock_code": "005380"},
    {"name": "LS ELECTRIC",  "stock_code": "010120"},
    {"name": "한화오션",      "stock_code": "042660"},
    {"name": "인텔리안테크",  "stock_code": "189300"},
    {"name": "효성중공업",    "stock_code": "298040"},
]

BASE = "https://opendart.fss.or.kr/api"


# ── 1. 종목코드 → corp_code 변환 ──────────────────────────────
def get_corp_code(stock_code: str) -> str | None:
    try:
        r = requests.get(f"{BASE}/company.json",
            params={"crtfc_key": DART_KEY, "stock_code": stock_code},
            timeout=10)
        d = r.json()
        if d.get("status") == "000":
            return d.get("corp_code")
    except Exception as e:
        print(f"  [ERR] corp_code 조회 실패 ({stock_code}): {e}")
    return None


# ── 2. 주요재무정보 조회 ──────────────────────────────────────
def get_fnltt_indx(corp_code: str, year: int) -> list:
    """
    reprt_code:
      11011 = 사업보고서 (12월 결산 기준 연간)
      11014 = 3분기보고서
      11012 = 반기보고서
    최신 공시부터 순서대로 시도.
    """
    for reprt_code in ["11011", "11014", "11012"]:
        try:
            r = requests.get(f"{BASE}/fnlttSinglIndx.json",
                params={"crtfc_key": DART_KEY, "corp_code": corp_code,
                        "bsns_year": str(year), "reprt_code": reprt_code},
                timeout=10)
            d = r.json()
            if d.get("status") == "000" and d.get("list"):
                print(f"  → {year}년 reprt_code={reprt_code} 데이터 확인")
                return d["list"]
        except Exception as e:
            print(f"  [WARN] {year}/{reprt_code}: {e}")
    return []


# ── 3. 숫자 파싱 ──────────────────────────────────────────────
def to_num(val) -> float | None:
    if val is None or str(val).strip() in ["-", "", "N/A"]:
        return None
    try:
        return float(str(val).replace(",", "").strip())
    except ValueError:
        return None


# ── 4. 계정명 → EPS / BPS / ROE / DPS 추출 ──────────────────
def parse_indx(items: list) -> dict:
    data = {}
    for item in items:
        nm  = item.get("account_nm", "")
        val = to_num(item.get("thstrm_amount"))
        if val is None:
            continue

        nm_up = nm.upper()
        if "주당순이익" in nm or "EPS" in nm_up:
            data.setdefault("eps", val)
        elif "주당순자산" in nm or "BPS" in nm_up:
            data.setdefault("bps", val)
        elif "자기자본이익률" in nm or "ROE" in nm_up:
            data.setdefault("roe", val)
        elif "주당배당금" in nm or "DPS" in nm_up:
            data.setdefault("dps", val)
        elif "부채비율" in nm:
            data.setdefault("debt_ratio", val)
        elif "영업이익률" in nm:
            data.setdefault("op_margin", val)
    return data


# ── 5. 메인 ──────────────────────────────────────────────────
def main():
    if not DART_KEY:
        print("[ERROR] DART_API_KEY 환경변수가 없습니다.")
        return

    now      = datetime.now(KST)
    now_str  = now.strftime("%Y.%m.%d %H:%M KST")
    cur_year = now.year
    result   = {"updated": now_str, "report_year": None, "stocks": {}}

    for h in HOLDINGS:
        sc = h["stock_code"]
        print(f"\n▶ {h['name']} ({sc})")

        corp_code = get_corp_code(sc)
        if not corp_code:
            print("  → corp_code 조회 실패, 스킵")
            continue
        print(f"  corp_code: {corp_code}")

        # 가장 최근 연도부터 2년 전까지 시도
        items = []
        found_year = None
        for year in [cur_year - 1, cur_year - 2]:
            items = get_fnltt_indx(corp_code, year)
            if items:
                found_year = year
                break

        if not items:
            print("  → 재무데이터 없음, 스킵")
            continue

        if result["report_year"] is None:
            result["report_year"] = str(found_year)

        parsed = parse_indx(items)
        result["stocks"][sc] = parsed
        print(f"  EPS={parsed.get('eps')}  BPS={parsed.get('bps')}  ROE={parsed.get('roe')}%  DPS={parsed.get('dps')}")

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "financials.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n[DONE] financials.json 저장 완료 — {now_str}")


if __name__ == "__main__":
    main()
