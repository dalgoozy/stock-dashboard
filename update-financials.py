"""
update-financials.py
DART OpenAPI → 재무 지표 수집 → financials.json 저장

사용 API:
  1. corpCode.xml  → 종목코드-corp_code 매핑 (ZIP 다운로드)
  2. fnlttSinglIndx → 수익성지표(ROE 등)  ← idx_cl_code 필수
  3. fnlttSinglAcntAll → 재무제표 전체    ← EPS(기본주당이익) 추출
"""
import requests, json, os, io, zipfile, time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

KST      = timezone(timedelta(hours=9))
DART_KEY = os.environ.get("DART_API_KEY", "")

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


# ── 1. 전체 기업코드 ZIP 다운로드 ──────────────────────────────
def build_corp_map() -> dict:
    print("[INFO] DART 기업코드 파일 다운로드 중...")
    r = requests.get(f"{BASE}/corpCode.xml",
        params={"crtfc_key": DART_KEY}, timeout=60)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        xml_bytes = zf.read(zf.namelist()[0])
    root = ET.fromstring(xml_bytes)
    corp_map = {}
    for item in root.findall("list"):
        sc = (item.findtext("stock_code") or "").strip()
        cc = (item.findtext("corp_code")  or "").strip()
        if sc and cc:
            corp_map[sc] = cc
    print(f"[INFO] {len(corp_map):,}개 기업코드 로드 완료")
    return corp_map


# ── 2. 수익성 지표 (ROE 등) ────────────────────────────────────
def get_profitability(corp_code: str, year: int) -> dict:
    for reprt_code in ["11011", "11014", "11012"]:
        try:
            r = requests.get(f"{BASE}/fnlttSinglIndx.json",
                params={"crtfc_key": DART_KEY, "corp_code": corp_code,
                        "bsns_year": str(year), "reprt_code": reprt_code,
                        "idx_cl_code": "M210000"},
                timeout=15)
            d = r.json()
            if d.get("status") == "000" and d.get("list"):
                result = {}
                for item in d["list"]:
                    nm  = item.get("idx_nm", "")
                    val = item.get("thstrm_val", "")
                    result[nm] = val
                print(f"  수익성 {year}/{reprt_code} ✓ ({len(result)}개 항목)")
                return result
        except Exception as e:
            print(f"  [WARN] 수익성 {year}/{reprt_code}: {e}")
    return {}


# ── 3. 재무제표 전체 (EPS 추출) ────────────────────────────────
def get_eps_from_acnt(corp_code: str, year: int) -> float | None:
    for fs_div in ["CFS", "OFS"]:
        for reprt_code in ["11011", "11014", "11012"]:
            try:
                r = requests.get(f"{BASE}/fnlttSinglAcntAll.json",
                    params={"crtfc_key": DART_KEY, "corp_code": corp_code,
                            "bsns_year": str(year), "reprt_code": reprt_code,
                            "fs_div": fs_div},
                    timeout=15)
                d = r.json()
                if d.get("status") != "000" or not d.get("list"):
                    continue
                for item in d["list"]:
                    nm = item.get("account_nm", "")
                    if "기본주당이익" in nm or "기본주당순이익" in nm:
                        val = item.get("thstrm_amount", "")
                        parsed = to_num(val)
                        if parsed is not None:
                            print(f"  EPS {year}/{reprt_code}/{fs_div} → {parsed}")
                            return parsed
            except Exception as e:
                print(f"  [WARN] EPS {year}/{reprt_code}/{fs_div}: {e}")
    return None


# ── 4. 숫자 파싱 ──────────────────────────────────────────────
def to_num(val) -> float | None:
    if val is None or str(val).strip() in ["-", "", "N/A"]:
        return None
    try:
        return float(str(val).replace(",", "").strip())
    except ValueError:
        return None


# ── 5. EPS 성장률 + PEG 계산 ─────────────────────────────────
def calc_eps_growth(eps_cur, eps_prev):
    """EPS 성장률(%) 계산. 전년도 EPS가 음수/0이면 None 반환"""
    if eps_cur is None or eps_prev is None:
        return None
    if eps_prev <= 0:
        return None
    return round((eps_cur - eps_prev) / abs(eps_prev) * 100, 1)

def calc_peg(per, eps_growth):
    """PEG = PER / EPS성장률. 성장률이 0 이하면 None"""
    if per is None or eps_growth is None or eps_growth <= 0:
        return None
    return round(per / eps_growth, 2)


# ── 6. 메인 ──────────────────────────────────────────────────
def main():
    if not DART_KEY:
        print("[ERROR] DART_API_KEY 없음")
        return

    now_str  = datetime.now(KST).strftime("%Y.%m.%d %H:%M KST")
    cur_year = datetime.now(KST).year
    result   = {"updated": now_str, "report_year": None, "stocks": {}}

    corp_map = build_corp_map()
    if not corp_map:
        print("[ERROR] 기업코드 로드 실패")
        return

    for h in HOLDINGS:
        sc = h["stock_code"]
        print(f"\n▶ {h['name']} ({sc})")

        corp_code = corp_map.get(sc)
        if not corp_code:
            print(f"  corp_code 없음")
            continue

        data = {"eps": None, "eps_prev": None, "eps_growth": None,
                "bps": None, "roe": None, "dps": None}
        found_year = None

        for year in [cur_year - 1, cur_year - 2]:
            prof = get_profitability(corp_code, year)
            eps  = get_eps_from_acnt(corp_code, year)
            time.sleep(0.3)

            if prof or eps is not None:
                found_year = year
                data["roe"] = to_num(prof.get("ROE"))
                data["dps"] = to_num(prof.get("주당배당금"))
                if eps is not None:
                    data["eps"] = eps

                # 전년도 EPS 추가 조회 (성장률 계산용)
                eps_prev = get_eps_from_acnt(corp_code, year - 1)
                time.sleep(0.3)
                data["eps_prev"] = eps_prev
                data["eps_growth"] = calc_eps_growth(eps, eps_prev)
                break

        result["stocks"][sc] = data
        if found_year and result["report_year"] is None:
            result["report_year"] = str(found_year)

        g = data['eps_growth']
        print(f"  → EPS={data['eps']}  EPS전년={data['eps_prev']}  성장률={g}%  ROE={data['roe']}%")

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "financials.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n[DONE] {now_str}")


if __name__ == "__main__":
    main()
