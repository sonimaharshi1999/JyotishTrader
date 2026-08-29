from __future__ import annotations

import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from src.astrology.bhavas import build_bhava_chart, analyze_bhavas, BHAVA_NAMES
from src.astrology.dashas import compute_dashas
from src.astrology.lunar import get_lunar_phase
from src.astrology.nakshatras import get_nakshatra, get_graha_nakshatras
from src.astrology.natal_chart import build_natal_chart
from src.astrology.planetary_hours import get_planetary_day_info
from src.astrology.retrogrades import get_all_retrograde_statuses
from src.astrology.scoring import score_transit_report
from src.astrology.sector_mapping import apply_sector_weighting
from src.astrology.transits import compute_transits
from src.astrology.yogas import detect_yogas
from src.config_loader import load_config
from src.data.company_registry import load_companies
from src.data.database import get_connection, get_portfolio_history, get_signals_for_date, get_trade_history, init_db
from src.data.ephemeris import Graha, GRAHA_NAMES
from src.experimental.ceo_overlay import CEO_DATABASE, compute_composite_score
from src.market.data_feed import fetch_history, get_trend_signal
from src.signals.confidence import compute_confidence
from src.signals.filters import apply_filters
from src.signals.generator import generate_signal
from src.signals.multi_timeframe import compute_multi_timeframe

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = PROJECT_ROOT / "config.yaml"
DEFAULT_COMPANIES = PROJECT_ROOT / "data" / "companies.csv"
DB_PATH = PROJECT_ROOT / "data" / "astro_trader.db"


st.set_page_config(
    page_title="JyotishTrader",
    page_icon="🕉️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Authentication gate ---
_dashboard_pw = st.secrets.get("dashboard_password", "")
if _dashboard_pw:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        st.title("🔒 JyotishTrader")
        pw = st.text_input("Enter dashboard password", type="password")
        if pw and pw == _dashboard_pw:
            st.session_state.authenticated = True
            st.rerun()
        elif pw:
            st.error("Incorrect password")
        st.stop()


@st.cache_data(ttl=300)
def _load_companies():
    return load_companies(DEFAULT_COMPANIES)


@st.cache_data(ttl=300)
def _load_config():
    return load_config(DEFAULT_CONFIG)


def render_sidebar():
    st.sidebar.title("🕉️ JyotishTrader")
    st.sidebar.caption("Vedic Astrology-Powered Trading")
    page = st.sidebar.radio(
        "Navigate",
        ["Dashboard", "Signals", "Kundali", "Dashas", "Backtest", "Portfolio", "Retrograde Calendar"],
    )
    st.sidebar.markdown("---")
    st.sidebar.caption("⚠️ For educational/research purposes only.")
    return page


def render_dashboard():
    st.title("📊 Vedic Dashboard")
    today = datetime.date.today()
    companies = _load_companies()
    cfg = _load_config()

    col1, col2, col3, col4 = st.columns(4)

    lunar = get_lunar_phase(today)
    day_info = get_planetary_day_info(today)
    retrogrades = get_all_retrograde_statuses(today)
    retro_names = [GRAHA_NAMES.get(r.planet, r.planet.name) for r in retrogrades if r.is_retrograde]

    col1.metric("🌙 Tithi Phase", lunar.phase.value)
    col2.metric("🪐 Vara (Day Lord)", GRAHA_NAMES.get(day_info.day_ruler, day_info.day_ruler.name))
    col3.metric("🔄 Vakri (Retro)", ", ".join(retro_names) if retro_names else "None")
    col4.metric("📅 Date", str(today))

    st.markdown("---")
    st.subheader("Today's Signals")

    signals_data = []
    for ticker, company in companies.items():
        try:
            signal = generate_signal(
                company, today,
                buy_threshold=cfg["signals"]["buy_threshold"],
                sell_threshold=cfg["signals"]["sell_threshold"],
            )
            signal = apply_filters(signal)
            signals_data.append({
                "Ticker": ticker,
                "Direction": signal.direction.value,
                "Score": f"{signal.astro_score:+.1f}",
                "Composite": f"{signal.composite_score:+.2f}",
                "Strength": signal.strength,
                "Dasha": signal.current_dasha or "—",
                "Yogas": ", ".join(signal.active_yogas) if signal.active_yogas else "—",
                "Nakshatra": signal.moon_nakshatra or "—",
            })
        except Exception as e:
            signals_data.append({
                "Ticker": ticker, "Direction": "ERROR",
                "Score": "—", "Composite": "—", "Strength": "—",
                "Dasha": "—", "Yogas": "—", "Nakshatra": str(e)[:40],
            })

    st.dataframe(pd.DataFrame(signals_data), use_container_width=True, hide_index=True)


def render_signals():
    st.title("📡 Signal Explorer")
    companies = _load_companies()
    cfg = _load_config()

    col1, col2 = st.columns(2)
    ticker = col1.selectbox("Ticker", list(companies.keys()))
    date = col2.date_input("Date", value=datetime.date.today())

    if st.button("Generate Signal", type="primary"):
        company = companies[ticker]

        with st.spinner("Computing Jyotish analysis..."):
            natal = build_natal_chart(ticker, company.incorporation_date)
            report = compute_transits(natal, date)

            moon_pos = natal.positions[Graha.CHANDRA]
            dasha_info = compute_dashas(company.incorporation_date, moon_pos.longitude, date)

            astro = score_transit_report(report, dasha_info=dasha_info, natal_positions=natal.positions)
            signal = generate_signal(company, date)
            signal = apply_filters(signal)

        col1, col2, col3 = st.columns(3)
        col1.metric("Direction", signal.direction.value)
        col2.metric("Composite Score", f"{signal.composite_score:+.2f}")
        col3.metric("Dasha", signal.current_dasha or "N/A")

        st.markdown("---")

        # Vedic score breakdown
        st.subheader("Vedic Score Components")
        score_cols = st.columns(5)
        score_cols[0].metric("Drishti", f"{astro.drishti_score:+.2f}")
        score_cols[1].metric("Dasha", f"{astro.dasha_score:+.2f}")
        score_cols[2].metric("Nakshatra", f"{astro.nakshatra_score:+.2f}")
        score_cols[3].metric("Yogas", f"{astro.yoga_score:+.2f}")
        score_cols[4].metric("Bhavas", f"{astro.bhava_score:+.2f}")

        if astro.active_yogas:
            st.markdown("---")
            st.subheader("Active Yogas")
            for y in astro.active_yogas:
                st.write(f"  🔮 {y}")

        st.markdown("---")
        st.subheader("Active Drishtis (Aspects)")
        if report.aspects:
            aspects_data = []
            for ta in report.aspects:
                aspects_data.append({
                    "Transit Graha": GRAHA_NAMES.get(ta.transit_planet, ta.transit_planet.name),
                    "Drishti": ta.aspect.drishti_type.value,
                    "Natal Graha": GRAHA_NAMES.get(ta.natal_planet, ta.natal_planet.name),
                    "Weight": ta.aspect.weight,
                    "Strength": f"{ta.aspect.strength:.2f}",
                })
            st.dataframe(pd.DataFrame(aspects_data), use_container_width=True, hide_index=True)
        else:
            st.info("No active drishtis for this date.")


def render_kundali():
    st.title("🕉️ Kundali (Birth Chart)")
    companies = _load_companies()

    ticker = st.selectbox("Ticker", list(companies.keys()), key="kundali_ticker")
    company = companies[ticker]

    natal = build_natal_chart(ticker, company.incorporation_date)

    st.subheader(f"Kundali: {ticker}")
    st.caption(f"Incorporation: {company.incorporation_date} | {company.incorporation_location}")

    # Graha positions
    st.markdown("#### Graha Positions (Sidereal / Lahiri)")
    graha_data = []
    for graha, pos in natal.positions.items():
        nak = get_nakshatra(pos.longitude)
        graha_data.append({
            "Graha": GRAHA_NAMES.get(graha, graha.name),
            "Rashi": f"{pos.rashi} ({pos.rashi_en})",
            "Degree": f"{pos.degree_in_rashi:.1f}°",
            "Nakshatra": f"{nak.name} (Pada {nak.pada})",
            "Nak Lord": GRAHA_NAMES.get(nak.lord, nak.lord.name),
            "Longitude": f"{pos.longitude:.2f}°",
            "Vakri": "☿Rx" if pos.is_vakri else "",
        })
    st.dataframe(pd.DataFrame(graha_data), use_container_width=True, hide_index=True)

    # Bhava chart
    st.markdown("#### Bhava (House) Analysis")
    chart = build_bhava_chart(natal.positions)
    analysis = analyze_bhavas(chart, natal.positions)

    bhava_data = []
    for house in range(1, 13):
        occupants = chart.house_occupants.get(house, [])
        occ_names = ", ".join(GRAHA_NAMES.get(g, g.name) for g in occupants) or "—"
        bhava_data.append({
            "House": house,
            "Bhava": BHAVA_NAMES.get(house, ""),
            "Occupants": occ_names,
        })
    st.dataframe(pd.DataFrame(bhava_data), use_container_width=True, hide_index=True)

    bcol1, bcol2, bcol3 = st.columns(3)
    bcol1.metric("Wealth Score", f"{analysis.wealth_house_score:+.2f}")
    bcol2.metric("Gains Score", f"{analysis.gains_house_score:+.2f}")
    bcol3.metric("Loss Score", f"{analysis.loss_house_score:.2f}")

    # Yogas
    yogas = detect_yogas(natal.positions)
    if yogas:
        st.markdown("#### Natal Yogas")
        for y in yogas:
            st.write(f"  🔮 **{y.name}** ({y.sanskrit}) — {y.description} [score: {y.market_score:+.1f}]")


def render_dashas():
    st.title("🔄 Vimshottari Dasha")
    companies = _load_companies()

    ticker = st.selectbox("Ticker", list(companies.keys()), key="dasha_ticker")
    company = companies[ticker]

    natal = build_natal_chart(ticker, company.incorporation_date)
    moon_pos = natal.positions[Graha.CHANDRA]
    moon_nak = get_nakshatra(moon_pos.longitude)

    st.caption(f"Moon Nakshatra: **{moon_nak.name}** (Lord: {GRAHA_NAMES.get(moon_nak.lord, moon_nak.lord.name)})")

    target = st.date_input("Target Date", value=datetime.date.today(), key="dasha_date")
    dasha_info = compute_dashas(company.incorporation_date, moon_pos.longitude, target)

    if dasha_info.current_maha:
        st.subheader("Current Maha Dasha")
        md = dasha_info.current_maha
        st.write(f"  **{GRAHA_NAMES.get(md.lord, md.lord.name)}** — {md.start_date} to {md.end_date} ({md.years:.1f} years)")
        st.write(f"  Market Score: {md.market_score:+.1f}")

    if dasha_info.current_antar:
        st.subheader("Current Antar Dasha")
        ad = dasha_info.current_antar
        st.write(f"  **{GRAHA_NAMES.get(ad.antar_lord, ad.antar_lord.name)}** — {ad.start_date} to {ad.end_date}")
        st.write(f"  Market Score: {ad.market_score:+.1f}")

    st.markdown("---")
    st.subheader("Maha Dasha Timeline")
    dasha_data = []
    for md in dasha_info.maha_dashas[:15]:
        is_current = md.start_date <= target < md.end_date
        dasha_data.append({
            "Lord": GRAHA_NAMES.get(md.lord, md.lord.name),
            "Start": str(md.start_date),
            "End": str(md.end_date),
            "Years": f"{md.years:.1f}",
            "Market": f"{md.market_score:+.1f}",
            "Active": "→" if is_current else "",
        })
    st.dataframe(pd.DataFrame(dasha_data), use_container_width=True, hide_index=True)


def render_backtest():
    st.title("📈 Backtesting")
    companies = _load_companies()

    col1, col2, col3 = st.columns(3)
    ticker = col1.selectbox("Ticker", list(companies.keys()), key="bt_ticker")
    start = col2.date_input("Start", value=datetime.date(2023, 1, 1), key="bt_start")
    end = col3.date_input("End", value=datetime.date.today(), key="bt_end")

    if st.button("Run Backtest", type="primary"):
        from src.signals.backtest import run_backtest, format_backtest_report
        from src.signals.backtest_advanced import (
            compute_risk_metrics, compare_to_benchmark,
            run_monte_carlo, format_risk_report, format_monte_carlo_report,
        )

        company = companies[ticker]

        with st.spinner("Running backtest..."):
            result = run_backtest(company, start, end)
            metrics = compute_risk_metrics(result)
            benchmark = compare_to_benchmark(result)
            mc = run_monte_carlo(result)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Return", f"{metrics.total_return_pct:+.2f}%")
        col2.metric("Sharpe Ratio", f"{metrics.sharpe_ratio:.2f}")
        col3.metric("Max Drawdown", f"{metrics.max_drawdown_pct:.2f}%")
        col4.metric("Win Rate", f"{metrics.win_rate:.1%}")

        tab1, tab2, tab3 = st.tabs(["Risk Metrics", "Monte Carlo", "Trade Log"])

        with tab1:
            st.code(format_risk_report(metrics, benchmark))
        with tab2:
            st.code(format_monte_carlo_report(mc))
        with tab3:
            if result.closed_trades:
                trades_data = [{
                    "Entry": str(t.entry_date), "Exit": str(t.exit_date),
                    "Entry $": f"${t.entry_price}", "Exit $": f"${t.exit_price}",
                    "P&L": f"{t.pnl_pct:+.2f}%" if t.pnl_pct else "—",
                } for t in result.closed_trades]
                st.dataframe(pd.DataFrame(trades_data), use_container_width=True, hide_index=True)
            else:
                st.info("No trades in this period.")


def render_portfolio():
    st.title("💼 Portfolio")
    init_db(DB_PATH)
    try:
        with get_connection(DB_PATH) as conn:
            history = get_portfolio_history(conn)
            trades = get_trade_history(conn)

        if history:
            st.subheader("Portfolio Value")
            hist_df = pd.DataFrame(history)
            hist_df["total_value"] = hist_df["total_value"].astype(float)
            hist_df["date"] = pd.to_datetime(hist_df["date"])
            st.line_chart(hist_df.set_index("date")["total_value"])

        if trades:
            st.subheader("Recent Trades")
            st.dataframe(pd.DataFrame(trades), use_container_width=True, hide_index=True)
        else:
            st.info("No trades yet. Run `python main.py trade --paper` first.")
    except Exception as e:
        st.warning(f"Database: {e}")


def render_retrograde_calendar():
    st.title("🔄 Vakri (Retrograde) Calendar")

    from src.astrology.retrogrades import TRADE_SENSITIVE_PLANETS
    from src.experimental.retrograde_report import find_retrograde_windows

    year = st.selectbox("Year", [2024, 2025, 2026], index=1)
    start = datetime.date(year, 1, 1)
    end = datetime.date(year, 12, 31)

    for planet in TRADE_SENSITIVE_PLANETS:
        windows = find_retrograde_windows(planet, start, end)
        st.subheader(GRAHA_NAMES.get(planet, planet.name))
        if windows:
            for w in windows:
                st.write(f"  🔄 {w.start_date} → {w.end_date} ({w.duration_days} days)")
        else:
            st.write("  No vakri periods found.")


def main():
    page = render_sidebar()
    pages = {
        "Dashboard": render_dashboard,
        "Signals": render_signals,
        "Kundali": render_kundali,
        "Dashas": render_dashas,
        "Backtest": render_backtest,
        "Portfolio": render_portfolio,
        "Retrograde Calendar": render_retrograde_calendar,
    }
    pages[page]()


if __name__ == "__main__":
    main()
