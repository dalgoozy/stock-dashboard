import yfinance as yf
import smtplib, ssl, base64, os
from datetime import datetime, timezone, timedelta

HOLDINGS = [
    {"name": "SK하이닉스",   "ticker": "000660.KS", "avg": 551733,  "qty": 15},
    {"name": "삼성전자",      "ticker": "005930.KS", "avg": 172167,  "qty": 87},
    {"name": "현대차",        "ticker": "005380.KS", "avg": 504000,  "qty": 20},
    {"name": "LS ELECTRIC",  "ticker": "010120.KS", "avg": 288500,  "qty": 91},
    {"name": "한화오션",      "ticker": "042660.KS", "avg": 123200,  "qty": 240},
    {"name": "인텔리안테크",  "ticker": "189300.KQ", "avg": 138650,  "qty": 2},
    {"name": "효성중공업",    "ticker": "298040.KS", "avg": 4150000, "qty": 7},
]

WARN_PCT   = 999.0
DANGER_PCT = -15.0
GMAIL_ADDRESS  = os.environ.get("GMAIL_ADDRESS", "")
GMAIL_APP_PASS = os.environ.get("GMAIL_APP_PASSWORD", "")
TO_ADDRESS     = "hwandabears01@gmail.com"
KST = timezone(timedelta(hours=9))


def fetch_prices():
    results = []
    for h in HOLDINGS:
        try:
            info  = yf.Ticker(h["ticker"]).fast_info
            price = round(info.last_price) if info.last_price else 0
            pct   = round((price - h["avg"]) / h["avg"] * 100, 2) if h["avg"] else 0
            pnl   = round((price - h["avg"]) * h["qty"])
            results.append({**h, "price": price, "pct": pct, "pnl": pnl})
        except Exception as e:
            results.append({**h, "price": 0, "pct": 0, "pnl": 0})
    return results


def send_email(subject, html_body):
    print(f"DEBUG-1: subject = {repr(subject)}")

    try:
        html_b64 = base64.b64encode(html_body.encode("utf-8")).decode("ascii")
        print("DEBUG-2: html b64 ok")
    except Exception as e:
        print(f"DEBUG-2 FAIL: {e}")
        return False

    raw = "\r\n".join([
        f"From: {GMAIL_ADDRESS}",
        f"To: {TO_ADDRESS}",
        f"Subject: {subject}",
        "MIME-Version: 1.0",
        'Content-Type: text/html; charset=utf-8',
        "Content-Transfer-Encoding: base64",
        "",
        html_b64,
        "",
    ])
    print("DEBUG-3: raw built")

    try:
        raw_bytes = raw.encode("ascii")
        print("DEBUG-4: encode ascii ok")
    except Exception as e:
        print(f"DEBUG-4 FAIL at encode ascii: {e}")
        print(f"DEBUG-4 subject repr: {repr(subject)}")
        print(f"DEBUG-4 GMAIL_ADDRESS repr: {repr(GMAIL_ADDRESS)}")
        print(f"DEBUG-4 TO_ADDRESS repr: {repr(TO_ADDRESS)}")
        return False

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as server:
            print("DEBUG-5: connected")
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASS)
            print("DEBUG-6: logged in")
            server.sendmail(GMAIL_ADDRESS, TO_ADDRESS, raw_bytes)
            print(f"DEBUG-7: sent OK -> {TO_ADDRESS}")
        return True
    except Exception as e:
        print(f"DEBUG-5to7 FAIL: {e}")
        return False


def main():
    now_str = datetime.now(KST).strftime("%Y.%m.%d %H:%M KST")
    print(f"[START] {now_str}")

    all_stocks = fetch_prices()
    alerts = [s for s in all_stocks if s["pct"] <= WARN_PCT and s["price"] > 0]

    if not alerts:
        print("[OK] no alerts")
        return

    warn_cnt   = sum(1 for s in alerts if s["pct"] > DANGER_PCT)
    danger_cnt = len(alerts) - warn_cnt
    subject    = f"[Boss Stock] WARNING {warn_cnt} - {now_str}" if not danger_cnt else f"[Boss Stock] DANGER {danger_cnt} - {now_str}"

    html = f"<html><body><p>Boss Stock Alert {now_str}</p><p>{len(alerts)} stocks triggered.</p></body></html>"
    send_email(subject, html)
    print("[DONE]")

if __name__ == "__main__":
    main()
