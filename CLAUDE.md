# JyotishTrader — Vedic Astrology Trading Agent

## Project Overview

An autonomous trading agent that generates stock trading signals using **Vedic astrology (Jyotish)** — sidereal zodiac with Lahiri Ayanamsa, Navagraha (9 grahas including Rahu/Ketu), Nakshatras, Vimshottari Dasha, Graha Drishti, Yogas, and Bhava analysis — combined with traditional market data. Paper trading by default via Alpaca.

**Disclaimer:** Experimental/educational project. Not validated financial advice. Never risk money you cannot afford to lose.

## Vedic Astrology System

### Sidereal Zodiac (Lahiri Ayanamsa)
All calculations use the **sidereal zodiac**, not tropical. The Lahiri Ayanamsa (~24°) is subtracted from tropical longitudes to get true sidereal positions. This is the standard used in Indian Jyotish.

### Navagraha (9 Grahas)
| Graha    | Western  | Role         | Market Weight |
|----------|----------|--------------|---------------|
| Surya    | Sun      | Authority    | +0.5          |
| Chandra  | Moon     | Public mood  | +0.3          |
| Mangal   | Mars     | Aggression   | -0.5          |
| Budha    | Mercury  | Commerce     | +1.0          |
| Guru     | Jupiter  | Expansion    | +2.0          |
| Shukra   | Venus    | Value        | +1.5          |
| Shani    | Saturn   | Restriction  | -1.5          |
| Rahu     | N. Node  | Disruption   | -1.0          |
| Ketu     | S. Node  | Detachment   | -0.5          |

### Nakshatras (27 Lunar Mansions)
Each nakshatra spans 13°20' with a ruling graha lord. Key financial nakshatras:
- **Pushya** (Shani lord) — universally auspicious for wealth
- **Rohini** (Chandra lord) — prosperity and growth
- **Mula** (Ketu lord) — destruction/transformation, bearish
- **Ardra** (Rahu lord) — storms and disruption

### Graha Drishti (Vedic Aspects)
Unlike Western astrology's symmetric aspects, Vedic uses **directional sight**:
- **All grahas** → aspect the 7th house (180°, full strength)
- **Mangal (Mars)** → also aspects 4th and 8th houses
- **Guru (Jupiter)** → also aspects 5th and 9th houses
- **Shani (Saturn)** → also aspects 3rd and 10th houses
- **Rahu/Ketu** → also aspect 5th and 9th houses

### Vimshottari Dasha (120-Year Planetary Periods)
Based on Moon's nakshatra at incorporation, the company cycles through 9 dasha periods:
```
Ketu(7y) → Shukra(20y) → Surya(6y) → Chandra(10y) → Mangal(7y)
→ Rahu(18y) → Guru(16y) → Shani(19y) → Budha(17y) = 120 years
```
Each maha dasha has 9 antardashas (sub-periods). Guru and Shukra dashas are most favorable for wealth.

### Yogas (Planetary Combinations)
| Yoga           | Condition                              | Market Score |
|----------------|----------------------------------------|-------------|
| Gaja Kesari    | Guru in kendra from Chandra            | +3.0        |
| Dhana Yoga     | Guru-Shukra in kendra/trikona          | +2.5        |
| Lakshmi Yoga   | Strong Shukra + Guru in kendra         | +3.0        |
| Budhaditya     | Budha conjunct Surya                   | +1.5        |
| Chandra-Mangal | Chandra conjunct Mangal                | +1.5        |
| Hamsa Yoga     | Guru in kendra in own sign             | +2.5        |
| Kemadruma      | Chandra isolated (no neighbors)        | -2.5        |
| Surya Grahan   | Surya conjunct Rahu                    | -2.0        |
| Chandra Grahan | Chandra conjunct Rahu                  | -2.0        |
| Shani-Mangal   | Shani conjunct Mangal                  | -3.0        |

### Bhavas (Whole-Sign Houses)
Sun's rashi = 1st house (proxy lagna when birth time unknown). Key financial houses:
- **2nd (Dhana)** — accumulated wealth
- **5th (Putra)** — speculation, investments
- **10th (Karma)** — career success
- **11th (Labha)** — gains and profits
- **12th (Vyaya)** — losses and expenditure

## Signal Pipeline

```
Company (incorporation date)
    ↓
Sidereal Natal Chart (Lahiri Ayanamsa, all 9 grahas)
    ↓
┌─ Graha Drishti (Vedic aspects to natal) → 30% weight
├─ Vimshottari Dasha (current period)     → 25% weight
├─ Yoga Detection (10 wealth/poverty yogas)→ 20% weight
├─ Nakshatra Analysis (Moon's mansion)    → 15% weight
└─ Bhava Analysis (house placements)      → 10% weight
    ↓
Composite Vedic Score [-10, +10]
    ↓
Market Trend Confirmation (SMA crossover)
    ↓
composite = vedic_score × (1 + 0.3 × trend)
    ↓
Filters (Budha vakri, earnings, market closed)
    ↓
Signal: BUY / HOLD / SELL
    ↓
Risk Checks → Execute → Database → Alerts
```

## Architecture

```
astrology_trading_agent/
├── main.py                          # CLI (signals / backtest / trade)
├── dashboard.py                     # Streamlit dashboard (7 pages)
├── config.yaml                      # All parameters
├── requirements.txt
│
├── src/
│   ├── astrology/                   # Vedic Engine
│   │   ├── natal_chart.py           # Sidereal natal chart
│   │   ├── transits.py              # Graha transits
│   │   ├── aspects.py               # Graha Drishti (Vedic aspects)
│   │   ├── retrogrades.py           # Vakri (retrograde) detection
│   │   ├── scoring.py               # Combined Vedic scoring
│   │   ├── nakshatras.py            # 27 Nakshatras with lords
│   │   ├── dashas.py                # Vimshottari Dasha system
│   │   ├── yogas.py                 # 10 wealth/poverty yogas
│   │   ├── bhavas.py                # Whole-sign house system
│   │   ├── lunar.py                 # Lunar phases (Tithi)
│   │   ├── planetary_hours.py       # Vara (day lords)
│   │   ├── eclipses.py              # Eclipse amplifier
│   │   ├── progressions.py          # Secondary progressions
│   │   └── sector_mapping.py        # Sector ↔ graha weighting
│   │
│   ├── market/                      # Market Data
│   │   ├── data_feed.py             # yfinance price/volume
│   │   ├── fundamentals.py          # Market cap, P/E
│   │   └── calendar.py              # Earnings, holidays
│   │
│   ├── signals/                     # Signal Generation
│   │   ├── generator.py             # Vedic score + trend → signal
│   │   ├── filters.py               # Vakri / earnings filters
│   │   ├── confidence.py            # 0-100 confidence scoring
│   │   ├── multi_timeframe.py       # Daily/weekly/monthly alignment
│   │   ├── correlation.py           # Adaptive weight tuning
│   │   ├── backtest.py              # Historical backtesting
│   │   └── backtest_advanced.py     # Sharpe, Monte Carlo, walk-forward
│   │
│   ├── trading/                     # Execution & Risk
│   │   ├── portfolio.py             # Position management
│   │   ├── risk.py                  # Exposure limits
│   │   ├── executor.py              # Order execution
│   │   ├── trailing_stop.py         # Trailing stop-loss
│   │   ├── sector_limits.py         # Sector concentration
│   │   ├── volatility_sizing.py     # ATR-based sizing
│   │   └── kelly.py                 # Kelly criterion
│   │
│   ├── data/                        # Data Layer
│   │   ├── ephemeris.py             # Sidereal Swiss Ephemeris + Rahu/Ketu
│   │   ├── company_registry.py      # CSV loader
│   │   └── database.py              # SQLite persistence
│   │
│   ├── alerts/                      # Slack / Email / Console
│   │   └── notifier.py
│   │
│   └── experimental/                # IPO fallback, CEO overlay, retrograde report
│       ├── ipo_fallback.py
│       ├── ceo_overlay.py
│       └── retrograde_report.py
│
├── data/
│   └── companies.csv
│
└── tests/                           # 17 test files
    ├── test_aspects.py              # Vedic drishti tests
    ├── test_nakshatras.py           # 27 nakshatra tests
    ├── test_dashas.py               # Vimshottari dasha tests
    ├── test_yogas.py                # Yoga detection tests
    ├── test_bhavas.py               # House system tests
    ├── test_natal_chart.py
    ├── test_transits.py
    ├── test_scoring.py
    ├── test_signals.py
    ├── test_backtest.py
    ├── test_backtest_advanced.py
    ├── test_portfolio.py
    ├── test_lunar.py
    ├── test_confidence.py
    ├── test_trailing_stop.py
    ├── test_kelly.py
    ├── test_correlation.py
    └── test_database.py
```

## Dashboard Pages

| Page                | Description                                         |
|---------------------|-----------------------------------------------------|
| Dashboard           | Tithi, Vara, Vakri status + all signals              |
| Signals             | Deep-dive: drishti, dasha, yoga, nakshatra breakdown |
| Kundali             | Full sidereal birth chart with bhava table           |
| Dashas              | Vimshottari timeline with current maha/antar dasha   |
| Backtest            | Sharpe, Monte Carlo, trade log                       |
| Portfolio           | Value chart, recent trades                           |
| Retrograde Calendar | Budha/Shukra/Mangal vakri windows by year            |

## Commands

```bash
pip install -r requirements.txt
python main.py signals
python main.py backtest --ticker AAPL --start 2023-01-01 --end 2024-12-31
python main.py trade --paper
streamlit run dashboard.py
pytest tests/ -v
```

## Coding Conventions

- Type hints on all functions
- Dataclasses for structured data
- `Decimal` for monetary values, timezone-aware datetimes
- `logging` module, config as dependency injection, pure functions preferred
- Vedic Sanskrit terms used in code alongside English aliases for backward compatibility
