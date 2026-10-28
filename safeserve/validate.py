"""Intake validation: what the donor form enforces before a donation enters the pool."""
from . import safety as S

LAT_RANGE = (12.80, 13.25)   # Chennai metropolitan bounding box (approx.)
LON_RANGE = (80.00, 80.35)
STORAGES = {"ambient", "hot_held", "chilled"}


def check(d):
    """Return a list of problems; empty list = accept."""
    errs = []
    if d.category not in S.RULES:
        errs.append("unknown food category")
    if d.storage not in STORAGES:
        errs.append("unknown storage condition")
    if d.prep_time is None or d.announce_time is None:
        errs.append("missing prep or announce time")
    elif d.prep_time > d.announce_time:
        errs.append("prep time after announce time")
    if not (1 <= d.meals <= 500):
        errs.append("meals out of range 1-500")
    if not (LAT_RANGE[0] <= d.lat <= LAT_RANGE[1] and LON_RANGE[0] <= d.lon <= LON_RANGE[1]):
        errs.append("location outside service area")
    return errs


def is_duplicate(d, accepted, minutes=10, metres=150):
    """Same category, posted within 10 min, from within ~150 m of an accepted donation."""
    for a in accepted:
        if (a.category == d.category and abs(a.announce_time - d.announce_time) <= minutes
                and abs(a.lat - d.lat) * 111000 < metres and abs(a.lon - d.lon) * 108000 < metres):
            return True
    return False
