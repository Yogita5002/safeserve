"""Synthetic but realistic scenario generator on real Chennai coordinates.

No public dataset of donor-to-recipient food transactions exists, so donations, recipients and
volunteers are generated around real neighbourhood centroids with documented distributions.
Every random draw goes through one seeded numpy Generator, so a seed reproduces a scenario exactly.
"""
import csv
from dataclasses import dataclass, field
import numpy as np
from . import config as C

# donor type -> (share, category, meals range, P(storage=ambient), other storage)
DONOR_TYPES = {
    "restaurant":  (0.35, "cooked_meal",   (10, 40),  0.70, "hot_held"),
    "canteen":     (0.20, "cooked_meal",   (30, 120), 0.60, "hot_held"),
    "event_hall":  (0.10, "cooked_meal",   (80, 250), 0.50, "hot_held"),
    "bakery":      (0.12, "bakery",        (10, 40),  1.00, "ambient"),
    "sweet_shop":  (0.10, "dairy_sweet",   (10, 40),  0.50, "chilled"),
    "grocery":     (0.13, "whole_produce", (20, 80),  1.00, "ambient"),
}


@dataclass
class Donation:
    id: int
    donor_type: str
    lat: float
    lon: float
    category: str
    storage: str          # ambient | hot_held | chilled
    is_veg: bool
    meals: int
    prep_time: int        # minute food was cooked / taken out of storage
    announce_time: int    # minute the donor posted it on the platform

    @property
    def kg(self):
        return self.meals * C.KG_PER_MEAL

    @property
    def loc(self):
        return (self.lat, self.lon)


@dataclass
class Recipient:
    id: int
    lat: float
    lon: float
    capacity: int         # meals it can use today
    veg_only: bool
    need_weight: float    # relative number of people served
    received: int = 0

    @property
    def loc(self):
        return (self.lat, self.lon)

    @property
    def remaining(self):
        return self.capacity - self.received


@dataclass
class Vehicle:
    id: int
    kind: str
    lat: float
    lon: float
    cap_kg: float
    free_at: int = C.SIM_START
    km: float = 0.0

    @property
    def loc(self):
        return (self.lat, self.lon)


def load_zones():
    with open(C.DATA_DIR / "chennai_zones.csv", newline="") as f:
        return [(r["zone"], float(r["lat"]), float(r["lon"])) for r in csv.DictReader(f)]


def _jitter(rng, lat, lon, km=1.2):
    # ~1 km of spread around a neighbourhood centroid
    return lat + rng.normal(0, km / 111.0), lon + rng.normal(0, km / 108.0)


@dataclass
class Scenario:
    donations: list
    recipients: list
    vehicles: list
    seed: int
    meta: dict = field(default_factory=dict)


def generate(seed=0, n_donations=45, n_recipients=15, n_two_wheelers=6, n_autos=2,
             hot_held_share_boost=0.0):
    rng = np.random.default_rng(seed)
    zones = load_zones()
    types = list(DONOR_TYPES)
    shares = np.array([DONOR_TYPES[t][0] for t in types])
    shares = shares / shares.sum()

    donations = []
    for i in range(n_donations):
        t = types[rng.choice(len(types), p=shares)]
        _, cat, (lo, hi), p_amb, other = DONOR_TYPES[t]
        p_amb = max(0.0, p_amb - hot_held_share_boost) if other != "ambient" else p_amb
        storage = "ambient" if rng.random() < p_amb else other
        z = zones[rng.integers(len(zones))]
        lat, lon = _jitter(rng, z[1], z[2])
        # two surplus waves: after lunch (~15:00) and after dinner (~22:00)
        if rng.random() < 0.55:
            ann = rng.normal(15 * 60, 45)
        else:
            ann = rng.normal(22 * 60, 40)
        ann = int(np.clip(ann, 12 * 60 + 30, 23 * 60 + 30))
        prep = ann - int(rng.integers(5, 41))          # surplus noticed 5-40 min after cooking
        is_veg = True if cat != "cooked_meal" else bool(rng.random() < 0.6)
        donations.append(Donation(i, t, lat, lon, cat, storage, is_veg,
                                  int(rng.integers(lo, hi + 1)), prep, ann))

    recipients = []
    for j in range(n_recipients):
        z = zones[rng.integers(len(zones))]
        lat, lon = _jitter(rng, z[1], z[2])
        recipients.append(Recipient(j, lat, lon, int(rng.integers(80, 301)),
                                    bool(rng.random() < 0.25), float(rng.uniform(0.5, 1.5))))

    vehicles = []
    for k in range(n_two_wheelers + n_autos):
        z = zones[rng.integers(len(zones))]
        lat, lon = _jitter(rng, z[1], z[2])
        kind = "two_wheeler" if k < n_two_wheelers else "auto"
        vehicles.append(Vehicle(k, kind, lat, lon, 30.0 if kind == "two_wheeler" else 120.0))

    return Scenario(donations, recipients, vehicles, seed)
