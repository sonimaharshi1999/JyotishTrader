from __future__ import annotations

import csv
import datetime
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CompanyInfo:
    ticker: str
    incorporation_date: datetime.date
    incorporation_location: str
    sector: str


def load_companies(csv_path: Path | str) -> dict[str, CompanyInfo]:
    csv_path = Path(csv_path)
    companies: dict[str, CompanyInfo] = {}
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ticker = row["ticker"].strip().upper()
            companies[ticker] = CompanyInfo(
                ticker=ticker,
                incorporation_date=datetime.date.fromisoformat(row["incorporation_date"].strip()),
                incorporation_location=row["incorporation_location"].strip(),
                sector=row["sector"].strip(),
            )
    return companies
