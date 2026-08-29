"""Telegram Bot for Vedic Astrology Trading Signals.

Sends:
- Morning Panchang report (once daily at market open)
- Hourly Hora signals during market hours
- End-of-day summary

Setup:
1. Create a bot via @BotFather on Telegram, get the token
2. Set TELEGRAM_BOT_TOKEN in .env
3. Set TELEGRAM_CHAT_ID in .env (your chat/group ID)
4. Run: python telegram_bot.py
"""
from __future__ import annotations

import datetime
import json
import logging
import time
from pathlib import Path
from urllib.request import Request, urlopen

from src.astrology.hora import compute_trading_day_horas
from src.astrology.muhurta import compute_muhurta_schedule, is_in_rahu_kaal
from src.astrology.panchang import compute_panchang
from src.data.company_registry import load_companies
from src.data.ephemeris import GRAHA_NAMES
from src.signals.intraday import compute_natal_score_for_day, plan_trading_day

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("telegram-bot")

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_COMPANIES = PROJECT_ROOT / "data" / "companies.csv"


class TelegramBot:
    def __init__(self, token: str, chat_id: str) -> None:
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{token}"

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        payload = json.dumps({
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }).encode("utf-8")
        req = Request(
            f"{self.base_url}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception:
            logger.error("Failed to send Telegram message", exc_info=True)
            return False


def format_panchang_message(date: datetime.date) -> str:
    p = compute_panchang(date)
    vara_name = GRAHA_NAMES.get(p.vara_ruler, p.vara_ruler.name)

    status = "AUSPICIOUS" if p.is_auspicious else "CAUTION"
    icon = "+" if p.is_auspicious else "!!"

    lines = [
        f"<b>PANCHANG -- {date.strftime('%A, %d %b %Y')}</b>",
        "",
        f"Tithi:     {p.tithi.name} ({p.tithi.paksha}) [{p.tithi.score:+.1f}]",
        f"Yoga:      {p.yoga.name} [{p.yoga.score:+.1f}]",
        f"Karana:    {p.karana.name} [{p.karana.score:+.1f}]",
        f"Nakshatra: {p.moon_nakshatra}",
        f"Vara:      {vara_name}",
        "",
        f"<b>Day Score: {p.composite_score:+.2f} [{status}]</b>",
    ]

    if p.warnings:
        lines.append("")
        for w in p.warnings:
            lines.append(f"!! {w}")

    return "\n".join(lines)


def format_hora_message(
    ticker: str,
    companies: dict,
    date: datetime.date,
) -> str:
    company = companies.get(ticker)
    if company is None:
        return f"Ticker {ticker} not found in registry"

    plan, panchang = plan_trading_day(company, date)

    lines = [
        f"<b>HORA PLAN -- {ticker} -- {date}</b>",
        "",
    ]
    for row in plan:
        icon = {"BUY": "+", "SELL/EXIT": "-", "HOLD": "="}[row["recommendation"]]
        lines.append(
            f"[{icon}] {row['time']}  {row['hora_ruler']:8s}  -> {row['recommendation']}"
        )

    return "\n".join(lines)


def format_hourly_signal(
    ticker: str,
    companies: dict,
    dt: datetime.datetime,
) -> str:
    company = companies.get(ticker)
    if company is None:
        return ""

    natal = compute_natal_score_for_day(company, dt.date())
    from src.signals.intraday import generate_intraday_signal
    from src.astrology.panchang import compute_panchang

    panchang = compute_panchang(dt.date())
    signal = generate_intraday_signal(company, dt, natal, panchang=panchang)

    icon = {"BUY": "+", "SELL": "-", "HOLD": "="}[signal.direction.value]

    lines = [
        f"<b>[{icon}] {ticker} -- {dt.strftime('%H:%M')}</b>",
        f"Direction: {signal.direction.value} ({signal.strength})",
        f"Hora: {signal.hora_ruler.name} [{signal.hora_score:+.1f}]",
        f"Muhurta: {signal.muhurta_name} [{signal.muhurta_score:+.1f}]",
        f"Confidence: {signal.confidence}/100",
        f"Reason: {signal.reason}",
    ]
    if signal.warnings:
        lines.append(f"Warnings: {', '.join(signal.warnings)}")

    return "\n".join(lines)


def run_bot(
    token: str,
    chat_id: str,
    tickers: list[str] | None = None,
    market_open_hour: int = 9,
    market_close_hour: int = 16,
) -> None:
    bot = TelegramBot(token, chat_id)
    companies = load_companies(DEFAULT_COMPANIES)

    if tickers is None:
        tickers = list(companies.keys())[:5]

    logger.info("Telegram bot started for %d tickers: %s", len(tickers), tickers)

    last_panchang_date = None
    last_hora_hour = -1

    while True:
        now = datetime.datetime.now()
        today = now.date()
        current_hour = now.hour

        # Skip weekends
        if today.weekday() >= 5:
            time.sleep(300)
            continue

        # Morning Panchang (send once at market open)
        if current_hour >= market_open_hour and last_panchang_date != today:
            logger.info("Sending morning Panchang")
            msg = format_panchang_message(today)
            bot.send_message(msg)

            for ticker in tickers:
                hora_msg = format_hora_message(ticker, companies, today)
                bot.send_message(hora_msg)
                time.sleep(1)

            last_panchang_date = today
            last_hora_hour = current_hour

        # Hourly Hora signals during market hours
        if (market_open_hour <= current_hour < market_close_hour
                and current_hour != last_hora_hour):
            logger.info("Sending hourly signals for hour %d", current_hour)
            for ticker in tickers:
                try:
                    msg = format_hourly_signal(ticker, companies, now)
                    if msg:
                        bot.send_message(msg)
                    time.sleep(1)
                except Exception:
                    logger.error("Failed for %s", ticker, exc_info=True)
            last_hora_hour = current_hour

        # End of day summary
        if current_hour == market_close_hour and last_hora_hour != -99:
            panchang = compute_panchang(today)
            summary = (
                f"<b>END OF DAY -- {today}</b>\n\n"
                f"Panchang score: {panchang.composite_score:+.2f}\n"
                f"Day was: {'AUSPICIOUS' if panchang.is_auspicious else 'CAUTIOUS'}"
            )
            bot.send_message(summary)
            last_hora_hour = -99

        time.sleep(60)


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    load_dotenv()

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        print("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
        print("1. Message @BotFather on Telegram to create a bot")
        print("2. Get your chat ID from @userinfobot")
        exit(1)

    # Optional: comma-separated tickers
    tickers = os.environ.get("TELEGRAM_TICKERS", "RELIANCE,TCS,INFY,HDFCBANK,AAPL")
    ticker_list = [t.strip() for t in tickers.split(",")]

    run_bot(token, chat_id, ticker_list)
