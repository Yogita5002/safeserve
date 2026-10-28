# SafeServe — temperature-adaptive food redistribution

**Team:** Charitha Sri, Yogita Y V, Lahari Y · SRM Institute of Science and Technology · 21CSC402P Report Writing

SafeServe matches surplus food to recipients and routes volunteers so that cooked food is delivered
inside its *temperature-dependent* safe window (USDA FSIS: 2 h, or 1 h above 32 °C; FSSAI 2019
surplus-food regulations).

## Quick start (macOS / Linux)
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    python -m pytest -v
    python -m streamlit run app.py

To regenerate results (about 6 min) and figures:

    python experiments.py
    python make_figures.py

Note: OR-Tools stops at a 0.25 s time limit per epoch, so optimised results can differ by a few tenths of a point between runs.

## Layout
    safeserve/config.py      all assumptions (speed, circuity, 32 C threshold, epoch, weights)
    safeserve/safety.py      safe-window engine + ground-truth safety check   <- novelty
    safeserve/data_gen.py    seeded synthetic scenario on real Chennai coordinates
    safeserve/validate.py    intake validation and duplicate detection
    safeserve/geo.py         haversine distance and travel-time matrix
    safeserve/matching.py    Hungarian assignment (scipy) + nearest baseline
    safeserve/routing.py     OR-Tools pickup-and-delivery with time windows + ride-time limit
    safeserve/simulator.py   20-minute rolling horizon, 5 methods, metrics
    data/                    safe_window_rules.csv (with sources), chennai_zones.csv
    results/                 CSVs, significance tests, test report, figures
    tests/                   pytest suite (20 tests)

## Methods compared
| | static 4-h window | temperature-adaptive window |
|---|---|---|
| greedy first-come nearest | FCFS-Static (status quo) | FCFS-Adaptive |
| Hungarian + OR-Tools PDPTW | Opt-Static | **SafeServe** |
Ablation: SafeServe-NoHungarian (nearest recipient + PDPTW).

## Honest scope
Synthetic donations, a calibrated cosine temperature profile, and haversine x 1.35 travel times.
Replace with Open-Meteo/IMD temperatures and OSRM road times for a field version.
