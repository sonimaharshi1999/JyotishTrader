from __future__ import annotations

import json
import logging
import smtplib
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

MAX_SEND_ATTEMPTS = 3
RATE_LIMIT_SECONDS = 3600  # 1 alert per ticker per hour


@dataclass(frozen=True)
class AlertMessage:
    title: str
    body: str
    level: str = "info"  # info, warning, critical
    ticker: str | None = None
    data: dict[str, Any] | None = None


class AlertChannel(ABC):
    @abstractmethod
    def send(self, message: AlertMessage) -> bool:
        ...


class SlackChannel(AlertChannel):
    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    def send(self, message: AlertMessage) -> bool:
        emoji = {"info": ":chart_with_upwards_trend:", "warning": ":warning:", "critical": ":rotating_light:"}
        icon = emoji.get(message.level, ":star:")

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{icon} {message.title}"},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": message.body},
            },
        ]
        if message.data:
            fields = [
                {"type": "mrkdwn", "text": f"*{k}:* {v}"}
                for k, v in message.data.items()
            ]
            blocks.append({"type": "section", "fields": fields[:10]})

        payload = json.dumps({"blocks": blocks}).encode("utf-8")
        req = Request(self.webhook_url, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception:
            logger.error("Failed to send Slack alert", exc_info=True)
            return False


class EmailChannel(AlertChannel):
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        from_addr: str,
        to_addrs: list[str],
        use_tls: bool = True,
    ) -> None:
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_addr = from_addr
        self.to_addrs = to_addrs
        self.use_tls = use_tls

    def send(self, message: AlertMessage) -> bool:
        msg = MIMEMultipart()
        msg["From"] = self.from_addr
        msg["To"] = ", ".join(self.to_addrs)
        msg["Subject"] = f"[Astro Trader {message.level.upper()}] {message.title}"

        body = message.body
        if message.data:
            body += "\n\n--- Details ---\n"
            for k, v in message.data.items():
                body += f"{k}: {v}\n"

        msg.attach(MIMEText(body, "plain"))

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            return True
        except Exception:
            logger.error("Failed to send email alert", exc_info=True)
            return False


class ConsoleChannel(AlertChannel):
    def send(self, message: AlertMessage) -> bool:
        prefix = {"info": "INFO", "warning": "WARN", "critical": "CRIT"}
        tag = prefix.get(message.level, "INFO")
        print(f"[{tag}] {message.title}: {message.body}")
        return True


class AlertManager:
    def __init__(self) -> None:
        self.channels: list[AlertChannel] = []
        self._last_alert: dict[str, float] = {}

    def add_channel(self, channel: AlertChannel) -> None:
        self.channels.append(channel)

    def _is_rate_limited(self, key: str) -> bool:
        last = self._last_alert.get(key, 0)
        if time.time() - last < RATE_LIMIT_SECONDS:
            return True
        self._last_alert[key] = time.time()
        return False

    def send(self, message: AlertMessage) -> None:
        rate_key = f"{message.ticker}:{message.title}" if message.ticker else message.title
        if self._is_rate_limited(rate_key):
            logger.debug("Rate-limited alert: %s", rate_key)
            return

        for ch in self.channels:
            sent = False
            for attempt in range(MAX_SEND_ATTEMPTS):
                try:
                    if ch.send(message):
                        sent = True
                        break
                except Exception:
                    if attempt == MAX_SEND_ATTEMPTS - 1:
                        logger.error("Alert channel %s failed after %d attempts", type(ch).__name__, MAX_SEND_ATTEMPTS, exc_info=True)
                    else:
                        time.sleep(2 ** attempt)

    def signal_alert(
        self,
        ticker: str,
        direction: str,
        composite_score: float,
        confidence: int | None = None,
    ) -> None:
        self.send(AlertMessage(
            title=f"{direction} Signal: {ticker}",
            body=f"Composite score: {composite_score:+.2f}",
            level="info" if direction == "HOLD" else "warning",
            ticker=ticker,
            data={"Direction": direction, "Score": f"{composite_score:+.2f}", "Confidence": str(confidence or "N/A")},
        ))

    def stop_loss_alert(self, ticker: str, entry_price: float, current_price: float) -> None:
        drop = (entry_price - current_price) / entry_price * 100
        self.send(AlertMessage(
            title=f"Stop Loss Triggered: {ticker}",
            body=f"Price dropped {drop:.1f}% from entry ${entry_price:.2f} to ${current_price:.2f}",
            level="critical",
            ticker=ticker,
            data={"Entry": f"${entry_price:.2f}", "Current": f"${current_price:.2f}", "Drop": f"{drop:.1f}%"},
        ))

    def trade_executed_alert(self, ticker: str, action: str, shares: int, price: float) -> None:
        self.send(AlertMessage(
            title=f"Trade Executed: {action} {ticker}",
            body=f"{action} {shares} shares @ ${price:.2f}",
            level="info",
            ticker=ticker,
            data={"Action": action, "Shares": str(shares), "Price": f"${price:.2f}"},
        ))
