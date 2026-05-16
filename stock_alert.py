import yfinance as yf
import subprocess, tempfile, base64, os
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
            tag = "R" if pct <= DANGER_PCT else "W" if pct <= WARN_PCT else "OK"
            print(f"[{tag}] {h['name']}: {price:,}  {pct:+.1f}%")
        except Exception as e:
            results.append({**h, "price": 0, "pct": 0, "pnl": 0})
    return results


def build_html(all_stocks, now_str):
    def bg(pct):
        return "#2d1515" if pct <= DANGER_PCT else "#2d2510" if pct <= WARN_PCT else "#0f1a0f"
    def fc(pct):
        return "#ef4444" if pct <= DANGER_PCT else "#f59e0b" if pct <= WARN_PCT else "#10b981"

    rows = "".join(
        f'<tr style="background:{bg(s["pct"])}">'
        f'<td style="padding:10px;border-bottom:1px solid #1f2937">{s["name"]}</td>'
        f'<td style="padding:10px;border-bottom:1px solid #1f2937;text-align:right">{s["price"]:,}원</td>'
        f'<td style="padding:10px;border-bottom:1px solid #1f2937;text-align:right">{s["avg"]:,}원</td>'
        f'<td style="padding:10px;border-bottom:1px solid #1f2937;text-align:right;color:{fc(s["pct"])}">{s["pct"]:+.1f}%</td>'
        f'<td style="padding:10px;border-bottom:1px solid #1f2937;text-align:right;color:{fc(s["pct"])}">{s["pnl"]:+,.0f}원</td>'
        f'</tr>'
        for s in all_stocks if s["price"] > 0
    )
    return (
        f'<html><body style="background:#0a0e1a;color:#f9fafb;font-family:sans-serif;padding:20px">'
        f'<div style="max-width:640px;margin:0 auto">'
        f'<h2 style="color:#3b82f6">Boss 주식 스탑로스 알림</h2>'
        f'<p style="color:#6b7280">{now_str}</p>'
        f'<table style="width:100%;border-collapse:collapse;background:#111827">'
        f'<tr style="background:#1f2937">'
        f'<th style="padding:10px;text-align:left;color:#6b7280">종목</th>'
        f'<th style="padding:10px;text-align:right;color:#6b7280">현재가</th>'
        f'<th style="padding:10px;text-align:right;color:#6b7280">평단가</th>'
        f'<th style="padding:10px;text-align:right;color:#6b7280">수익률</th>'
        f'<th style="padding:10px;text-align:right;color:#6b7280">평가손익</th>'
        f'</tr>{rows}</table>'
        f'<p style="margin-top:20px;text-align:center">'
        f'<a href="https://dalgoozy.github.io/stock-dashboard/" style="color:#3b82f6">대시보드 열기</a>'
        f'</p></div></body></html>'
    )


def send_email(subject, html_body):
    html_b64 = base64.b64encode(html_body.encode("utf-8")).decode("ascii")
    eml = (
        f"From: {GMAIL_ADDRESS}\r\n"
        f"To: {TO_ADDRESS}\r\n"
        f"Subject: {subject}\r\n"
        f"MIME-Version: 1.0\r\n"
        f"Content-Type: text/html; charset=utf-8\r\n"
        f"Content-Transfer-Encoding: base64\r\n"
        f"\r\n"
        f"{html_b64}\r\n"
    )
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".eml", delete=False) as f:
        f.write(eml.encode("ascii"))
        tmpfile = f.name

    cmd = [
        "curl", "--ssl-reqd",
        "--url", "smtps://smtp.gmail.com:465",
        "--user", f"{GMAIL_ADDRESS}:{GMAIL_APP_PASS}",
        "--mail-from", GMAIL_ADDRESS,
        "--mail-rcpt", TO_ADDRESS,
        "--upload-file", tmpfile,
        "-s", "--stderr", "-"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    os.unlink(tmpfile)

    if result.returncode == 0:
        print(f"OK: sent -> {TO_ADDRESS}")
        return True
    else:
        print(f"ERROR: curl exit {result.returncode}")
        print(result.stdout[:300])
        print(result.stderr[:300])
        return False


def main():
    now_str = datetime.now(KST).strftime("%Y.%m.%d %H:%M KST")
    print(f"[START] {now_str}")
    all_stocks = fetch_prices()
    alerts = [s for s in all_stocks if s["pct"] <= WARN_PCT and s["price"] > 0]
    if not alerts:
        print("[OK] no alerts")
        return
    danger_cnt = sum(1 for s in alerts if s["pct"] <= DANGER_PCT)
    warn_cnt   = len(alerts) - danger_cnt
    subject = (f"[Boss Stock] DANGER {danger_cnt} stocks - {now_str}" if danger_cnt
               else f"[Boss Stock] WARNING {warn_cnt} stocks - {now_str}")
    html = build_html(all_stocks, now_str)
    send_email(subject, html)
    print(f"[DONE]")

if __name__ == "__main__":
    main()
