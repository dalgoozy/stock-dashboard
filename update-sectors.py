"""
update-sectors.py
섹터별 대표 종목 현재가 / 등락률 / 52주 위치를 수집해 sectors.json으로 저장.
GitHub Actions 에서 매일 장 마감 후 실행.
"""
import yfinance as yf
import json, os
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

SECTORS = [
    {
        "id": "power",
        "stocks": [
            {"name": "효성중공업",     "ticker": "298040.KS"},
            {"name": "LS ELECTRIC",   "ticker": "010120.KS"},
            {"name": "HD현대일렉트릭", "ticker": "267260.KS"},
            {"name": "일진전기",       "ticker": "103590.KS"},
        ]
    },
    {
        "id": "shipbuilding",
        "stocks": [
            {"name": "한화오션",       "ticker": "042660.KS"},
            {"name": "HD한국조선해양", "ticker": "009540.KS"},
            {"name": "삼성중공업",     "ticker": "010140.KS"},
        ]
    },
    {
        "id": "defense",
        "stocks": [
            {"name": "한화에어로스페이스", "ticker": "012450.KS"},
            {"name": "LIG넥스원",          "ticker": "079550.KS"},
            {"name": "현대로템",            "ticker": "064350.KS"},
            {"name": "한국항공우주",        "ticker": "047810.KS"},
        ]
    },
    {
        "id": "semiconductor",
        "stocks": [
            {"name": "SK하이닉스", "ticker": "000660.KS"},
            {"name": "삼성전자",   "ticker": "005930.KS"},
            {"name": "한미반도체", "ticker": "042700.KS"},
        ]
    },
    {
        "id": "chemical",
        "stocks": [
            {"name": "LG화학",       "ticker": "051910.KS"},
            {"name": "SK이노베이션", "ticker": "096770.KS"},
            {"name": "롯데케미칼",   "ticker": "011170.KS"},
        ]
    },
    {
        "id": "auto",
        "stocks": [
            {"name": "현대차",    "ticker": "005380.KS"},
            {"name": "기아",      "ticker": "000270.KS"},
            {"name": "현대모비스","ticker": "012330.KS"},
        ]
    },
]


def fetch_stock(ticker):
    try:
        info  = yf.Ticker(ticker).fast_info
        price = round(info.last_price)       if getattr(info, "last_price", None)          else None
        prev  = round(info.previous_close)   if getattr(info, "previous_close", None)      else None
        w52h  = round(info.fifty_two_week_high) if getattr(info, "fifty_two_week_high", None) else None
        w52l  = round(info.fifty_two_week_low)  if getattr(info, "fifty_two_week_low",  None) else None

        pct   = round((price - prev) / prev * 100, 2) if price and prev else None
        pos52 = None
        if price and w52h and w52l and w52h != w52l:
            pos52 = round((price - w52l) / (w52h - w52l) * 100)
            pos52 = max(0, min(100, pos52))

        return {"price": price, "prev": prev, "pct": pct, "w52h": w52h, "w52l": w52l, "pos52": pos52}
    except Exception as e:
        print(f"  [ERR] {ticker}: {e}")
        return {"price": None, "prev": None, "pct": None, "w52h": None, "w52l": None, "pos52": None}


def main():
    now_str = datetime.now(KST).strftime("%Y.%m.%d %H:%M KST")
    result  = {"updated": now_str, "sectors": {}}

    for sector in SECTORS:
        sid    = sector["id"]
        stocks = []
        pcts   = []

        for st in sector["stocks"]:
            print(f"[{sid}] {st['name']} ({st['ticker']})")
            d = fetch_stock(st["ticker"])
            entry = {
                "name":   st["name"],
                "ticker": st["ticker"],
                "price":  d["price"],
                "pct":    d["pct"],
                "pos52":  d["pos52"],
                "w52h":   d["w52h"],
                "w52l":   d["w52l"],
            }
            stocks.append(entry)
            if d["pct"] is not None:
                pcts.append(d["pct"])

        avg_pct = round(sum(pcts) / len(pcts), 2) if pcts else None
        result["sectors"][sid] = {"avg_pct": avg_pct, "stocks": stocks}
        print(f"  → avg_pct={avg_pct}")

    out_path = os.path.join(os.path.dirname(__file__), "sectors.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n[DONE] sectors.json 저장 완료 — {now_str}")


if __name__ == "__main__":
    main()
