"""All tunable constants in one place, so the viva answer to 'where is X set?' is always this file."""
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Geography / travel
SPEED_KMPH = 20.0          # effective urban speed for a two-wheeler / auto in Chennai (assumption)
CIRCUITY = 1.35            # road distance ~= 1.35 x straight-line distance (assumption, typical urban value)
SERVICE_MIN = 5            # minutes spent at each pickup and each delivery

# Simulation clock (minutes after midnight)
SIM_START = 12 * 60        # 12:00
SIM_END = 26 * 60          # 02:00 next day (lets late-evening donations finish)
EPOCH_MIN = 20             # rolling-horizon re-optimisation interval

# Food
KG_PER_MEAL = 0.4
STATIC_WINDOW_MIN = 240    # the "under 4 hours" rule used by the status-quo baseline
HOT_THRESHOLD_C = 32.0     # USDA FSIS: above 90 F (32 C) the 2-hour limit becomes 1 hour

# Matching score weights (cost = minutes-equivalent)
ALPHA_URGENCY = 1.0        # how much urgency inflates travel time
BETA_NEED = 10.0           # minutes-equivalent bonus for recipients with more unmet need
BIG = 1e6                  # cost for an infeasible pair

# Solver
SOLVER_TIME_LIMIT_S = 0.25
PARTIAL_COMMIT = True       # commit only pickups starting this epoch; re-plan the rest
