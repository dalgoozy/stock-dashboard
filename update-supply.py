"""
update-supply.py
외국인 / 기관 5일 순매매 데이터 수집 → supply.json 저장
NAVER Finance 파싱 사용 (인증 불필요)
단위: 주 (순매매량)
"""
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timezone, timedelta
import time
import re

STOCKS = {
    "000660": "SK하이닉스",
    "005930": "삼성전자",
    "005380": "현대차",
    "010120": "LS ELECTRIC",
    "042660": "한화오션",
    "189300": "인텔리안테크",
    "298040": "효성중공업",
}

KST = timezone(timedelta(hours=9))
now = datetime.now(KST)

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

def parse_num(s):
    """'+1,234,567' 또는 '-307,631' → 정수"""
    s = s.replace(",", "").replace("+", "").strip()
    try:
        return int(s)
    except:
        return 0

def fetch_supply(ticker):
    url = f"https://finance.naver.com/item/frgn.naver?code={ticker}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.encoding = "euc-kr"
    soup = BeautifulSoup(r.text, "html.parser")

    # 외국인/기관 순매매 테이블 찾기
    target_table = None
    for t in soup.find_all("table"):
        cap = t.find("caption")
        if cap and "외국인" in cap.get_text() and "기관" in cap.get_text():
            target_table = t
            break

    if not target_table:
        return None

    rows = target_table.find_all("tr")
    data_rows = []
    for row in rows:
        tds = row.find_all("td")
        if len(tds) >= 7:
            date_txt = tds[0].get_text(strip=True)
            if re.match(r"\d{4}\.\d{2}\.\d{2}", date_txt):
                data_rows.append(tds)

    days = []
    institution_total = 0
    foreign_total = 0

    for tds in data_rows[:5]:
        date_str = tds[0].get_text(strip=True).replace(".", "-")
        inst_net = parse_num(tds[5].get_text(strip=True))   # 기관 순매매량
        fgn_net = parse_num(tds[6].get_text(strip=True))    # 외국인 순매매량
        institution_total += inst_net
        foreign_total += fgn_net
        days.append({"date": date_str, "foreign": fgn_net, "institution": inst_net})

    return {
        "foreign_5d": foreign_total,
        "institution_5d": institution_total,
        "days": days,
    }

result = {}

for ticker, name in STOCKS.items():
    try:
        data = fetch_supply(ticker)
        if not data or not data["days"]:
            print(f"⚠️  {name}: 데이터 없음")
            result[ticker] = {"name": name, "foreign_5d": 0, "institution_5d": 0, "days": []}
            continue

        result[ticker] = {"name": name, **data}
        fv, iv = data["foreign_5d"], data["institution_5d"]
        sf = "+" if fv >= 0 else ""
        si = "+" if iv >= 0 else ""
        print(f"✅ {name:12s}: 외국인 {sf}{fv:,}주  기관 {si}{iv:,}주")
        time.sleep(0.3)

    except Exception as e:
        print(f"❌ {name}: {e}")
        result[ticker] = {"name": name, "foreign_5d": 0, "institution_5d": 0, "days": [], "error": str(e)}

output = {"updated": now.strftime("%Y.%m.%d %H:%M KST"), "unit": "shares", "stocks": result}

with open("supply.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n✅ supply.json 저장 완료 — {now.strftime('%Y.%m.%d %H:%M KST')}")
