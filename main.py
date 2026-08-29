from __future__ import annotations

import datetime
import logging
import sys
from decimal import Decimal
from pathlib import Path

import click

from src.infra.logging_config import setup_logging, generate_cycle_id

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = PROJECT_ROOT / "config.yaml"
DEFAULT_COMPANIES = PROJECT_ROOT / "data" / "companies.csv"

logger = logging.getLogger("astro-trader")


def _build_alert_manager(settings):
    from src.alerts.notifier import AlertManager, ConsoleChannel, SlackChannel, EmailChannel
    mgr = AlertManager()
    mgr.add_channel(ConsoleChannel())
    if settings.alerts.enabled:
        webhook = settings.alerts.slack_webhook.get_secret_value()
        if webhook:
            mgr.add_channel(SlackChannel(webhook))
        email = settings.alerts.email
        if email.smtp_host and email.username:
            mgr.add_channel(EmailChannel(
                smtp_host=email.smtp_host,
                smtp_port=email.smtp_port,
                username=email.username,
                password=email.password.get_secret_value(),
                from_addr=email.from_addr,
                to_addrs=email.to_addrs,
            ))
    return mgr


def _build_broker(settings, force_paper: bool = True):
    from src.trading.broker import AlpacaBroker, PaperBroker, ZerodhaBroker
    provider = settings.broker.provider.lower()
    api_key = settings.broker.api_key.get_secret_value()

    if provider == "zerodha":
        access_token = settings.broker.access_token.get_secret_value()
        if not api_key or not access_token:
            logger.warning("No Zerodha credentials, using in-memory PaperBroker")
            return PaperBroker(settings.portfolio.initial_capital)
        if force_paper or not settings.broker.live:
            logger.warning("Zerodha has no paper API — using in-memory PaperBroker")
            return PaperBroker(settings.portfolio.initial_capital)
        return ZerodhaBroker(api_key, access_token, settings.broker.exchange)

    # Default: Alpaca
    api_secret = settings.broker.api_secret.get_secret_value()
    if not api_key or not api_secret:
        logger.warning("No Alpaca credentials, using in-memory PaperBroker")
        return PaperBroker(settings.portfolio.initial_capital)

    if force_paper or not settings.broker.live:
        base_url = "https://paper-api.alpaca.markets"
    else:
        base_url = "https://api.alpaca.markets"

    return AlpacaBroker(api_key, api_secret, base_url)


def _run_trading_cycle(settings, companies, executor, correlation_tracker):
    from src.signals.filters import apply_filters
    from src.signals.generator import SignalDirection, generate_signal

    cycle_id = generate_cycle_id()
    today = datetime.date.today()
    logger.info("[%s] Starting trading cycle for %s (%d tickers)", cycle_id, today, len(companies))

    executor.sync_positions()

    stop_results = executor.check_trailing_stops()
    if stop_results:
        logger.info("[%s] Trailing stops triggered: %d sells", cycle_id, len(stop_results))

    executed = 0
    for ticker, company in companies.items():
        try:
            signal = generate_signal(
                company, today,
                buy_threshold=settings.signals.buy_threshold,
                sell_threshold=settings.signals.sell_threshold,
                require_trend_confirmation=settings.signals.require_trend_confirmation,
                min_confidence=settings.signals.min_confidence,
                use_multi_timeframe=settings.signals.use_multi_timeframe,
                correlation_tracker=correlation_tracker,
            )
            signal = apply_filters(
                signal,
                skip_mercury_retrograde=settings.astrology.skip_mercury_retrograde,
                retrograde_shadow_days=settings.astrology.retrograde_shadow_days,
                earnings_buffer_days=settings.market.earnings_buffer_days,
            )

            if signal.direction == SignalDirection.HOLD:
                continue

            price = executor.broker.get_current_price(ticker)
            if price is None:
                from src.market.data_feed import fetch_history
                df = fetch_history(ticker, today - datetime.timedelta(days=5), today)
                if df.empty:
                    continue
                price = Decimal(str(round(df["Close"].iloc[-1], 2)))

            result = executor.execute_signal(signal, price)
            if result and result.is_filled:
                executed += 1
                if executor.alerts:
                    executor.alerts.signal_alert(
                        ticker, signal.direction.value,
                        signal.composite_score, signal.confidence,
                    )

        except Exception:
            logger.error("[%s] Error processing %s", cycle_id, ticker, exc_info=True)

    executor.snapshot_portfolio()
    logger.info("[%s] Cycle complete: %d orders executed", cycle_id, executed)


@click.group()
def cli() -> None:
    """JyotishTrader — Vedic astrology-powered stock trading."""


@cli.command()
@click.option("--config", "config_path", default=str(DEFAULT_CONFIG))
@click.option("--companies", "companies_path", default=str(DEFAULT_COMPANIES))
@click.option("--ticker", default=None)
@click.option("--date", "date_str", default=None)
@click.option("--json-output", is_flag=True, default=False)
def signals(config_path: str, companies_path: str, ticker: str | None, date_str: str | None, json_output: bool) -> None:
    """Generate trading signals."""
    setup_logging(json_output=json_output)

    from src.data.company_registry import load_companies
    from src.settings import load_settings
    from src.signals.filters import apply_filters
    from src.signals.generator import generate_signal

    settings = load_settings(config_path)
    companies = load_companies(companies_path)
    target_date = datetime.date.fromisoformat(date_str) if date_str else datetime.date.today()

    tickers = [ticker.upper()] if ticker else list(companies.keys())

    click.echo(f"\n{'='*70}")
    click.echo(f"  Vedic Astrology Trading Signals — {target_date}")
    click.echo(f"{'='*70}\n")

    for t in tickers:
        if t not in companies:
            click.echo(f"  {t}: not in registry, skipping")
            continue
        company = companies[t]
        try:
            signal = generate_signal(
                company, target_date,
                buy_threshold=settings.signals.buy_threshold,
                sell_threshold=settings.signals.sell_threshold,
                require_trend_confirmation=settings.signals.require_trend_confirmation,
                min_confidence=settings.signals.min_confidence,
                use_multi_timeframe=settings.signals.use_multi_timeframe,
            )
            signal = apply_filters(signal)
            icon = {"BUY": "+", "SELL": "-", "HOLD": "="}[signal.direction.value]
            click.echo(
                f"  [{icon}] {signal.ticker:6s}  {signal.direction.value:4s}  "
                f"score={signal.astro_score:+.1f}  composite={signal.composite_score:+.2f}  "
                f"conf={signal.confidence or 0:3d}  ({signal.strength})"
            )
            if signal.current_dasha:
                click.echo(f"         dasha={signal.current_dasha}  yogas={', '.join(signal.active_yogas or []) or 'none'}")
        except Exception:
            logger.error("Failed to generate signal for %s", t, exc_info=True)

    click.echo()


@cli.command()
@click.option("--config", "config_path", default=str(DEFAULT_CONFIG))
@click.option("--companies", "companies_path", default=str(DEFAULT_COMPANIES))
@click.option("--ticker", default=None)
@click.option("--start", "start_str", required=True)
@click.option("--end", "end_str", required=True)
@click.option("--all", "run_all", is_flag=True)
def backtest(config_path: str, companies_path: str, ticker: str | None, start_str: str, end_str: str, run_all: bool) -> None:
    """Run historical backtest."""
    setup_logging()

    from src.data.company_registry import load_companies
    from src.settings import load_settings
    from src.signals.backtest import run_backtest, format_backtest_report
    from src.signals.backtest_advanced import compute_risk_metrics, compare_to_benchmark, format_risk_report

    settings = load_settings(config_path)
    companies = load_companies(companies_path)
    start = datetime.date.fromisoformat(start_str)
    end = datetime.date.fromisoformat(end_str)

    if ticker:
        tickers = [ticker.upper()]
    elif run_all:
        tickers = list(companies.keys())
    else:
        click.echo("Specify --ticker or --all")
        sys.exit(1)

    for t in tickers:
        if t not in companies:
            click.echo(f"{t}: not in registry, skipping")
            continue
        click.echo(f"\nRunning backtest for {t}...")
        result = run_backtest(
            companies[t], start, end,
            buy_threshold=settings.signals.buy_threshold,
            sell_threshold=settings.signals.sell_threshold,
            stop_loss_pct=settings.portfolio.stop_loss_pct * 100,
        )
        metrics = compute_risk_metrics(result)
        try:
            benchmark = compare_to_benchmark(result)
        except Exception:
            benchmark = None
        click.echo(format_risk_report(metrics, benchmark))
        click.echo()


@cli.command()
@click.option("--config", "config_path", default=str(DEFAULT_CONFIG))
@click.option("--companies", "companies_path", default=str(DEFAULT_COMPANIES))
@click.option("--paper", "force_paper", is_flag=True, default=True)
@click.option("--live", "go_live", is_flag=True, default=False)
@click.option("--json-output", is_flag=True, default=False)
def trade(config_path: str, companies_path: str, force_paper: bool, go_live: bool, json_output: bool) -> None:
    """Run a single trading cycle with real broker."""
    setup_logging(json_output=json_output)

    from src.data.company_registry import load_companies
    from src.data.database import init_db
    from src.settings import load_settings
    from src.signals.correlation import CorrelationTracker
    from src.trading.executor import TradingExecutor

    settings = load_settings(config_path)
    companies = load_companies(companies_path)

    if go_live and not settings.broker.live:
        click.echo("ERROR: --live requires broker.live=true in config")
        sys.exit(1)

    is_paper = not go_live
    mode = "PAPER" if is_paper else "LIVE"

    db_path = PROJECT_ROOT / settings.database.path
    init_db(db_path)

    broker = _build_broker(settings, force_paper=is_paper)
    alert_manager = _build_alert_manager(settings)
    correlation_path = PROJECT_ROOT / "data" / "correlation.json"
    correlation_tracker = CorrelationTracker.load(correlation_path)

    executor = TradingExecutor(
        broker=broker,
        settings=settings.portfolio,
        db_path=db_path,
        alert_manager=alert_manager,
        company_registry=companies,
    )

    click.echo(f"\n[{mode}] Starting trading cycle...")

    _run_trading_cycle(settings, companies, executor, correlation_tracker)

    correlation_tracker.save(correlation_path)

    account = broker.get_account()
    positions = broker.get_positions()
    click.echo(f"\nPortfolio ({mode}):")
    click.echo(f"  Equity:  ${account.equity:,.2f}")
    click.echo(f"  Cash:    ${account.cash:,.2f}")
    if positions:
        click.echo(f"  Positions ({len(positions)}):")
        for t, p in positions.items():
            click.echo(f"    {t}: {p.qty} shares @ ${p.avg_entry_price:.2f} (P&L: ${p.unrealized_pnl:+,.2f})")
    click.echo()


@cli.command()
@click.option("--config", "config_path", default=str(DEFAULT_CONFIG))
@click.option("--companies", "companies_path", default=str(DEFAULT_COMPANIES))
@click.option("--ticker", default=None, help="Single ticker to trade (or all)")
@click.option("--paper", "force_paper", is_flag=True, default=True)
@click.option("--live", "go_live", is_flag=True, default=False)
def intraday(config_path: str, companies_path: str, ticker: str | None, force_paper: bool, go_live: bool) -> None:
    """Run hourly Hora-based intraday trading for one full day."""
    setup_logging()

    from src.data.company_registry import load_companies
    from src.data.database import init_db
    from src.settings import load_settings
    from src.signals.intraday import plan_trading_day
    from src.trading.intraday_executor import IntradayExecutor

    settings = load_settings(config_path)
    all_companies = load_companies(companies_path)

    if ticker:
        companies = {ticker.upper(): all_companies[ticker.upper()]}
    else:
        companies = all_companies

    if go_live and not settings.broker.live:
        click.echo("ERROR: --live requires broker.live=true in config")
        sys.exit(1)

    is_paper = not go_live
    mode = "PAPER" if is_paper else "LIVE"
    today = datetime.date.today()

    db_path = PROJECT_ROOT / settings.database.path
    init_db(db_path)
    broker = _build_broker(settings, force_paper=is_paper)
    alert_manager = _build_alert_manager(settings)

    # Show today's panchang + hora plan
    click.echo(f"\n{'='*70}")
    click.echo(f"  Vedic Intraday Plan -- {today} [{mode}]")
    click.echo(f"{'='*70}")

    from src.astrology.panchang import compute_panchang
    from src.data.ephemeris import GRAHA_NAMES
    panchang = compute_panchang(today)
    click.echo(f"\n  PANCHANG:")
    click.echo(f"    Tithi:     {panchang.tithi.name} ({panchang.tithi.paksha}) [{panchang.tithi.score:+.1f}]")
    click.echo(f"    Yoga:      {panchang.yoga.name} [{panchang.yoga.score:+.1f}]")
    click.echo(f"    Karana:    {panchang.karana.name} [{panchang.karana.score:+.1f}]")
    click.echo(f"    Nakshatra: {panchang.moon_nakshatra}")
    click.echo(f"    Vara:      {GRAHA_NAMES.get(panchang.vara_ruler, panchang.vara_ruler.name)}")
    click.echo(f"    Day Score: {panchang.composite_score:+.2f} ({'AUSPICIOUS' if panchang.is_auspicious else 'CAUTION'})")
    if panchang.warnings:
        for w in panchang.warnings:
            click.echo(f"    !! {w}")

    sample = list(companies.values())[0]
    plan, _ = plan_trading_day(sample, today, market_open=9.25, market_close=15.5)
    click.echo(f"\n  HORA SCHEDULE ({sample.ticker}):")
    for row in plan:
        icon = {"BUY": "+", "SELL/EXIT": "-", "HOLD": "="}[row["recommendation"]]
        click.echo(
            f"    [{icon}] {row['time']}  {row['hora_ruler']:8s}  "
            f"natal={row['natal_score']}  combined={row['combined']}  -> {row['recommendation']}"
        )

    click.echo(f"\n  Starting intraday execution ({len(companies)} stocks)...\n")

    executor = IntradayExecutor(
        broker=broker,
        settings=settings.portfolio,
        db_path=db_path,
        alert_manager=alert_manager,
        max_trades_per_stock=8,
    )

    executor.init_day(companies, today)

    # Simulate hourly ticks for market hours (9:15 AM to 3:30 PM)
    import time
    current_hour = 9
    while current_hour < 16:
        dt = datetime.datetime(today.year, today.month, today.day, current_hour, 15)
        click.echo(f"  --- {dt.strftime('%H:%M')} tick ---")

        actions = executor.tick(companies, dt)
        for a in actions:
            pnl = f" pnl={a.get('pnl_pct', 0):+.2f}%" if "pnl_pct" in a else ""
            click.echo(
                f"    {a['action']:4s} {a['ticker']:10s} "
                f"{'shares=' + str(a.get('shares', '')) + ' ':16s}"
                f"@{a.get('price', 0):.2f}{pnl}  "
                f"hora={a.get('hora', '')}  {a.get('reason', '')}"
            )
        if not actions:
            click.echo("    (no trades)")

        current_hour += 1

    # End of day — close all
    click.echo(f"\n  --- 15:30 End of Day ---")
    eod_dt = datetime.datetime(today.year, today.month, today.day, 15, 30)
    eod_actions = executor.close_all_positions(eod_dt)
    for a in eod_actions:
        click.echo(f"    EOD SELL {a['ticker']} @{a['price']:.2f} pnl={a['pnl_pct']:+.2f}%")

    summary = executor.get_day_summary()
    click.echo(f"\n{'='*70}")
    click.echo(f"  Day Summary")
    click.echo(f"{'='*70}")
    click.echo(f"  Total trades: {summary['total_trades']}")
    click.echo(f"  Stocks traded: {', '.join(summary['stocks_traded']) or 'none'}")
    click.echo(f"  Daily P&L: {summary['daily_pnl_pct']:+.2f}%")
    if summary['per_stock_pnl']:
        for t, pnl in summary['per_stock_pnl'].items():
            click.echo(f"    {t}: {pnl:+.2f}%")
    click.echo()


@cli.command()
@click.option("--config", "config_path", default=str(DEFAULT_CONFIG))
@click.option("--companies", "companies_path", default=str(DEFAULT_COMPANIES))
@click.option("--paper", "force_paper", is_flag=True, default=True)
@click.option("--live", "go_live", is_flag=True, default=False)
@click.option("--health-port", default=8080, type=int)
@click.option("--json-output", is_flag=True, default=True)
def daemon(
    config_path: str, companies_path: str, force_paper: bool,
    go_live: bool, health_port: int, json_output: bool,
) -> None:
    """Run as a scheduled daemon (production mode)."""
    setup_logging(json_output=json_output)

    from src.data.company_registry import load_companies
    from src.data.database import init_db
    from src.infra.health import start_health_server, update_status
    from src.infra.scheduler import TradingScheduler
    from src.settings import load_settings
    from src.signals.correlation import CorrelationTracker
    from src.trading.executor import TradingExecutor

    settings = load_settings(config_path)
    companies = load_companies(companies_path)

    if go_live and not settings.broker.live:
        click.echo("ERROR: --live requires broker.live=true in config")
        sys.exit(1)

    is_paper = not go_live
    mode = "PAPER" if is_paper else "LIVE"

    db_path = PROJECT_ROOT / settings.database.path
    init_db(db_path)

    broker = _build_broker(settings, force_paper=is_paper)
    alert_manager = _build_alert_manager(settings)
    correlation_path = PROJECT_ROOT / "data" / "correlation.json"
    correlation_tracker = CorrelationTracker.load(correlation_path)

    executor = TradingExecutor(
        broker=broker,
        settings=settings.portfolio,
        db_path=db_path,
        alert_manager=alert_manager,
        company_registry=companies,
    )

    start_health_server(health_port)
    update_status(status="running", mode=mode)

    def run_cycle():
        logger.info("=== Trading cycle triggered ===")
        _run_trading_cycle(settings, companies, executor, correlation_tracker)
        correlation_tracker.save(correlation_path)
        update_status(
            last_cycle=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            open_positions=len(broker.get_positions()),
        )

    def check_stops():
        results = executor.check_trailing_stops()
        if results:
            logger.info("Stop monitor: %d stops triggered", len(results))

    def snapshot():
        executor.snapshot_portfolio()
        logger.info("Daily portfolio snapshot saved")

    hour, minute = (int(x) for x in settings.schedule.run_time.split(":"))
    scheduler = TradingScheduler(settings.schedule)
    scheduler.add_trading_cycle(run_cycle, hour, minute)
    scheduler.add_stop_monitor(check_stops, interval_minutes=5)
    scheduler.add_daily_snapshot(snapshot)

    update_status(scheduler_running=True)
    logger.info("[%s] Daemon starting — trading at %s %s", mode, settings.schedule.run_time, settings.schedule.timezone)
    scheduler.start()


if __name__ == "__main__":
    cli()
