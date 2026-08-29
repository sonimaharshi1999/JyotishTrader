# JyotishTrader

**Automated stock trading powered by Jyotish (Vedic astrology)** -- Panchang, Muhurta, Hora, Vimshottari Dasha, Yogas, Nakshatras, Graha Drishti, and Bhava analysis.

Generates BUY/SELL/HOLD signals for NSE (Indian) and US stocks using a sidereal natal chart built from each company's incorporation date, then executes trades via Zerodha (Kite Connect) or Alpaca.

> **Disclaimer:** This is experimental software. Astrology-based trading is not a validated financial strategy. Never risk money you cannot afford to lose.

## What Makes This Unique

No other open-source project combines **all** of these Vedic layers into an automated trading system:

| Layer | What it does |
|---|---|
| **Graha Drishti** | Vedic aspects (Mars 4/7/8, Jupiter 5/7/9, Saturn 3/7/10) from transit planets to natal chart |
| **Vimshottari Dasha** | 120-year planetary period system -- knows if a company is in Guru dasha (expansion) or Shani dasha (contraction) |
| **Yogas** | Detects wealth combinations (Gaja Kesari, Dhana, Lakshmi) and poverty yogas (Kemadruma, Shani-Mangal) |
| **Nakshatras** | 27 lunar mansions with market scores -- Pushya (best for wealth) vs Mula (destruction) |
| **Bhavas** | Whole-sign house analysis -- are wealth houses (2nd, 11th) activated or loss houses (8th, 12th)? |
| **Panchang** | Daily Vedic calendar: Tithi, Yoga, Karana filter -- won't trade on Vishti karana or Shoola yoga days |
| **Hora** | Hourly planetary rulers -- BUY during Guru/Shukra hours, SELL during Shani/Mangal hours |
| **Muhurta** | 48-minute auspicious windows -- Abhijit muhurta is the best, Rahu Kaal is blocked |

## Quick Start

```bash
pip install -r requirements.txt

# See today's Panchang + signals for all 30 stocks
python main.py signals

# See hourly Hora trading plan for RELIANCE
python main.py intraday --ticker RELIANCE --paper

# Run daily trading cycle (paper)
python main.py trade --paper

# Run as scheduled daemon
python main.py daemon --paper

# Launch web dashboard
streamlit run dashboard.py
```

## Intraday Hora Trading

The agent trades multiple times per day based on planetary hours:

```
10:00 SHANI hora  -> SELL (Saturn = restriction)
11:00 GURU hora   -> BUY  (Jupiter = expansion)
12:00 MANGAL hora -> SELL (Mars = aggression, take profit)
13:00 SURYA hora  -> HOLD (Sun = neutral)
14:00 SHUKRA hora -> BUY  (Venus = value)
15:30 END OF DAY  -> close all positions
```

Each tick also checks:
- Is this a Rahu Kaal period? (blocked)
- Is the current Muhurta auspicious? (gated)
- Does the Panchang allow trading today? (Vishti karana = no trades)
- Does the price trend confirm the astro direction? (safety)

## Supported Brokers

| Broker | Market | Mode |
|---|---|---|
| **Zerodha (Kite Connect)** | NSE / BSE | Live only (no paper API) |
| **Alpaca** | US markets | Paper + Live |

Set in `config.yaml`:
```yaml
broker:
  provider: zerodha   # or "alpaca"
  exchange: NSE       # or "BSE"
```

## 30 Stocks (15 US + 15 Indian)

US: AAPL, MSFT, AMZN, TSLA, GOOGL, META, NVDA, JPM, V, JNJ, WMT, DIS, KO, PFE, BA

India: RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK, HINDUNILVR, ITC, SBIN, BHARTIARTL, KOTAKBANK, LT, MARUTI, SUNPHARMA, TATAMOTORS, WIPRO

## Architecture

```
src/astrology/    -- Vedic engine (14 modules, pure computation, zero API calls)
src/signals/      -- Signal generation, confidence, backtesting, intraday
src/trading/      -- Broker integration, executor, risk management
src/data/         -- Ephemeris, company registry, SQLite database
src/alerts/       -- Slack, email, console notifications
src/infra/        -- Scheduler, health check, logging, resilience
dashboard.py      -- Streamlit web UI (7 pages)
```

165 tests. Docker support. Structured logging. Health check endpoint.

## License

MIT
