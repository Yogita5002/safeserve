"""Stage 1: decide WHICH recipient gets each pending donation.

Cost of pairing donation d with recipient r (lower is better):

    cost(d, r) = t(d, r) * (1 + ALPHA * urgency(d)) + BETA * (1 - unmet_need(r))

  t(d, r)      travel minutes donor -> recipient (proximity)
  urgency(d)   1 - slack/120, clipped to [0, 1]; slack = minutes to spare if picked up now (safe window)
  unmet_need   share of recipient capacity still open, scaled by need weight (fairness / capacity)
  infeasible   veg-only recipient + non-veg food, too little capacity, or cannot arrive before expiry
               -> cost = BIG (food-type fit and the safety window are hard constraints, not soft weights)

Solved for all pending donations at once with the Hungarian algorithm
(scipy.optimize.linear_sum_assignment), which returns the minimum-total-cost one-to-one assignment.
Each recipient is split into "slots" so it can receive more than one donation per epoch.
"""
import numpy as np
from scipy.optimize import linear_sum_assignment
from . import config as C
from .geo import travel_min


def compatible(d, r):
    if r.veg_only and not d.is_veg:
        return False
    return r.remaining >= d.meals


def pair_cost(d, r, now, expiry, nearest_vehicle_min, max_need):
    if not compatible(d, r):
        return C.BIG
    t = travel_min(d.loc, r.loc)
    arrival = now + nearest_vehicle_min + C.SERVICE_MIN + t
    slack = expiry - arrival
    if slack < 0:
        return C.BIG
    urgency = 1.0 - min(1.0, slack / 120.0)
    unmet = (r.remaining / r.capacity) * (r.need_weight / max_need)
    return t * (1 + C.ALPHA_URGENCY * urgency) + C.BETA_NEED * (1 - unmet)


def hungarian_assign(pending, recipients, now, expiry_of, vehicles):
    """Return {donation_id: recipient} for donations that can be matched this epoch."""
    if not pending or not recipients:
        return {}
    max_need = max(r.need_weight for r in recipients)
    # slots: a recipient appears once per donation it could plausibly absorb
    slots = []
    for r in recipients:
        k = int(min(len(pending), max(0, r.remaining) // max(1, min(d.meals for d in pending))))
        slots += [r] * max(0, k)
    if not slots:
        return {}
    near = {d.id: min(travel_min(v.loc, d.loc) + max(0, v.free_at - now) for v in vehicles)
            for d in pending}
    cost = np.full((len(pending), len(slots)), C.BIG)
    cache = {}
    for i, d in enumerate(pending):
        for j, r in enumerate(slots):
            key = (d.id, r.id)
            if key not in cache:
                cache[key] = pair_cost(d, r, now, expiry_of(d), near[d.id], max_need)
            cost[i, j] = cache[key]
    rows, cols = linear_sum_assignment(cost)
    # repair pass: respect cumulative capacity, most urgent (earliest expiry) first
    chosen = sorted([(i, j) for i, j in zip(rows, cols) if cost[i, j] < C.BIG],
                    key=lambda ij: expiry_of(pending[ij[0]]))
    used = {r.id: 0 for r in recipients}
    out = {}
    for i, j in chosen:
        d, r = pending[i], slots[j]
        if used[r.id] + d.meals <= r.remaining:
            used[r.id] += d.meals
            out[d.id] = r
    return out


def nearest_assign(pending, recipients, now, expiry_of, vehicles):
    """Baseline/ablation: each donation (in arrival order) goes to the nearest compatible recipient."""
    used = {r.id: 0 for r in recipients}
    out = {}
    for d in sorted(pending, key=lambda x: x.announce_time):
        best, best_t = None, None
        for r in recipients:
            if (r.veg_only and not d.is_veg) or used[r.id] + d.meals > r.remaining:
                continue
            t = travel_min(d.loc, r.loc)
            if best_t is None or t < best_t:
                best, best_t = r, t
        if best is not None:
            used[best.id] += d.meals
            out[d.id] = best
    return out
