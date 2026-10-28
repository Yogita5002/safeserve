"""Draw report figures from results/*.csv:  python make_figures.py"""
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

R, F = "results/", "results/figures/"
ORDER = ["FCFS-Static", "Opt-Static", "FCFS-Adaptive", "SafeServe-NoHungarian", "SafeServe"]
df = pd.read_csv(R + "main_results_raw.csv")
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})

# Fig 1: safe vs unsafe meals per method and climate
fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
for ax, clim in zip(axes, ["summer", "winter"]):
    g = df[df.climate == clim].groupby("method")[["safe_meals", "unsafe_meals"]].mean().reindex(ORDER)
    ax.bar(g.index, g.safe_meals, color="#2e8b57", label="Safe meals delivered")
    ax.bar(g.index, g.unsafe_meals, bottom=g.safe_meals, color="#d9534f", label="Unsafe meals delivered")
    ax.set_title(f"{clim.title()} (mean of 10 scenario-days)")
    ax.tick_params(axis="x", rotation=30)
axes[0].set_ylabel("Meals per day"); axes[0].legend(frameon=False)
fig.tight_layout(); fig.savefig(F + "fig1_safe_vs_unsafe.png", dpi=200)

# Fig 2: safe-delivery rate with spread
fig, ax = plt.subplots(figsize=(8, 4))
for i, clim in enumerate(["summer", "winter"]):
    g = df[df.climate == clim].groupby("method").safe_rate
    m, s = g.mean().reindex(ORDER), g.std().reindex(ORDER)
    x = [j + (i - 0.5) * 0.35 for j in range(len(ORDER))]
    ax.bar(x, m * 100, 0.35, yerr=s * 100, capsize=3, label=clim.title(),
           color="#e07b39" if clim == "summer" else "#3b7dd8")
ax.set_xticks(range(len(ORDER))); ax.set_xticklabels(ORDER, rotation=20)
ax.set_ylabel("Safe meals / meals offered (%)"); ax.legend(frameon=False)
fig.tight_layout(); fig.savefig(F + "fig2_safe_rate.png", dpi=200)

# Fig 3: efficiency and fairness
fig, axes = plt.subplots(1, 2, figsize=(11, 4))
for ax, k, lab in zip(axes, ["km_per_safe_meal", "jain_fairness"], ["Km driven per safe meal (lower is better)",
                                                                    "Jain fairness index (higher is better)"]):
    g = df.groupby(["method", "climate"])[k].mean().unstack().reindex(ORDER)
    g.plot.bar(ax=ax, color=["#e07b39", "#3b7dd8"], rot=20)
    ax.set_title(lab); ax.set_xlabel(""); ax.legend(frameon=False)
fig.tight_layout(); fig.savefig(F + "fig3_efficiency_fairness.png", dpi=200)

# Fig 4: fleet sensitivity
f = pd.read_csv(R + "fleet_sensitivity.csv")
fig, ax = plt.subplots(figsize=(6, 4))
for m, c in [("FCFS-Static", "#d9534f"), ("FCFS-Adaptive", "#888888"), ("SafeServe", "#2e8b57")]:
    g = f[f.method == m].groupby("fleet").safe_rate.mean() * 100
    ax.plot(g.index, g.values, marker="o", color=c, label=m)
ax.set_xlabel("Volunteer vehicles"); ax.set_ylabel("Safe-delivery rate (%)"); ax.set_title("Summer, 5 seeds")
ax.legend(frameon=False); fig.tight_layout(); fig.savefig(F + "fig4_fleet_sensitivity.png", dpi=200)

# Fig 5: temperature profile and safe window
from safeserve import safety as S
hrs = [h / 2 for h in range(24, 49)]
fig, ax = plt.subplots(figsize=(7, 3.5))
for clim, c in [("summer", "#e07b39"), ("winter", "#3b7dd8")]:
    ax.plot(hrs, [S.ambient_temp(h * 60, clim) for h in hrs], color=c, label=clim.title())
ax.axhline(32, ls="--", color="k", lw=1); ax.text(12.2, 32.3, "32 °C: window drops 120 → 60 min", fontsize=9)
ax.set_xlabel("Hour of day"); ax.set_ylabel("Ambient °C"); ax.legend(frameon=False)
fig.tight_layout(); fig.savefig(F + "fig5_temperature_threshold.png", dpi=200)
print("figures written")
