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

# 3단계 손절 기준
STAGE1_PCT = -15.0   # 52주 최고가 대비 -15% → 추세 꺾임
STAGE2_PCT = -15.0   # 평단가 대비 -15%       → 실제 손실
# 3단계: 52주 최저가 이탈 (숫자 기준 없음, price < w52l 로 판단)

GMAIL_ADDRESS  = os.environ.get("GMAIL_ADDRESS", "")
GMAIL_APP_PASS = os.environ.get("GMAIL_APP_PASSWORD", "")
TO_ADDRESS     = "hwandabears01@gmail.com"
KST = timezone(timedelta(hours=9))


def check_stages(price, avg, w52h, w52l):
    """
    Returns list of triggered stages (1, 2, 3).
    Stage 1: 52주 최고가 대비 -15% 이하
    Stage 2: 평단가 대비 -15% 이하
    Stage 3: 52주 최저가 이탈
    """
    stages = []
    if w52h and w52h > 0:
        pct_from_high = (price - w52h) / w52h * 100
        if pct_from_high <= STAGE1_PCT:
            stages.append(1)
    if avg and avg > 0:
        pct_from_avg = (price - avg) / avg * 100
        if pct_from_avg <= STAGE2_PCT:
            stages.append(2)
    if w52l and w52l > 0:
        if price < w52l:
            stages.append(3)
    return stages


def fetch_prices():
    results = []
    for h in HOLDINGS:
        try:
            info  = yf.Ticker(h["ticker"]).fast_info
            price = round(info.last_price) if info.last_price else 0
            w52h  = round(info.fifty_two_week_high)  if getattr(info, "fifty_two_week_high", None)  else 0
            w52l  = round(info.fifty_two_week_low)   if getattr(info, "fifty_two_week_low",  None)  else 0
            pct_avg  = round((price - h["avg"]) / h["avg"] * 100, 2) if h["avg"] and price else 0
            pct_high = round((price - w52h) / w52h * 100, 2)         if w52h and price      else 0
            pnl      = round((price - h["avg"]) * h["qty"])

            stages = check_stages(price, h["avg"], w52h, w52l) if price else []
            max_stage = max(stages) if stages else 0

            tag = "🚨3" if max_stage == 3 else "🔴2" if max_stage == 2 else "⚠️1" if max_stage == 1 else "OK"
            print(f"[{tag}] {h['name']}: {price:,}  평단{pct_avg:+.1f}%  52고{pct_high:+.1f}%  52저:{w52l:,}")

            results.append({
                **h,
                "price": price, "pct_avg": pct_avg, "pnl": pnl,
                "w52h": w52h, "w52l": w52l, "pct_high": pct_high,
                "stages": stages, "max_stage": max_stage,
            })
        except Exception as e:
            print(f"[ERR] {h['name']}: {e}")
            results.append({
                **h,
                "price": 0, "pct_avg": 0, "pnl": 0,
                "w52h": 0, "w52l": 0, "pct_high": 0,
                "stages": [], "max_stage": 0,
            })
    return results


def stage_label(stages):
    labels = []
    if 3 in stages:
        labels.append("3단계:52주최저 이탈")
    if 2 in stages:
        labels.append("2단계:평단-15%")
    if 1 in stages:
        labels.append("1단계:52고-15%")
    return " / ".join(labels) if labels else ""


def build_html(all_stocks, now_str):
    def row_bg(max_stage):
        return {3: "#2d1515", 2: "#2d1a10", 1: "#2d2510"}.get(max_stage, "#0f1a0f")

    def stage_color(max_stage):
        return {3: "#ef4444", 2: "#f97316", 1: "#f59e0b"}.get(max_stage, "#10b981")

    def stage_icon(max_stage):
        return {3: "🚨", 2: "🔴", 1: "⚠️"}.get(max_stage, "✅")

    rows = ""
    for s in all_stocks:
        if s["price"] == 0:
            continue
        bg    = row_bg(s["max_stage"])
        color = stage_color(s["max_stage"])
        icon  = stage_icon(s["max_stage"])
        lbl   = stage_label(s["stages"])
        stage_cell = f'<span style="color:{color};font-size:12px">{icon} {lbl}</span>' if lbl else '<span style="color:#10b981">정상</span>'
        rows += (
            f'<tr style="background:{bg}">'
            f'<td style="padding:10px;border-bottom:1px solid #1f2937">{s["name"]}</td>'
            f'<td style="padding:10px;border-bottom:1px solid #1f2937;text-align:right">{s["price"]:,}원</td>'
            f'<td style="padding:10px;border-bottom:1px solid #1f2937;text-align:right">{s["avg"]:,}원</td>'
            f'<td style="padding:10px;border-bottom:1px solid #1f2937;text-align:right;color:{color}">{s["pct_avg"]:+.1f}%</td>'
            f'<td style="padding:10px;border-bottom:1px solid #1f2937;text-align:right;color:{color}">{s["pnl"]:+,.0f}원</td>'
            f'<td style="padding:10px;border-bottom:1px solid #1f2937;font-size:12px">{stage_cell}</td>'
            f'</tr>'
        )

    # 범례
    legend = (
        '<div style="margin-top:16px;padding:12px;background:#111827;border-radius:8px;font-size:12px;color:#9ca3af">'
        '<b style="color:#f9fafb">손절 3단계 기준</b><br>'
        '⚠️ 1단계: 52주 최고가 대비 -15% 이하 — 추세 꺾임, 매수 이유 재검토<br>'
        '🔴 2단계: 평단가 대비 -15% 이하 — 실제 손실, 절반 매도 검토<br>'
        '🚨 3단계: 52주 최저가 이탈 — 추세 붕괴, 전량 매도 검토'
        '</div>'
    )

    return (
        f'<html><body style="background:#0a0e1a;color:#f9fafb;font-family:sans-serif;padding:20px">'
        f'<div style="max-width:720px;margin:0 auto">'
        f'<h2 style="color:#3b82f6">Boss 주식 손절 알림</h2>'
        f'<p style="color:#6b7280">{now_str}</p>'
        f'<table style="width:100%;border-collapse:collapse;background:#111827">'
        f'<tr style="background:#1f2937">'
        f'<th style="padding:10px;text-align:left;color:#6b7280">종목</th>'
        f'<th style="padding:10px;text-align:right;color:#6b7280">현재가</th>'
        f'<th style="padding:10px;text-align:right;color:#6b7280">평단가</th>'
        f'<th style="padding:10px;text-align:right;color:#6b7280">평단대비</th>'
        f'<th style="padding:10px;text-align:right;color:#6b7280">평가손익</th>'
        f'<th style="padding:10px;text-align:left;color:#6b7280">단계</th>'
        f'</tr>{rows}</table>'
        f'{legend}'
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
    now     = datetime.now(KST)
    now_str = now.strftime("%Y.%m.%d %H:%M KST")
    is_final    = (now.hour >= 14)
    alert_tag   = "🚨 최종경고 — 마감 30분 전 대응 가능" if is_final else "⚠️ 주의 — 오후 3시 재확인 필요"
    subject_tag = "최종경고" if is_final else "주의"

    print(f"[START] {now_str}  ({'최종경고' if is_final else '주의'} 타임슬롯)")
    all_stocks = fetch_prices()

    alerts = [s for s in all_stocks if s["max_stage"] > 0 and s["price"] > 0]
    if not alerts:
        print("[OK] no alerts — 모든 종목 정상")
        return

    # 가장 높은 단계 기준으로 제목 결정
    max_stage_overall = max(s["max_stage"] for s in alerts)
    stage3_cnt = sum(1 for s in alerts if s["max_stage"] == 3)
    stage2_cnt = sum(1 for s in alerts if s["max_stage"] == 2)
    stage1_cnt = sum(1 for s in alerts if s["max_stage"] == 1)

    if max_stage_overall == 3:
        subject = f"[Boss Stock] {subject_tag} 🚨3단계(추세붕괴) {stage3_cnt}종목 - {now_str}"
    elif max_stage_overall == 2:
        subject = f"[Boss Stock] {subject_tag} 🔴2단계(실손실) {stage2_cnt}종목 - {now_str}"
    else:
        subject = f"[Boss Stock] {subject_tag} ⚠️1단계(추세꺾임) {stage1_cnt}종목 - {now_str}"

    html = build_html(all_stocks, f"{now_str}  |  {alert_tag}")
    send_email(subject, html)
    print(f"[DONE] 알림 {len(alerts)}종목 — 최고단계: {max_stage_overall}단계")

if __name__ == "__main__":
    main()
