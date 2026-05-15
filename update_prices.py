import yfinance as yf
import json
from datetime import datetime, timezone, timedelta

TICKERS = [
    "000660.KS",  # SK하이닉스
    "005930.KS",  # 삼성전자
    "005380.KS",  # 현대차
    "010120.KS",  # LS ELECTRIC
    "042660.KS",  # 한화오션
    "189300.KQ",  # 인텔리안테크
    "298040.KS",  # 효성중공업
]

KST = timezone(timedelta(hours=9))
now_kst = datetime.now(KST)
timestamp = now_kst.strftime("%Y.%m.%d %H:%M KST")

prices = {}

for ticker in TICKERS:
    try:
        stock = yf.Ticker(ticker)
        info = stock.fast_info
        hist = stock.history(period="1y")

        price = round(info.last_price) if info.last_price else 0
        prev  = round(info.previous_close) if info.previous_close else price
        change = round(price - prev)
        pct = round((price - prev) / prev * 100, 2) if prev else 0
        w52h = round(hist['High'].max()) if not hist.empty else 0
        w52l = round(hist['Low'].min()) if not hist.empty else 0

        prices[ticker] = {
            "price": price,
            "change": change,
            "pct": pct,
            "w52h": w52h,
            "w52l": w52l
        }
        print(f"✅ {ticker}: {price:,}원 ({pct:+.1f}%)")
    except Exception as e:
        print(f"❌ {ticker}: {e}")
        prices[ticker] = {"price": 0, "change": 0, "pct": 0, "w52h": 0, "w52l": 0}

output = {"updated": timestamp, "prices": prices}

with open("prices.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n✅ prices.json 업데이트 완료: {timestamp}")
