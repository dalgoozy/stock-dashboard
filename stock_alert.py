"""
Boss 주식 스탑로스 이메일 알림 시스템
"""

import yfinance as yf
import smtplib
import ssl
from email.message import EmailMessage
import os
from datetime import datetime, timezone, timedelta

# ──────────────────────────────────────────
# 보유 종목
# ──────────────────────────────────────────
HOLDINGS = [
    {"name": "SK하이닉스",   "ticker": "000660.KS", "avg": 551733,  "qty": 15},
    {"name": "삼성전자",      "ticker": "005930.KS", "avg": 172167,  "qty": 87},
    {"name": "현대차",        "ticker": "005380.KS", "avg": 504000,  "qty": 20},
    {"name": "LS ELECTRIC",  "ticker": "010120.KS", "avg": 288500,  "qty": 91},
    {"name": "한화오션",      "ticker": "042660.KS", "avg": 123200,  "qty": 240},
    {"name": "인텔리안테크",  "ticker": "189300.KQ", "avg": 138650,  "qty": 2},
    {"name": "효성중공업",    "ticker": "298040.KS", "avg": 4150000, "qty": 7},
]

# ──────────────────────────────────────────
# 스탑로스 임계값
# ──────────────────────────────────────────
WARN_PCT   = 999.0   # 테스트용 (실제: -8.0)
DANGER_PCT = -15.0

# ──────────────────────────────────────────
# 이메일 설정
# ──────────────────────────────────────────
GMAIL_ADDRESS  = os.environ.get("GMAIL_ADDRESS", "")
GMAIL_APP_PASS = os.environ.get("GMAIL_APP_PASSWORD", "")
TO_ADDRESS     = "hwandabears01@gmail.com"

KST = timezone(timedelta(hours=9))


def fetch_prices():
    results = []
    for h in HOLDINGS:
        try:
            stock = yf.Ticker(h["ticker"])
            info  = stock.fast_info
            price = round(info.last_price) if info.last_price else 0
            pct   = round((price - h["avg"]) / h["avg"] * 100, 2) if h["avg"] else 0
            pnl   = round((price - h["avg"]) * h["qty"])
            results.append({**h, "price": price, "pct": pct, "pnl": pnl})
            emoji = "R" if pct <= DANGER_PCT else "W" if pct <= WARN_PCT else "OK"
            print(f"[{emoji}] {h['name']}: {price:,}원  평단대비 {pct:+.1f}%  손익 {pnl:+,.0f}원")
        except Exception as e:
            print(f"[ERR] {h['name']} 조회 실패: {e}")
            results.append({**h, "price": 0, "pct": 0, "pnl": 0})
    return results


def build_email_html(alerts, all_stocks, now_str):
    danger_list = [s for s in alerts if s["pct"] <= DANGER_PCT]
    warn_list   = [s for s in alerts if DANGER_PCT < s["pct"] <= WARN_PCT]

    def row_bg(pct):
        if pct <= DANGER_PCT: return "#2d1515"
        if pct <= WARN_PCT:   return "#2d2510"
        return "#0f1a0f"

    def pct_color(pct):
        if pct <= DANGER_PCT: return "#ef4444"
        if pct <= WARN_PCT:   return "#f59e0b"
        return "#10b981"

    rows = ""
    for s in all_stocks:
        if s["price"] == 0:
            continue
        rows += f"""
        <tr style="background:{row_bg(s['pct'])};">
          <td style="padding:10px 14px;border-bottom:1px solid #1f2937;font-weight:600;">{s['name']}</td>
          <td style="padding:10px 14px;border-bottom:1px solid #1f2937;text-align:right;">{s['price']:,}원</td>
          <td style="padding:10px 14px;border-bottom:1px solid #1f2937;text-align:right;">{s['avg']:,}원</td>
          <td style="padding:10px 14px;border-bottom:1px solid #1f2937;text-align:right;font-weight:700;color:{pct_color(s['pct'])};">{s['pct']:+.1f}%</td>
          <td style="padding:10px 14px;border-bottom:1px solid #1f2937;text-align:right;color:{pct_color(s['pct'])};">{s['pnl']:+,.0f}원</td>
        </tr>"""

    summary_lines = ""
    if danger_list:
        names = ", ".join(s["name"] for s in danger_list)
        summary_lines += f'<p style="color:#ef4444;font-size:1rem;margin:6px 0;">위험 (&le;-15%): <strong>{names}</strong></p>'
    if warn_list:
        names = ", ".join(s["name"] for s in warn_list)
        summary_lines += f'<p style="color:#f59e0b;font-size:1rem;margin:6px 0;">경고 (&le;-8%): <strong>{names}</strong></p>'

    return f"""<!DOCTYPE html>
<html>
<body style="background:#0a0e1a;color:#f9fafb;font-family:-apple-system,sans-serif;margin:0;padding:20px;">
  <div style="max-width:640px;margin:0 auto;">
    <h2 style="color:#3b82f6;margin-bottom:4px;">Boss 주식 스탑로스 알림</h2>
    <p style="color:#6b7280;font-size:0.85rem;margin-bottom:20px;">{now_str}</p>
    <div style="background:#111827;border-radius:10px;padding:16px;margin-bottom:20px;">{summary_lines}</div>
    <table style="width:100%;border-collapse:collapse;background:#111827;border-radius:10px;overflow:hidden;">
      <thead>
        <tr style="background:#1f2937;">
          <th style="padding:10px 14px;text-align:left;font-size:0.75rem;color:#6b7280;">종목</th>
          <th style="padding:10px 14px;text-align:right;font-size:0.75rem;color:#6b7280;">현재가</th>
          <th style="padding:10px 14px;text-align:right;font-size:0.75rem;color:#6b7280;">평단가</th>
          <th style="padding:10px 14px;text-align:right;font-size:0.75rem;color:#6b7280;">수익률</th>
          <th style="padding:10px 14px;text-align:right;font-size:0.75rem;color:#6b7280;">평가손익</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    <p style="color:#374151;font-size:0.72rem;margin-top:20px;text-align:center;">
      <a href="https://dalgoozy.github.io/stock-dashboard/" style="color:#3b82f6;">대시보드 열기</a>
    </p>
  </div>
</body>
</html>"""


def send_email(subject, html_body):
    if not GMAIL_ADDRESS or not GMAIL_APP_PASS:
        print("ERROR: 환경변수 없음 (GMAIL_ADDRESS / GMAIL_APP_PASSWORD)")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"]    = GMAIL_ADDRESS
    msg["To"]      = TO_ADDRESS
    msg.set_content("Boss Stock Alert - Please view in HTML email client")
    msg.add_alternative(html_body, subtype="html")

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASS)
            server.send_message(msg)
        print(f"OK: 이메일 발송 완료 -> {TO_ADDRESS}")
        return True
    except Exception as e:
        print(f"ERROR: 이메일 발송 실패: {e}")
        return False


def main():
    now_kst = datetime.now(KST)
    now_str = now_kst.strftime("%Y.%m.%d %H:%M KST")
    print(f"\n[START] 스탑로스 점검 시작 - {now_str}\n")

    all_stocks = fetch_prices()
    alerts = [s for s in all_stocks if s["pct"] <= WARN_PCT and s["price"] > 0]

    if not alerts:
        print("\n[OK] 스탑로스 발동 종목 없음. 이메일 발송 안 함.")
        return

    danger_cnt = sum(1 for s in alerts if s["pct"] <= DANGER_PCT)
    warn_cnt   = len(alerts) - danger_cnt

    if danger_cnt:
        subject = f"[Boss Stock] DANGER Stop-Loss {danger_cnt} stocks - {now_str}"
    else:
        subject = f"[Boss Stock] WARNING Stop-Loss {warn_cnt} stocks - {now_str}"

    html = build_email_html(alerts, all_stocks, now_str)
    send_email(subject, html)
    print(f"\n[DONE] 알림 대상: {[s['name'] for s in alerts]}")


if __name__ == "__main__":
    main()
