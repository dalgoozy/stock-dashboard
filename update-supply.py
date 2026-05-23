"""
update-supply.py
외국인 / 기관 5일 순매수 데이터 수집 → supply.json 저장
pykrx 사용 (KRX 공식 데이터, API 키 불필요)
"""
from pykrx import stock as krx
import json
from datetime import datetime, timezone, timedelta
import time

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
today = now.strftime("%Y%m%d")
from_d = (now - timedelta(days=14)).strftime("%Y%m%d")  # 14일치 → 5 거래일 확보

result = {}

for ticker, name in STOCKS.items():
    try:
        # 투자자별 순매수 거래대금 (단위: 원)
        df = krx.get_market_trading_value_by_date(from_d, today, ticker)

        if df is None or df.empty:
            print(f"⚠️  {name}: 데이터 없음")
            result[ticker] = {"name": name, "foreign_5d": 0, "institution_5d": 0, "days": []}
            continue

        # 컬럼명 확인 (디버그)
        print(f"  [{name}] 컬럼: {list(df.columns)}")

        df5 = df.tail(5)
        days = []
        foreign_total = 0
        institution_total = 0

        for idx, row in df5.iterrows():
            date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
            row_d = row.to_dict()

            foreign_net = 0
            institution_net = 0

            for col, val in row_d.items():
                cs = str(col)
                try:
                    v = int(val) if val == val else 0
                except Exception:
                    v = 0
                # pykrx 컬럼: "외국인합계" (기타외국인 제외), "기관합계"
                if cs == "외국인합계":
                    foreign_net = v
                elif cs == "기관합계":
                    institution_net = v
                # 혹시 "순" 포함 버전도 대응
                elif "외국인" in cs and "순" in cs and "기타" not in cs:
                    foreign_net = v
                elif "기관" in cs and "순" in cs and "외국인" not in cs:
                    institution_net = v

            foreign_total += foreign_net
            institution_total += institution_net
            days.append({"date": date_str, "foreign": foreign_net, "institution": institution_net})

        result[ticker] = {
            "name": name,
            "foreign_5d": foreign_total,
            "institution_5d": institution_total,
            "days": days,
        }
        sign_f = "+" if foreign_total >= 0 else ""
        sign_i = "+" if institution_total >= 0 else ""
        print(f"✅ {name:12s}: 외국인 {sign_f}{foreign_total/1e8:,.1f}억  기관 {sign_i}{institution_total/1e8:,.1f}억")
        time.sleep(0.5)

    except Exception as e:
        print(f"❌ {name}: {e}")
        result[ticker] = {"name": name, "foreign_5d": 0, "institution_5d": 0, "days": [], "error": str(e)}

output = {"updated": now.strftime("%Y.%m.%d %H:%M KST"), "stocks": result}

with open("supply.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n✅ supply.json 저장 완료 — {now.strftime('%Y.%m.%d %H:%M KST')}")
