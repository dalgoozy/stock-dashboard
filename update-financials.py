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
    """
    fnlttSinglIndx + idx_cl_code=M210000 (수익성지표)
    반환 필드: idx_nm, thstrm_val
    """
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
                print(f"  수익성 {year}/{reprt_code} ✓ 항목: {list(result.keys())}")
                return result
        except Exception as e:
            print(f"  [WARN] 수익성 {year}/{reprt_code}: {e}")
    return {}


# ── 3. 재무제표 전체 (EPS 추출) ────────────────────────────────
def get_eps_from_acnt(corp_code: str, year: int) -> float | None:
    """
    fnlttSinglAcntAll → '기본주당이익(손실)' 항목 추출
    fs_div: CFS=연결, OFS=별도 (연결 우선)
    """
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


# ── 5. 메인 ──────────────────────────────────────────────────
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
        print(f"  corp_code: {corp_code}")

        data = {"eps": None, "bps": None, "roe": None, "dps": None}
        found_year = None

        for year in [cur_year - 1, cur_year - 2]:
            prof = get_profitability(corp_code, year)
            eps  = get_eps_from_acnt(corp_code, year)
            time.sleep(0.3)  # API rate limit 방지

            if prof or eps is not None:
                found_year = year
                # ROE 파싱 (수익성 지표에서)
                # ROE 직접 추출
        roe_raw = prof.get('ROE') or prof.get('자기자본이익률')
        print(f"  ROE raw: {repr(roe_raw)}")
        data["roe"] = to_num(roe_raw)
        # 배당 지표
        data["dps"] = to_num(prof.get('주당배당금'))
                if eps is not None:
                    data["eps"] = eps
                break

        result["stocks"][sc] = data
        if found_year and result["report_year"] is None:
            result["report_year"] = str(found_year)

        print(f"  → EPS={data['eps']}  ROE={data['roe']}%")

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "financials.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n[DONE] {now_str}")


if __name__ == "__main__":
    main()
