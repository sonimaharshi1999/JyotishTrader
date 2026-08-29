from __future__ import annotations

import datetime
import logging
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AccountInfo:
    equity: Decimal
    cash: Decimal
    buying_power: Decimal
    currency: str = "USD"


@dataclass(frozen=True)
class BrokerPosition:
    ticker: str
    qty: int
    avg_entry_price: Decimal
    market_value: Decimal
    current_price: Decimal
    unrealized_pnl: Decimal


@dataclass(frozen=True)
class OrderResult:
    order_id: str
    status: str
    ticker: str
    side: str
    qty: int
    filled_qty: int = 0
    filled_avg_price: Decimal | None = None
    submitted_at: datetime.datetime | None = None
    filled_at: datetime.datetime | None = None

    @property
    def is_filled(self) -> bool:
        return self.status == "filled"


@runtime_checkable
class Broker(Protocol):
    def get_account(self) -> AccountInfo: ...
    def get_positions(self) -> dict[str, BrokerPosition]: ...
    def get_current_price(self, ticker: str) -> Decimal | None: ...
    def submit_order(
        self, ticker: str, qty: int, side: str,
        order_type: str = "market", time_in_force: str = "day",
    ) -> OrderResult: ...
    def get_order(self, order_id: str) -> OrderResult: ...
    def cancel_order(self, order_id: str) -> bool: ...


class AlpacaBroker:
    def __init__(self, api_key: str, api_secret: str, base_url: str) -> None:
        import alpaca_trade_api as tradeapi
        self._api = tradeapi.REST(api_key, api_secret, base_url, api_version="v2")
        self._base_url = base_url
        logger.info("Alpaca broker initialized: %s", base_url)

    @property
    def is_paper(self) -> bool:
        return "paper" in self._base_url

    def get_account(self) -> AccountInfo:
        acct = self._api.get_account()
        return AccountInfo(
            equity=Decimal(acct.equity),
            cash=Decimal(acct.cash),
            buying_power=Decimal(acct.buying_power),
            currency=acct.currency,
        )

    def get_positions(self) -> dict[str, BrokerPosition]:
        positions = self._api.list_positions()
        result: dict[str, BrokerPosition] = {}
        for p in positions:
            result[p.symbol] = BrokerPosition(
                ticker=p.symbol,
                qty=int(p.qty),
                avg_entry_price=Decimal(p.avg_entry_price),
                market_value=Decimal(p.market_value),
                current_price=Decimal(p.current_price),
                unrealized_pnl=Decimal(p.unrealized_pl),
            )
        return result

    def get_current_price(self, ticker: str) -> Decimal | None:
        try:
            quote = self._api.get_latest_trade(ticker)
            return Decimal(str(quote.price))
        except Exception:
            logger.warning("Failed to get price for %s", ticker, exc_info=True)
            return None

    def submit_order(
        self, ticker: str, qty: int, side: str,
        order_type: str = "market", time_in_force: str = "day",
    ) -> OrderResult:
        logger.info("Submitting %s order: %s %d %s", order_type, side, qty, ticker)
        order = self._api.submit_order(
            symbol=ticker,
            qty=qty,
            side=side,
            type=order_type,
            time_in_force=time_in_force,
        )
        return self._map_order(order)

    def get_order(self, order_id: str) -> OrderResult:
        order = self._api.get_order(order_id)
        return self._map_order(order)

    def cancel_order(self, order_id: str) -> bool:
        try:
            self._api.cancel_order(order_id)
            return True
        except Exception:
            logger.error("Failed to cancel order %s", order_id, exc_info=True)
            return False

    def wait_for_fill(self, order_id: str, timeout_sec: int = 30) -> OrderResult:
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            result = self.get_order(order_id)
            if result.status in ("filled", "cancelled", "expired", "rejected"):
                return result
            time.sleep(1)
        return self.get_order(order_id)

    def _map_order(self, order) -> OrderResult:
        filled_price = None
        if order.filled_avg_price:
            filled_price = Decimal(str(order.filled_avg_price))
        return OrderResult(
            order_id=order.id,
            status=order.status,
            ticker=order.symbol,
            side=order.side,
            qty=int(order.qty),
            filled_qty=int(order.filled_qty or 0),
            filled_avg_price=filled_price,
            submitted_at=order.submitted_at if hasattr(order, "submitted_at") else None,
            filled_at=order.filled_at if hasattr(order, "filled_at") else None,
        )


class PaperBroker:
    """In-memory broker for testing without Alpaca credentials."""

    def __init__(self, initial_cash: float = 100000) -> None:
        self._cash = Decimal(str(initial_cash))
        self._positions: dict[str, BrokerPosition] = {}
        self._orders: list[OrderResult] = []
        self._order_counter = 0

    @property
    def is_paper(self) -> bool:
        return True

    def get_account(self) -> AccountInfo:
        equity = self._cash + sum(p.market_value for p in self._positions.values())
        return AccountInfo(
            equity=equity,
            cash=self._cash,
            buying_power=self._cash,
        )

    def get_positions(self) -> dict[str, BrokerPosition]:
        return dict(self._positions)

    def get_current_price(self, ticker: str) -> Decimal | None:
        pos = self._positions.get(ticker)
        if pos:
            return pos.current_price
        return None

    def submit_order(
        self, ticker: str, qty: int, side: str,
        order_type: str = "market", time_in_force: str = "day",
    ) -> OrderResult:
        self._order_counter += 1
        order_id = f"paper-{self._order_counter:06d}"

        price = self.get_current_price(ticker)
        if price is None:
            price = Decimal("100.00")

        if side == "buy":
            cost = price * qty
            if cost > self._cash:
                qty = int(self._cash / price)
                if qty <= 0:
                    return OrderResult(
                        order_id=order_id, status="rejected",
                        ticker=ticker, side=side, qty=0,
                    )
                cost = price * qty

            self._cash -= cost
            existing = self._positions.get(ticker)
            if existing:
                total_qty = existing.qty + qty
                avg_price = (existing.avg_entry_price * existing.qty + price * qty) / total_qty
                self._positions[ticker] = BrokerPosition(
                    ticker=ticker, qty=total_qty, avg_entry_price=avg_price,
                    market_value=price * total_qty, current_price=price,
                    unrealized_pnl=(price - avg_price) * total_qty,
                )
            else:
                self._positions[ticker] = BrokerPosition(
                    ticker=ticker, qty=qty, avg_entry_price=price,
                    market_value=price * qty, current_price=price,
                    unrealized_pnl=Decimal("0"),
                )
        elif side == "sell":
            pos = self._positions.get(ticker)
            if pos is None or pos.qty < qty:
                return OrderResult(
                    order_id=order_id, status="rejected",
                    ticker=ticker, side=side, qty=qty,
                )
            proceeds = price * qty
            self._cash += proceeds
            remaining = pos.qty - qty
            if remaining > 0:
                self._positions[ticker] = BrokerPosition(
                    ticker=ticker, qty=remaining, avg_entry_price=pos.avg_entry_price,
                    market_value=price * remaining, current_price=price,
                    unrealized_pnl=(price - pos.avg_entry_price) * remaining,
                )
            else:
                del self._positions[ticker]

        now = datetime.datetime.now(datetime.timezone.utc)
        result = OrderResult(
            order_id=order_id, status="filled",
            ticker=ticker, side=side, qty=qty,
            filled_qty=qty, filled_avg_price=price,
            submitted_at=now, filled_at=now,
        )
        self._orders.append(result)
        return result

    def get_order(self, order_id: str) -> OrderResult:
        for o in self._orders:
            if o.order_id == order_id:
                return o
        return OrderResult(
            order_id=order_id, status="not_found",
            ticker="", side="", qty=0,
        )

    def cancel_order(self, order_id: str) -> bool:
        return False

    def update_price(self, ticker: str, price: Decimal) -> None:
        pos = self._positions.get(ticker)
        if pos:
            self._positions[ticker] = BrokerPosition(
                ticker=ticker, qty=pos.qty, avg_entry_price=pos.avg_entry_price,
                market_value=price * pos.qty, current_price=price,
                unrealized_pnl=(price - pos.avg_entry_price) * pos.qty,
            )


class ZerodhaBroker:
    """Zerodha Kite Connect broker implementation for Indian markets (NSE/BSE)."""

    KITE_STATUS_MAP = {
        "COMPLETE": "filled",
        "CANCELLED": "cancelled",
        "REJECTED": "rejected",
        "OPEN": "open",
        "TRIGGER PENDING": "open",
        "OPEN PENDING": "open",
        "VALIDATION PENDING": "open",
        "PUT ORDER REQ RECEIVED": "open",
        "MODIFY PENDING": "open",
        "CANCEL PENDING": "open",
    }

    def __init__(self, api_key: str, access_token: str, exchange: str = "NSE") -> None:
        from kiteconnect import KiteConnect
        self._kite = KiteConnect(api_key=api_key)
        self._kite.set_access_token(access_token)
        self._exchange = exchange
        logger.info("Zerodha broker initialized: exchange=%s", exchange)

    @property
    def is_paper(self) -> bool:
        return False

    def get_account(self) -> AccountInfo:
        margins = self._kite.margins("equity")
        available = margins.get("available", {})
        utilised = margins.get("utilised", {})
        net = margins.get("net", 0)

        cash = Decimal(str(available.get("live_balance", 0)))
        equity = Decimal(str(net)) if net else cash
        buying_power = Decimal(str(available.get("collateral", 0))) + cash

        return AccountInfo(
            equity=equity,
            cash=cash,
            buying_power=buying_power,
            currency="INR",
        )

    def get_positions(self) -> dict[str, BrokerPosition]:
        positions_data = self._kite.positions()
        net_positions = positions_data.get("net", [])
        result: dict[str, BrokerPosition] = {}

        for p in net_positions:
            if p.get("quantity", 0) == 0:
                continue
            symbol = p["tradingsymbol"]
            qty = abs(int(p["quantity"]))
            avg_price = Decimal(str(p.get("average_price", 0)))
            last_price = Decimal(str(p.get("last_price", 0)))
            pnl = Decimal(str(p.get("pnl", 0)))

            result[symbol] = BrokerPosition(
                ticker=symbol,
                qty=qty,
                avg_entry_price=avg_price,
                market_value=last_price * qty,
                current_price=last_price,
                unrealized_pnl=pnl,
            )
        return result

    def get_current_price(self, ticker: str) -> Decimal | None:
        try:
            instrument = f"{self._exchange}:{ticker}"
            data = self._kite.ltp(instrument)
            price_info = data.get(instrument)
            if price_info:
                return Decimal(str(price_info["last_price"]))
            return None
        except Exception:
            logger.warning("Failed to get price for %s", ticker, exc_info=True)
            return None

    def submit_order(
        self, ticker: str, qty: int, side: str,
        order_type: str = "market", time_in_force: str = "day",
    ) -> OrderResult:
        from kiteconnect import KiteConnect

        tx_type = (
            KiteConnect.TRANSACTION_TYPE_BUY if side.lower() == "buy"
            else KiteConnect.TRANSACTION_TYPE_SELL
        )

        kite_order_type = {
            "market": KiteConnect.ORDER_TYPE_MARKET,
            "limit": KiteConnect.ORDER_TYPE_LIMIT,
            "sl": KiteConnect.ORDER_TYPE_SLM,
        }.get(order_type.lower(), KiteConnect.ORDER_TYPE_MARKET)

        kite_validity = {
            "day": KiteConnect.VALIDITY_DAY,
            "ioc": KiteConnect.VALIDITY_IOC,
        }.get(time_in_force.lower(), KiteConnect.VALIDITY_DAY)

        logger.info(
            "Zerodha: submitting %s %s %d %s on %s",
            kite_order_type, side, qty, ticker, self._exchange,
        )

        try:
            order_id = self._kite.place_order(
                variety=KiteConnect.VARIETY_REGULAR,
                exchange=self._exchange,
                tradingsymbol=ticker,
                transaction_type=tx_type,
                quantity=qty,
                order_type=kite_order_type,
                product=KiteConnect.PRODUCT_CNC,
                validity=kite_validity,
            )
            return OrderResult(
                order_id=str(order_id),
                status="open",
                ticker=ticker,
                side=side.lower(),
                qty=qty,
                submitted_at=datetime.datetime.now(datetime.timezone.utc),
            )
        except Exception as e:
            logger.error("Zerodha order failed: %s", e, exc_info=True)
            return OrderResult(
                order_id="", status="rejected",
                ticker=ticker, side=side.lower(), qty=qty,
            )

    def get_order(self, order_id: str) -> OrderResult:
        try:
            history = self._kite.order_history(order_id)
            if not history:
                return OrderResult(
                    order_id=order_id, status="not_found",
                    ticker="", side="", qty=0,
                )
            latest = history[-1]
            status = self.KITE_STATUS_MAP.get(latest.get("status", ""), "open")

            filled_qty = int(latest.get("filled_quantity", 0))
            filled_price = None
            if latest.get("average_price"):
                filled_price = Decimal(str(latest["average_price"]))

            return OrderResult(
                order_id=order_id,
                status=status,
                ticker=latest.get("tradingsymbol", ""),
                side=latest.get("transaction_type", "").lower(),
                qty=int(latest.get("quantity", 0)),
                filled_qty=filled_qty,
                filled_avg_price=filled_price,
            )
        except Exception:
            logger.error("Failed to get order %s", order_id, exc_info=True)
            return OrderResult(
                order_id=order_id, status="not_found",
                ticker="", side="", qty=0,
            )

    def cancel_order(self, order_id: str) -> bool:
        try:
            from kiteconnect import KiteConnect
            self._kite.cancel_order(
                variety=KiteConnect.VARIETY_REGULAR,
                order_id=order_id,
            )
            return True
        except Exception:
            logger.error("Failed to cancel order %s", order_id, exc_info=True)
            return False

    def wait_for_fill(self, order_id: str, timeout_sec: int = 30) -> OrderResult:
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            result = self.get_order(order_id)
            if result.status in ("filled", "cancelled", "rejected", "not_found"):
                return result
            time.sleep(1)
        return self.get_order(order_id)
