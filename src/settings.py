from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PortfolioSettings(BaseModel):
    initial_capital: float = 100000
    max_position_pct: float = 0.05
    max_exposure_pct: float = 0.30
    stop_loss_pct: float = 0.07
    trailing_stop_pct: float = 0.07
    max_sector_pct: float = 0.15
    risk_per_trade_pct: float = 0.01
    use_volatility_sizing: bool = True
    use_kelly_sizing: bool = False


class SignalSettings(BaseModel):
    buy_threshold: float = 3.0
    sell_threshold: float = -3.0
    require_trend_confirmation: bool = True
    min_confidence: int = 30
    use_multi_timeframe: bool = True
    use_sector_weighting: bool = True


class OrbDefaults(BaseModel):
    conjunction: float = 8
    sextile: float = 6
    square: float = 8
    trine: float = 8
    opposition: float = 8


class AspectWeights(BaseModel):
    conjunction: int = 3
    sextile: int = 1
    square: int = -2
    trine: int = 2
    opposition: int = -3


class AstrologySettings(BaseModel):
    orb_defaults: OrbDefaults = OrbDefaults()
    aspect_weights: AspectWeights = AspectWeights()
    skip_mercury_retrograde: bool = True
    retrograde_shadow_days: int = 3
    use_lunar_phases: bool = True
    use_planetary_hours: bool = True
    use_eclipses: bool = True
    use_progressions: bool = True
    use_ceo_overlay: bool = False


class MarketSettings(BaseModel):
    data_provider: str = "yfinance"
    api_key: SecretStr = SecretStr("")
    earnings_buffer_days: int = 3


class BrokerSettings(BaseModel):
    provider: str = "alpaca"  # "alpaca" or "zerodha"
    api_key: SecretStr = SecretStr("")
    api_secret: SecretStr = SecretStr("")  # Alpaca secret
    access_token: SecretStr = SecretStr("")  # Zerodha Kite access token
    base_url: str = "https://paper-api.alpaca.markets"
    exchange: str = "NSE"  # NSE or BSE (Zerodha only)
    live: bool = False


class EmailSettings(BaseModel):
    smtp_host: str = ""
    smtp_port: int = 587
    username: str = ""
    password: SecretStr = SecretStr("")
    from_addr: str = ""
    to_addrs: list[str] = []


class AlertSettings(BaseModel):
    enabled: bool = False
    slack_webhook: SecretStr = SecretStr("")
    email: EmailSettings = EmailSettings()


class DatabaseSettings(BaseModel):
    path: str = "data/astro_trader.db"


class ScheduleSettings(BaseModel):
    run_time: str = "08:00"
    timezone: str = "US/Eastern"


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ASTRO_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    portfolio: PortfolioSettings = PortfolioSettings()
    signals: SignalSettings = SignalSettings()
    astrology: AstrologySettings = AstrologySettings()
    market: MarketSettings = MarketSettings()
    broker: BrokerSettings = BrokerSettings()
    alerts: AlertSettings = AlertSettings()
    database: DatabaseSettings = DatabaseSettings()
    schedule: ScheduleSettings = ScheduleSettings()

    @field_validator("broker", mode="before")
    @classmethod
    def _resolve_broker_env(cls, v: Any) -> Any:
        """Allow flat env vars for both Alpaca and Zerodha credentials."""
        import os
        if isinstance(v, dict):
            if not v.get("api_key") and os.environ.get("ALPACA_API_KEY"):
                v["api_key"] = os.environ["ALPACA_API_KEY"]
            if not v.get("api_secret") and os.environ.get("ALPACA_API_SECRET"):
                v["api_secret"] = os.environ["ALPACA_API_SECRET"]
            if not v.get("api_key") and os.environ.get("KITE_API_KEY"):
                v["api_key"] = os.environ["KITE_API_KEY"]
            if not v.get("access_token") and os.environ.get("KITE_ACCESS_TOKEN"):
                v["access_token"] = os.environ["KITE_ACCESS_TOKEN"]
        return v


def load_settings(config_path: str | Path = "config.yaml") -> AppSettings:
    """Load settings from YAML file with env var overrides."""
    import yaml
    config_path = Path(config_path)
    overrides: dict[str, Any] = {}
    if config_path.exists():
        with config_path.open(encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        overrides = raw
    return AppSettings(**overrides)
