"""Rolling-horizon simulator: every EPOCH_MIN minutes, look at what has been posted, plan, commit.

Four methods form a 2 x 2 design so each idea's effect can be isolated:

                          static 4-hour window      temperature-adaptive window
  greedy (FCFS-nearest)   FCFS-Static (status quo)  FCFS-Adaptive
  optimised (Hung.+PDPTW) Opt-Static                SafeServe (proposed)

Plus an ablation, SafeServe-NoHungarian, that keeps adaptive windows + PDPTW but assigns each
donation to its nearest recipient, to measure what the Hungarian stage adds.

Every method's deliveries are judged by the SAME ground-truth rule (safety.is_safe_delivery).
"""
import copy
import time as _time
from . import config as C
from . import safety as S
from .geo import travel_min, road_km
from .matching import hungarian_assign, nearest_assign
from .routing import solve_pdptw, route_km

METHODS = ["FCFS-Static", "FCFS-Adaptive", "Opt-Static", "SafeServe", "SafeServe-NoHungarian"]


def _believed_expiry(d, adaptive, climate):
    return S.true_limits(d, climate) if adaptive else S.static_expiry(d)


def _ride_max(d, adaptive, at_min, climate):
    if not adaptive:
        return None
    r = S.RULES[d.category]
    if r.perishable and d.storage != "ambient":
        return S.ambient_window(d.category, at_min, climate)
    return None


def run(scenario, method, climate):
    sc = copy.deepcopy(scenario)
    adaptive = method in ("FCFS-Adaptive", "SafeServe", "SafeServe-NoHungarian")
    optimised = method in ("Opt-Static", "SafeServe", "SafeServe-NoHungarian")
    use_hungarian = method in ("Opt-Static", "SafeServe")
    exp = lambda d: _believed_expiry(d, adaptive, climate)

    pending, done, dropped = [], [], []
    queue = sorted(sc.donations, key=lambda d: d.announce_time)
    solve_times = []
    now = C.SIM_START
    while now <= C.SIM_END:
        while queue and queue[0].announce_time <= now:
            pending.append(queue.pop(0))
        # drop what the method itself believes can no longer be delivered in time
        keep = []
        for d in pending:
            (dropped if now > exp(d) else keep).append(d)
        pending = keep

        if pending:
            t0 = _time.perf_counter()
            if optimised:
                idle = [v for v in sc.vehicles if v.free_at < now + C.EPOCH_MIN]
                assign = (hungarian_assign if use_hungarian else nearest_assign)(
                    pending, sc.recipients, now, exp, idle or sc.vehicles)
                jobs = []
                for d in pending:
                    if d.id in assign:
                        slack = exp(d) - now
                        jobs.append({"d": d, "r": assign[d.id], "expiry": exp(d),
                                     "ride_max": _ride_max(d, adaptive, now, climate),
                                     "urgency": 1 - min(1.0, max(0.0, slack) / 240.0)})
                plans = solve_pdptw(jobs, idle, now)
                for v, stops in plans:
                    # commit only pairs whose pickup starts this epoch; the rest are re-planned next time
                    if C.PARTIAL_COMMIT:
                        stops = [s for s in stops if s[1] < now + C.EPOCH_MIN] or stops[:1]
                    km, end_loc = route_km(v, stops)
                    v.km += km
                    v.lat, v.lon = end_loc
                    v.free_at = max(tq for _, _, tq in stops) + C.SERVICE_MIN
                    for job, tp, tq in stops:
                        job["r"].received += job["d"].meals
                        done.append((job["d"], job["r"], tp, tq))
                        pending.remove(job["d"])
            else:
                for d in sorted(list(pending), key=lambda x: x.announce_time):
                    idle = [v for v in sc.vehicles if v.free_at <= now and v.cap_kg >= d.kg]
                    rmap = nearest_assign([d], sc.recipients, now, exp, sc.vehicles)
                    if not idle or d.id not in rmap:
                        continue
                    r = rmap[d.id]
                    v = min(idle, key=lambda v: travel_min(v.loc, d.loc))
                    tp = now + travel_min(v.loc, d.loc)
                    tq = tp + C.SERVICE_MIN + travel_min(d.loc, r.loc)
                    rm = _ride_max(d, adaptive, tp, climate)
                    if tq > exp(d) or (rm is not None and tq - tp > rm):
                        continue  # method believes it cannot make it with this vehicle now
                    v.km += road_km(v.loc, d.loc) + road_km(d.loc, r.loc)
                    v.lat, v.lon = r.loc
                    v.free_at = int(tq + C.SERVICE_MIN)
                    r.received += d.meals
                    done.append((d, r, tp, tq))
                    pending.remove(d)
            solve_times.append(_time.perf_counter() - t0)
        now += C.EPOCH_MIN

    return summarise(sc, method, climate, done, dropped + pending, solve_times)


def jain(xs):
    xs = [x for x in xs]
    s, s2 = sum(xs), sum(x * x for x in xs)
    return (s * s) / (len(xs) * s2) if s2 > 0 else 0.0


def summarise(sc, method, climate, done, not_done, solve_times):
    offered = sum(d.meals for d in sc.donations)
    perishable_offered = sum(d.meals for d in sc.donations if S.RULES[d.category].perishable)
    safe = unsafe = 0
    lat = []
    log = []
    for d, r, tp, tq in done:
        ok = S.is_safe_delivery(d, tp, tq, climate)
        safe += d.meals if ok else 0
        unsafe += 0 if ok else d.meals
        if S.RULES[d.category].perishable:
            lat.append(tq - d.announce_time)
        log.append(dict(donation=d.id, recipient=r.id, category=d.category, storage=d.storage,
                        meals=d.meals, prep=d.prep_time, announce=d.announce_time,
                        pickup=round(tp), delivery=round(tq), safe=ok))
    lost = sum(d.meals for d in not_done if S.RULES[d.category].perishable)
    km = sum(v.km for v in sc.vehicles)
    # fairness counts only SAFE meals: unsafe food must not inflate a method's fairness score
    safe_got = {r.id: 0 for r in sc.recipients}
    for d, r, tp, tq in done:
        if S.is_safe_delivery(d, tp, tq, climate):
            safe_got[r.id] += d.meals
    per_need = [safe_got[r.id] / r.need_weight for r in sc.recipients]
    return dict(
        method=method, climate=climate, seed=sc.seed,
        meals_offered=offered,
        safe_meals=safe,
        unsafe_meals=unsafe,
        safe_rate=safe / offered,
        perishable_safe_rate=(sum(d.meals for d, r, tp, tq in done
                                  if S.RULES[d.category].perishable and S.is_safe_delivery(d, tp, tq, climate))
                              / perishable_offered) if perishable_offered else 0.0,
        unsafe_share=unsafe / (safe + unsafe) if (safe + unsafe) else 0.0,
        perishable_meals_lost=lost,
        mean_latency_min=sum(lat) / len(lat) if lat else float("nan"),
        km_per_safe_meal=km / safe if safe else float("nan"),
        jain_fairness=jain(per_need),
        mean_solve_s=sum(solve_times) / len(solve_times) if solve_times else 0.0,
        log=log,
    )
