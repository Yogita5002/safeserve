"""Test cases for the report's 'test cases and results' appendix. Run:  pytest -v"""
import math
import pytest
from safeserve import config as C, safety as S
from safeserve.geo import haversine_km, travel_min
from safeserve.data_gen import generate, Donation, Recipient
from safeserve.matching import hungarian_assign, compatible
from safeserve.simulator import run


def mk(category="cooked_meal", storage="ambient", prep=15 * 60, veg=True, meals=20):
    return Donation(0, "restaurant", 13.04, 80.23, category, storage, veg, meals, prep, prep + 10)


# ---- geo -------------------------------------------------------------------
def test_haversine_known_distance():
    # T Nagar -> Adyar is roughly 5 km in a straight line
    assert 4.0 < haversine_km(13.0418, 80.2341, 13.0012, 80.2565) < 6.0


def test_travel_time_zero_for_same_point():
    assert travel_min((13.0, 80.2), (13.0, 80.2)) == 0


# ---- safety model (the novelty) ---------------------------------------------
def test_hot_afternoon_halves_window():
    assert S.ambient_window("cooked_meal", 14 * 60, "summer") == 60


def test_cool_morning_keeps_two_hours():
    assert S.ambient_window("cooked_meal", 4 * 60, "summer") == 120


def test_winter_afternoon_two_hours():
    assert S.ambient_window("cooked_meal", 14 * 60, "winter") == 120


def test_bakery_not_temperature_limited():
    assert S.ambient_window("bakery", 14 * 60, "summer") == 1440


def test_static_baseline_believes_four_hours():
    d = mk()
    assert S.static_expiry(d) - d.prep_time == 240


def test_late_delivery_is_unsafe():
    d = mk(prep=14 * 60)
    assert not S.is_safe_delivery(d, 14 * 60 + 20, 14 * 60 + 90, "summer")


def test_two_phase_clock_rejects_long_ride():
    d = mk(storage="hot_held", prep=13 * 60)  # 4 h storage cap, but ride limited to 60 min in heat
    assert S.is_safe_delivery(d, 15 * 60, 15 * 60 + 40, "summer")
    assert not S.is_safe_delivery(d, 15 * 60, 15 * 60 + 75, "summer")


# ---- matching ------------------------------------------------------------------
def test_veg_only_recipient_rejects_non_veg():
    r = Recipient(0, 13.04, 80.23, 100, True, 1.0)
    assert not compatible(mk(veg=False), r)


def test_hungarian_respects_capacity():
    sc = generate(3)
    now = 15 * 60
    pending = [d for d in sc.donations if d.announce_time <= now][:10]
    out = hungarian_assign(pending, sc.recipients, now, lambda d: S.true_limits(d, "winter"), sc.vehicles)
    load = {}
    for d in pending:
        if d.id in out:
            load[out[d.id].id] = load.get(out[d.id].id, 0) + d.meals
    for r in sc.recipients:
        assert load.get(r.id, 0) <= r.remaining


# ---- end-to-end -------------------------------------------------------------
@pytest.mark.parametrize("climate", ["summer", "winter"])
def test_safeserve_never_delivers_unsafe_food(climate):
    r = run(generate(0), "SafeServe", climate)
    assert r["unsafe_meals"] == 0


def test_status_quo_delivers_unsafe_food_in_summer():
    r = run(generate(0), "FCFS-Static", "summer")
    assert r["unsafe_meals"] > 0


def test_same_seed_is_reproducible():
    a = run(generate(7), "FCFS-Adaptive", "winter")
    b = run(generate(7), "FCFS-Adaptive", "winter")
    assert a["safe_meals"] == b["safe_meals"]


def test_recipient_capacity_never_exceeded():
    r = run(generate(2), "SafeServe", "summer")
    sc = generate(2)
    got = {}
    for row in r["log"]:
        got[row["recipient"]] = got.get(row["recipient"], 0) + row["meals"]
    for rec in sc.recipients:
        assert got.get(rec.id, 0) <= rec.capacity


# ---- intake validation --------------------------------------------------------
from safeserve.validate import check, is_duplicate


def test_valid_donation_accepted():
    assert check(mk()) == []


def test_out_of_area_rejected():
    d = mk(); d.lat = 19.07   # Mumbai
    assert "location outside service area" in check(d)


def test_duplicate_detected():
    a, b = mk(), mk()
    assert is_duplicate(b, [a])


def test_generated_data_passes_validation():
    sc = generate(5)
    assert all(check(d) == [] for d in sc.donations)
