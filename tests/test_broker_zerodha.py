import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

from src.trading.broker import ZerodhaBroker, PaperBroker, AccountInfo, BrokerPosition, OrderResult


class MockKiteConnect:
    TRANSACTION_TYPE_BUY = "BUY"
    TRANSACTION_TYPE_SELL = "SELL"
    ORDER_TYPE_MARKET = "MARKET"
    ORDER_TYPE_LIMIT = "LIMIT"
    ORDER_TYPE_SLM = "SL-M"
    VALIDITY_DAY = "DAY"
    VALIDITY_IOC = "IOC"
    VARIETY_REGULAR = "regular"
    PRODUCT_CNC = "CNC"

    def __init__(self, api_key):
        self.api_key = api_key
        self._access_token = None

    def set_access_token(self, token):
        self._access_token = token


class TestZerodhaBrokerGetAccount:
    @patch("src.trading.broker.ZerodhaBroker.__init__", return_value=None)
    def test_maps_margins_to_account_info(self, mock_init):
        broker = ZerodhaBroker.__new__(ZerodhaBroker)
        broker._kite = MagicMock()
        broker._exchange = "NSE"
        broker._kite.margins.return_value = {
            "available": {"live_balance": 500000, "collateral": 100000},
            "utilised": {"debits": 50000},
            "net": 550000,
        }

        account = broker.get_account()
        assert isinstance(account, AccountInfo)
        assert account.currency == "INR"
        assert account.cash == Decimal("500000")
        assert account.equity == Decimal("550000")


class TestZerodhaBrokerGetPositions:
    @patch("src.trading.broker.ZerodhaBroker.__init__", return_value=None)
    def test_maps_net_positions(self, mock_init):
        broker = ZerodhaBroker.__new__(ZerodhaBroker)
        broker._kite = MagicMock()
        broker._exchange = "NSE"
        broker._kite.positions.return_value = {
            "net": [
                {
                    "tradingsymbol": "RELIANCE",
                    "quantity": 10,
                    "average_price": 2500.0,
                    "last_price": 2600.0,
                    "pnl": 1000.0,
                },
                {
                    "tradingsymbol": "TCS",
                    "quantity": 0,
                    "average_price": 3500.0,
                    "last_price": 3600.0,
                    "pnl": 0,
                },
            ],
            "day": [],
        }

        positions = broker.get_positions()
        assert "RELIANCE" in positions
        assert "TCS" not in positions  # qty=0 filtered out
        assert positions["RELIANCE"].qty == 10
        assert positions["RELIANCE"].current_price == Decimal("2600.0")


class TestZerodhaBrokerGetPrice:
    @patch("src.trading.broker.ZerodhaBroker.__init__", return_value=None)
    def test_returns_last_price(self, mock_init):
        broker = ZerodhaBroker.__new__(ZerodhaBroker)
        broker._kite = MagicMock()
        broker._exchange = "NSE"
        broker._kite.ltp.return_value = {
            "NSE:INFY": {"last_price": 1450.50},
        }

        price = broker.get_current_price("INFY")
        assert price == Decimal("1450.5")
        broker._kite.ltp.assert_called_with("NSE:INFY")

    @patch("src.trading.broker.ZerodhaBroker.__init__", return_value=None)
    def test_returns_none_on_failure(self, mock_init):
        broker = ZerodhaBroker.__new__(ZerodhaBroker)
        broker._kite = MagicMock()
        broker._exchange = "NSE"
        broker._kite.ltp.side_effect = Exception("API error")

        price = broker.get_current_price("INFY")
        assert price is None


class TestZerodhaBrokerSubmitOrder:
    @patch("src.trading.broker.ZerodhaBroker.__init__", return_value=None)
    def test_buy_order(self, mock_init):
        broker = ZerodhaBroker.__new__(ZerodhaBroker)
        broker._kite = MagicMock()
        broker._exchange = "NSE"
        broker._kite.place_order.return_value = "230829000001"

        result = broker.submit_order("RELIANCE", 10, "buy")
        assert isinstance(result, OrderResult)
        assert result.order_id == "230829000001"
        assert result.status == "open"
        assert result.ticker == "RELIANCE"
        assert result.side == "buy"

    @patch("src.trading.broker.ZerodhaBroker.__init__", return_value=None)
    def test_rejected_on_exception(self, mock_init):
        broker = ZerodhaBroker.__new__(ZerodhaBroker)
        broker._kite = MagicMock()
        broker._exchange = "NSE"
        broker._kite.place_order.side_effect = Exception("Insufficient funds")

        result = broker.submit_order("RELIANCE", 10, "buy")
        assert result.status == "rejected"


class TestZerodhaBrokerGetOrder:
    @patch("src.trading.broker.ZerodhaBroker.__init__", return_value=None)
    def test_completed_order(self, mock_init):
        broker = ZerodhaBroker.__new__(ZerodhaBroker)
        broker._kite = MagicMock()
        broker._exchange = "NSE"
        broker._kite.order_history.return_value = [
            {"status": "OPEN", "tradingsymbol": "RELIANCE", "transaction_type": "BUY", "quantity": 10, "filled_quantity": 0},
            {"status": "COMPLETE", "tradingsymbol": "RELIANCE", "transaction_type": "BUY", "quantity": 10, "filled_quantity": 10, "average_price": 2550.0},
        ]

        result = broker.get_order("230829000001")
        assert result.status == "filled"
        assert result.filled_qty == 10
        assert result.filled_avg_price == Decimal("2550.0")

    @patch("src.trading.broker.ZerodhaBroker.__init__", return_value=None)
    def test_rejected_order(self, mock_init):
        broker = ZerodhaBroker.__new__(ZerodhaBroker)
        broker._kite = MagicMock()
        broker._exchange = "NSE"
        broker._kite.order_history.return_value = [
            {"status": "REJECTED", "tradingsymbol": "RELIANCE", "transaction_type": "BUY", "quantity": 10, "filled_quantity": 0},
        ]

        result = broker.get_order("230829000001")
        assert result.status == "rejected"


class TestStatusMapping:
    def test_all_known_statuses(self):
        mapping = ZerodhaBroker.KITE_STATUS_MAP
        assert mapping["COMPLETE"] == "filled"
        assert mapping["CANCELLED"] == "cancelled"
        assert mapping["REJECTED"] == "rejected"
        assert mapping["OPEN"] == "open"
        assert mapping["TRIGGER PENDING"] == "open"


class TestBuildBrokerDispatch:
    @patch("src.trading.broker.AlpacaBroker")
    def test_alpaca_provider(self, mock_alpaca):
        from unittest.mock import MagicMock
        settings = MagicMock()
        settings.broker.provider = "alpaca"
        settings.broker.api_key.get_secret_value.return_value = "key"
        settings.broker.api_secret.get_secret_value.return_value = "secret"
        settings.broker.live = False
        settings.portfolio.initial_capital = 100000

        from main import _build_broker
        broker = _build_broker(settings, force_paper=True)
        # With paper mode, either AlpacaBroker with paper URL or PaperBroker
        assert broker is not None

    def test_zerodha_paper_falls_back(self):
        from unittest.mock import MagicMock
        settings = MagicMock()
        settings.broker.provider = "zerodha"
        settings.broker.api_key.get_secret_value.return_value = "kite_key"
        settings.broker.access_token.get_secret_value.return_value = "kite_token"
        settings.broker.live = False
        settings.portfolio.initial_capital = 100000

        from main import _build_broker
        broker = _build_broker(settings, force_paper=True)
        assert isinstance(broker, PaperBroker)

    def test_no_credentials_falls_back(self):
        from unittest.mock import MagicMock
        settings = MagicMock()
        settings.broker.provider = "zerodha"
        settings.broker.api_key.get_secret_value.return_value = ""
        settings.broker.access_token.get_secret_value.return_value = ""
        settings.portfolio.initial_capital = 100000

        from main import _build_broker
        broker = _build_broker(settings, force_paper=True)
        assert isinstance(broker, PaperBroker)
