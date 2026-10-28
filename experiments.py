"""Reproduce every number and figure in the report:  python experiments.py
Outputs go to results/ (CSV) and results/figures/ (PNG)."""
import json
import statistics as st
from pathlib import Path
import pandas as pd
from scipy.stats import wilcoxon
from safeserve.data_gen import generate
from safeserve.simulator import run, METHODS

OUT = Path("results")
SEEDS = range(10)
CLIMATES = ["summer", "winter"]


def main_experiment():
    rows = []
    for clim in CLIMATES:
        for seed in SEEDS:
            sc = generate(seed)
            for m in METHODS:
                r = run(sc, m, clim)
                if seed == 0 and clim == "summer" and m == "SafeServe":
                    pd.DataFrame(r["log"]).to_csv(OUT / "sample_delivery_log_safeserve_summer_seed0.csv", index=False)
                r.pop("log")
                rows.append(r)
                print(clim, seed, m, round(r["safe_rate"], 3), flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "main_results_raw.csv", index=False)
    metrics = ["safe_rate", "perishable_safe_rate", "unsafe_share", "perishable_meals_lost",
               "mean_latency_min", "km_per_safe_meal", "jain_fairness", "mean_solve_s"]
    summ = df.groupby(["climate", "method"])[metrics].agg(["mean", "std"]).round(3)
    summ.to_csv(OUT / "main_results_summary.csv")
    tests = []
    for clim in CLIMATES:
        a = df[(df.climate == clim) & (df.method == "SafeServe")].sort_values("seed")
        for m in METHODS:
            if m == "SafeServe":
                continue
            b = df[(df.climate == clim) & (df.method == m)].sort_values("seed")
            diff = a.safe_rate.values - b.safe_rate.values
            p = wilcoxon(a.safe_rate.values, b.safe_rate.values).pvalue if any(diff != 0) else 1.0
            tests.append(dict(climate=clim, vs=m, mean_gain_pts=round(100 * diff.mean(), 1),
                              wins=int((diff > 0).sum()), p_value=round(p, 4)))
    pd.DataFrame(tests).to_csv(OUT / "significance_tests.csv", index=False)
    return df


def fleet_sensitivity():
    rows = []
    for tw, au in [(3, 1), (6, 2), (9, 3)]:
        for seed in range(5):
            sc = generate(seed, n_two_wheelers=tw, n_autos=au)
            for m in ["FCFS-Static", "FCFS-Adaptive", "SafeServe"]:
                r = run(sc, m, "summer"); r.pop("log")
                r["fleet"] = tw + au
                rows.append(r)
                print("fleet", tw + au, seed, m, flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "fleet_sensitivity.csv", index=False)
    return df


def hot_holding_policy():
    rows = []
    for boost in [0.0, 0.3]:
        for seed in range(5):
            sc = generate(seed, hot_held_share_boost=boost)
            r = run(sc, "SafeServe", "summer"); r.pop("log")
            r["hot_held_boost"] = boost
            rows.append(r)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "hot_holding_policy.csv", index=False)
    return df


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    main_experiment()
    fleet_sensitivity()
    hot_holding_policy()
    print("done")
