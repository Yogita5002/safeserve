"""Safe-window model: the novelty of the project.

Two ideas:
1. Temperature-adaptive window: ambient-held perishables get 120 min below/at 32 C and 60 min above
   (USDA FSIS 2-hour / 1-hour rule). The temperature used is the hottest hour in the 2 h after the
   clock starts, which is the conservative choice.
2. Two-phase safety clock: food kept hot (>=60 C) or chilled (<=5 C) at the donor has a longer
   storage-phase cap, but once it leaves on an uninsulated two-wheeler the ambient clock starts again,
   so delivery - pickup must also fit inside the ambient window ("max ride time").
"""
import csv
import math
from dataclasses import dataclass
from . import config as C


@dataclass(frozen=True)
class Rule:
    category: str
    perishable: bool
    amb_cool: int
    amb_hot: int
    controlled_cap: int


def load_rules(path=C.DATA_DIR / "safe_window_rules.csv"):
    rules = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            rules[row["category"]] = Rule(row["category"], row["perishable"] == "1",
                                          int(row["window_ambient_le32_min"]),
                                          int(row["window_ambient_gt32_min"]),
                                          int(row["controlled_storage_cap_min"]))
    return rules


RULES = load_rules()

# Hourly ambient-temperature profiles for Chennai (approximate climatology; swap in Open-Meteo/IMD data).
CLIMATE = {
    "summer": (32.5, 4.5),   # mean, amplitude  -> ~37 C at 15:00, ~28 C at 03:00 (May-like)
    "winter": (26.0, 4.0),   # -> ~30 C at 15:00, ~22 C at 03:00 (January-like)
}


def ambient_temp(minute, climate):
    """Ambient temperature (C) at a clock minute using a daily cosine profile peaking at 15:00."""
    mean, amp = CLIMATE[climate]
    hour = (minute / 60.0) % 24
    return mean + amp * math.cos(2 * math.pi * (hour - 15) / 24)


def max_temp(start_min, climate, span_min=120, step=10):
    return max(ambient_temp(start_min + s, climate) for s in range(0, span_min + 1, step))


def ambient_window(category, start_min, climate):
    """Minutes food of this category may stay at ambient temperature, starting at start_min."""
    r = RULES[category]
    if not r.perishable:
        return r.amb_cool
    return r.amb_hot if max_temp(start_min, climate) > C.HOT_THRESHOLD_C else r.amb_cool


def true_limits(d, climate):
    """Ground-truth safety limits for a donation.

    Returns (expiry_minute, ride_limit_min or None). ride_limit is checked against the actual
    pickup time later, so here we only return the storage-phase expiry.
    """
    r = RULES[d.category]
    if d.storage == "ambient" or not r.perishable:
        return d.prep_time + ambient_window(d.category, d.prep_time, climate)
    return d.prep_time + r.controlled_cap


def static_expiry(d):
    """What a status-quo system believes: every perishable is fine for 4 hours."""
    r = RULES[d.category]
    if not r.perishable:
        return d.prep_time + r.amb_cool
    return d.prep_time + C.STATIC_WINDOW_MIN


def is_safe_delivery(d, pickup_min, delivery_min, climate):
    """Ground-truth check applied to EVERY method's deliveries, so the comparison is fair."""
    if delivery_min > true_limits(d, climate):
        return False
    r = RULES[d.category]
    if r.perishable and d.storage != "ambient":
        if delivery_min - pickup_min > ambient_window(d.category, pickup_min, climate):
            return False
    return True
