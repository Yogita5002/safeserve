"""Stage 2: decide WHICH volunteer collects WHAT, in WHAT order.

Pickup-and-Delivery Problem with Time Windows (PDPTW), solved with Google OR-Tools.
Node layout:  0 = shared dummy end (routes are open: volunteers stop at their last drop)
              1..V = each vehicle's current position
              then a (pickup, delivery) node pair per donation.
Constraints:  pickup before delivery on the same vehicle; vehicle capacity in kg;
              pickup window [ready, expiry - drive - service]; delivery by expiry;
              optional max ride time (two-phase safety clock for hot-held / chilled food).
Objective:    minimise total drive minutes + penalties for donations left undelivered
              (penalty grows with meals and urgency, so the solver prefers saving more food).
"""
import math
from ortools.constraint_solver import pywrapcp, routing_enums_pb2
from . import config as C
from .geo import time_matrix, road_km


def solve_pdptw(jobs, vehicles, now, time_limit_s=C.SOLVER_TIME_LIMIT_S):
    """jobs: list of dicts {d, r, expiry, ride_max (or None), urgency}.
    Returns list of (vehicle, [(job, pickup_min, delivery_min), ...]) for vehicles with work."""
    if not jobs or not vehicles:
        return []
    V = len(vehicles)
    pts = [(0.0, 0.0)] + [v.loc for v in vehicles]
    for j in jobs:
        pts += [j["d"].loc, j["r"].loc]
    T = time_matrix(pts)
    T[:, 0] = 0          # free to "end" anywhere
    T[0, :] = 10 ** 5    # never leave the dummy node
    n = len(pts)
    starts = list(range(1, V + 1))
    mgr = pywrapcp.RoutingIndexManager(n, V, starts, [0] * V)
    rt = pywrapcp.RoutingModel(mgr)

    def transit(i, j):
        a, b = mgr.IndexToNode(i), mgr.IndexToNode(j)
        service = C.SERVICE_MIN if a > V else 0
        return int(T[a, b] + service) if b != 0 else 0

    cb = rt.RegisterTransitCallback(transit)
    rt.SetArcCostEvaluatorOfAllVehicles(cb)
    horizon = C.SIM_END + 24 * 60
    rt.AddDimension(cb, 24 * 60, horizon, False, "Time")
    time = rt.GetDimensionOrDie("Time")

    def demand(i):
        node = mgr.IndexToNode(i)
        if node <= V:
            return 0
        k, is_pick = divmod(node - V - 1, 2)
        kg = int(math.ceil(jobs[k]["d"].kg))
        return kg if is_pick == 0 else -kg

    dcb = rt.RegisterUnaryTransitCallback(demand)
    rt.AddDimensionWithVehicleCapacity(dcb, 0, [int(v.cap_kg) for v in vehicles], True, "Load")

    for k, v in enumerate(vehicles):
        time.CumulVar(rt.Start(k)).SetRange(max(now, v.free_at), max(now, v.free_at))

    solver = rt.solver()
    for k, j in enumerate(jobs):
        p = mgr.NodeToIndex(V + 1 + 2 * k)
        q = mgr.NodeToIndex(V + 2 + 2 * k)
        drive = int(T[V + 1 + 2 * k, V + 2 + 2 * k])
        ready = max(now, j["d"].announce_time)
        latest_pick = int(j["expiry"] - drive - C.SERVICE_MIN)
        if latest_pick < ready:
            latest_pick = ready  # will be dropped by the delivery window if truly infeasible
        time.CumulVar(p).SetRange(ready, latest_pick)
        time.CumulVar(q).SetRange(ready, int(j["expiry"]))
        rt.AddPickupAndDelivery(p, q)
        solver.Add(rt.VehicleVar(p) == rt.VehicleVar(q))
        solver.Add(time.CumulVar(p) <= time.CumulVar(q))
        if j.get("ride_max") is not None:
            solver.Add(time.CumulVar(q) - time.CumulVar(p) <= int(j["ride_max"]))
        penalty = int(1000 + 50 * j["d"].meals * (1 + j["urgency"]))
        rt.AddDisjunction([p], penalty)
        rt.AddDisjunction([q], penalty)
        solver.Add(rt.ActiveVar(p) == rt.ActiveVar(q))

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.FromMilliseconds(int(time_limit_s * 1000))
    sol = rt.SolveWithParameters(params)
    if sol is None:
        return []

    plans = []
    for k, v in enumerate(vehicles):
        idx = rt.Start(k)
        picks, stops = {}, []
        idx = sol.Value(rt.NextVar(idx))
        while not rt.IsEnd(idx):
            node = mgr.IndexToNode(idx)
            jk, is_pick = divmod(node - V - 1, 2)
            t = sol.Min(time.CumulVar(idx))
            if is_pick == 0:
                picks[jk] = t
            else:
                stops.append((jobs[jk], picks[jk], t))
            idx = sol.Value(rt.NextVar(idx))
        if stops:
            plans.append((v, stops))
    return plans


def route_km(vehicle, stops):
    """Distance driven for a committed plan (vehicle start -> pickups/deliveries in time order)."""
    events = []
    for job, tp, tq in stops:
        events += [(tp, job["d"].loc), (tq, job["r"].loc)]
    events.sort(key=lambda e: e[0])
    km, cur = 0.0, vehicle.loc
    for _, loc in events:
        km += road_km(cur, loc)
        cur = loc
    return km, cur
