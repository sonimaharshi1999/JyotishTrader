from __future__ import annotations

import datetime
import math
from dataclasses import dataclass
from enum import Enum

import ephem as _ephem

# Lahiri Ayanamsa calculation constants (IAU standard)
_AYANAMSA_J2000 = 23.85
_AYANAMSA_RATE = 50.29 / 3600  # arcseconds per year → degrees per year
_J2000_EPOCH = datetime.datetime(2000, 1, 1, 12, 0, tzinfo=datetime.timezone.utc)

# Mean ascending node constants (J2000.0)
_NODE_J2000 = 125.0445
_NODE_DAILY_RATE = -0.0529539  # degrees per day (retrograde)

RASHI_NAMES = [
    "Mesha", "Vrishabha", "Mithuna", "Karka",
    "Simha", "Kanya", "Tula", "Vrischika",
    "Dhanu", "Makara", "Kumbha", "Meena",
]

RASHI_NAMES_EN = [
    "Aries", "Taurus", "Gemini", "Cancer",
    "Leo", "Virgo", "Libra", "Scorpio",
    "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]


class Graha(Enum):
    SURYA = "Sun"
    CHANDRA = "Moon"
    MANGAL = "Mars"
    BUDHA = "Mercury"
    GURU = "Jupiter"
    SHUKRA = "Venus"
    SHANI = "Saturn"
    RAHU = "Rahu"
    KETU = "Ketu"


Planet = Graha

GRAHA_NAMES: dict[Graha, str] = {
    Graha.SURYA: "Surya (Sun)",
    Graha.CHANDRA: "Chandra (Moon)",
    Graha.MANGAL: "Mangal (Mars)",
    Graha.BUDHA: "Budha (Mercury)",
    Graha.GURU: "Guru (Jupiter)",
    Graha.SHUKRA: "Shukra (Venus)",
    Graha.SHANI: "Shani (Saturn)",
    Graha.RAHU: "Rahu",
    Graha.KETU: "Ketu",
}

_EPHEM_BODIES: dict[Graha, type] = {
    Graha.SURYA: _ephem.Sun,
    Graha.CHANDRA: _ephem.Moon,
    Graha.MANGAL: _ephem.Mars,
    Graha.BUDHA: _ephem.Mercury,
    Graha.GURU: _ephem.Jupiter,
    Graha.SHUKRA: _ephem.Venus,
    Graha.SHANI: _ephem.Saturn,
}


@dataclass(frozen=True)
class GrahaPosition:
    graha: Graha
    longitude: float
    latitude: float
    speed: float
    rashi_index: int
    rashi: str
    rashi_en: str
    degree_in_rashi: float

    @property
    def is_retrograde(self) -> bool:
        return self.speed < 0

    @property
    def is_vakri(self) -> bool:
        return self.is_retrograde

    @property
    def nakshatra_index(self) -> int:
        return int(self.longitude / (360 / 27))

    @property
    def nakshatra_pada(self) -> int:
        nak_span = 360 / 27
        pos_in_nak = self.longitude % nak_span
        return int(pos_in_nak / (nak_span / 4)) + 1

    @property
    def sign(self) -> str:
        return self.rashi_en

    @property
    def sign_degree(self) -> float:
        return self.degree_in_rashi


PlanetPosition = GrahaPosition


def _dt_to_ephem_date(dt: datetime.datetime) -> _ephem.Date:
    utc = dt.astimezone(datetime.timezone.utc)
    return _ephem.Date(utc.strftime("%Y/%m/%d %H:%M:%S"))


def get_ayanamsa(dt: datetime.datetime) -> float:
    utc = dt.astimezone(datetime.timezone.utc)
    years_from_j2000 = (utc - _J2000_EPOCH).total_seconds() / (365.25 * 86400)
    return _AYANAMSA_J2000 + _AYANAMSA_RATE * years_from_j2000


def _tropical_ecliptic_lon(body, edate: _ephem.Date) -> tuple[float, float]:
    body.compute(edate)
    eq = _ephem.Equatorial(body.ra, body.dec, epoch=edate)
    ec = _ephem.Ecliptic(eq)
    lon_deg = float(ec.lon) * 180 / math.pi
    lat_deg = float(ec.lat) * 180 / math.pi
    return lon_deg, lat_deg


def _compute_speed(graha: Graha, dt: datetime.datetime) -> float:
    """Speed in degrees/day via finite difference."""
    dt1 = dt
    dt2 = dt + datetime.timedelta(days=1)
    edate1 = _dt_to_ephem_date(dt1)
    edate2 = _dt_to_ephem_date(dt2)
    ayanamsa1 = get_ayanamsa(dt1)
    ayanamsa2 = get_ayanamsa(dt2)

    if graha == Graha.RAHU:
        lon1 = _mean_node_longitude(dt1)
        lon2 = _mean_node_longitude(dt2)
    elif graha == Graha.KETU:
        lon1 = (_mean_node_longitude(dt1) + 180) % 360
        lon2 = (_mean_node_longitude(dt2) + 180) % 360
    else:
        body_cls = _EPHEM_BODIES[graha]
        b1 = body_cls()
        lon1_trop, _ = _tropical_ecliptic_lon(b1, edate1)
        lon1 = (lon1_trop - ayanamsa1) % 360

        b2 = body_cls()
        lon2_trop, _ = _tropical_ecliptic_lon(b2, edate2)
        lon2 = (lon2_trop - ayanamsa2) % 360

    speed = lon2 - lon1
    if speed > 180:
        speed -= 360
    if speed < -180:
        speed += 360
    return speed


def _mean_node_longitude(dt: datetime.datetime) -> float:
    utc = dt.astimezone(datetime.timezone.utc)
    days_from_j2000 = (utc - _J2000_EPOCH).total_seconds() / 86400
    return (_NODE_J2000 + _NODE_DAILY_RATE * days_from_j2000) % 360


def get_graha_position(graha: Graha, dt: datetime.datetime) -> GrahaPosition:
    edate = _dt_to_ephem_date(dt)
    ayanamsa = get_ayanamsa(dt)

    if graha == Graha.RAHU:
        trop_lon = _mean_node_longitude(dt) + ayanamsa  # node is already ~sidereal
        sid_lon = _mean_node_longitude(dt)
        lat = 0.0
        speed = _NODE_DAILY_RATE
    elif graha == Graha.KETU:
        sid_lon = (_mean_node_longitude(dt) + 180) % 360
        lat = 0.0
        speed = _NODE_DAILY_RATE
    else:
        body = _EPHEM_BODIES[graha]()
        trop_lon, lat = _tropical_ecliptic_lon(body, edate)
        sid_lon = (trop_lon - ayanamsa) % 360
        speed = _compute_speed(graha, dt)

    rashi_idx = int(sid_lon // 30)
    return GrahaPosition(
        graha=graha,
        longitude=sid_lon,
        latitude=lat,
        speed=speed,
        rashi_index=rashi_idx,
        rashi=RASHI_NAMES[rashi_idx],
        rashi_en=RASHI_NAMES_EN[rashi_idx],
        degree_in_rashi=sid_lon % 30,
    )


get_planet_position = get_graha_position


def get_all_positions(dt: datetime.datetime) -> dict[Graha, GrahaPosition]:
    return {g: get_graha_position(g, dt) for g in Graha}
