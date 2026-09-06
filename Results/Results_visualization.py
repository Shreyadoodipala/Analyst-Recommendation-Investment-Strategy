""" Results visualization script. """

import pandas as pd
import matplotlib.pyplot as plt
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

df_wout_costs = pd.read_csv(PROJECT_ROOT / 'outputs' / 'grid_search_results.csv')
df_with_costs = pd.read_csv(PROJECT_ROOT / 'outputs' / 'grid_search_results_with_costs.csv')

# ## Sigma Prior


# Calculate average Sharpe ratios by sigma_prior
avg_sharpe_sigma = pd.DataFrame({
    "Without costs": df_wout_costs.groupby("sigma_prior")["sharpe"].mean(),
    "With costs": df_with_costs.groupby("sigma_prior")["sharpe"].mean(),
}).sort_index()

# Create stacked column chart
ax = avg_sharpe_sigma.plot(
    kind="bar",
    stacked=False,
    figsize=(9, 6),
    color=['teal', 'orange'],
    edgecolor="black"
)

ax.set_xlabel("Sigma prior")
ax.set_ylabel("Average Sharpe")
ax.set_title("Average Sharpe by Sigma Prior")
ax.axhline(0, color='black', linewidth=0.8, linestyle='--')
plt.xticks(rotation=0)

# Add labels to all bar containers
for container in ax.containers:
    ax.bar_label(container, fmt="%.3f", padding=3)

plt.tight_layout()
plt.savefig(PROJECT_ROOT / 'Results' / 'avg_sharpe_by_sigma_prior.png', dpi=300)

# ## Drift Horizon


# Calculate average Sharpe ratios by drift_days
avg_sharpe_drift = pd.DataFrame({
    "Without costs": df_wout_costs.groupby("drift_days")["sharpe"].mean(),
    "With costs": df_with_costs.groupby("drift_days")["sharpe"].mean(),
}).sort_index()

# Create stacked column chart
ax = avg_sharpe_drift.plot(
    kind="bar",
    stacked=False,
    figsize=(7, 6),
    color=['steelblue', 'orange'],
    edgecolor="black"
)

ax.set_xlabel("Drift Days")
ax.set_ylabel("Average Sharpe")
ax.set_title("Average Sharpe by Drift Days")
ax.axhline(0, color='black', linewidth=0.8, linestyle='--')
plt.xticks(rotation=0)

# Add labels to all bar containers
for container in ax.containers:
    ax.bar_label(container, fmt="%.3f", padding=3)

plt.tight_layout()
plt.savefig(PROJECT_ROOT / 'Results' / 'avg_sharpe_by_drift_days.png', dpi=300)

# ## Signal Weight


avg_sharpe_signal = pd.DataFrame({
    "Without costs": df_wout_costs.groupby("signal_method")["sharpe"].mean(),
    "With costs": df_with_costs.groupby("signal_method")["sharpe"].mean(),
}).sort_index()

# Create stacked column chart
ax = avg_sharpe_signal.plot(
    kind="bar",
    stacked=False,
    figsize=(7, 6),
    color=['steelblue', 'gold'],
    edgecolor="black"
)

ax.set_xlabel("Signal Method")
ax.set_ylabel("Average Sharpe")
ax.set_title("Average Sharpe by Signal Method")
ax.axhline(0, color='black', linewidth=0.8, linestyle='--')
plt.xticks(rotation=0)

# Add labels to all bar containers
for container in ax.containers:
    ax.bar_label(container, fmt="%.3f", padding=3)

plt.tight_layout()
plt.savefig(PROJECT_ROOT / 'Results' / 'avg_sharpe_by_signal_method.png', dpi=300)

# ## Position Sizing


avg_sharpe_ps = pd.DataFrame({
    "Without costs": df_wout_costs.groupby("position_sizing")["sharpe"].mean(),
    "With costs": df_with_costs.groupby("position_sizing")["sharpe"].mean(),
}).sort_index()

# Create stacked column chart
ax = avg_sharpe_ps.plot(
    kind="bar",
    stacked=False,
    figsize=(7, 6),
    color=['darkgreen', 'gold'],
    edgecolor="black"
)

ax.set_xlabel("Position Sizing")
ax.set_ylabel("Average Sharpe")
ax.set_title("Average Sharpe by Position Sizing")
ax.axhline(0, color='black', linewidth=0.8, linestyle='--')
plt.xticks(rotation=0)

# Add labels to all bar containers
for container in ax.containers:
    ax.bar_label(container, fmt="%.3f", padding=3)

plt.tight_layout()
plt.savefig(PROJECT_ROOT / 'Results' / 'avg_sharpe_by_position_sizing.png', dpi=300)

# ## Effect of transaction costs


# Compare overall average Sharpe ratio and annualized return
avg_metrics = pd.DataFrame({
    "Without costs": [
        df_wout_costs["sharpe"].mean(),
        df_wout_costs["ann_return"].mean(),
        df_wout_costs["max_drawdown"].mean()
    ],
    "With costs": [
        df_with_costs["sharpe"].mean(),
        df_with_costs["ann_return"].mean(),
        df_with_costs["max_drawdown"].mean()
    ]
}, index=["Average Sharpe", "Average Annual Return", "Average Max Drawdown"])


ax = avg_metrics.plot(
    kind="bar",
    figsize=(7, 8),
    color=["darkgreen", "orangered"],
    edgecolor="black"
)

ax.set_title("Effect of Transaction Costs on Performance Metrics")
ax.set_ylabel("Average Value")
ax.set_xlabel("")
ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
plt.xticks(rotation=0)

for container in ax.containers:
    ax.bar_label(container, fmt="%.3f", padding=3)

plt.tight_layout()
plt.savefig(PROJECT_ROOT / 'Results' / 'transaction_costs_on_performance_metrics.png', dpi=300)

# ## Market Exposure

# ### Alpha


avg_metrics_alpha = pd.DataFrame({
    "Without costs": [
        df_wout_costs["ann_alpha"].mean(),
        df_wout_costs["alpha_t"].mean(),
        df_wout_costs["alpha_p"].mean()
    ],
    "With costs": [
        df_with_costs["ann_alpha"].mean(),
        df_with_costs["alpha_t"].mean(),
        df_with_costs["alpha_p"].mean()
    ]
}, index=["Avg annualized alpha", "Avg alpha_t", "Avg alpha_p"])


ax = avg_metrics_alpha.plot(
    kind="bar",
    figsize=(7, 8),
    color=["slategray", "orangered"],
    edgecolor="black"
)

ax.set_title("Alpha and significance")
ax.set_ylabel("Average Value")
ax.set_xlabel("")
ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
plt.xticks(rotation=0)

for container in ax.containers:
    ax.bar_label(container, fmt="%.3f", padding=3)

plt.tight_layout()
plt.savefig(PROJECT_ROOT / 'Results' / 'alpha_and_significance.png', dpi=300)

# ### Beta


mean_beta = df_wout_costs["beta"].mean()
mean_beta_with_costs = df_with_costs["beta"].mean()

mean_beta_t = df_wout_costs["beta_t"].mean()
mean_beta_t_with_costs = df_with_costs["beta_t"].mean()

mean_beta_p = df_wout_costs["beta_p"].mean()
mean_beta_p_with_costs = df_with_costs["beta_p"].mean()

print(f"Mean beta without costs: {mean_beta:.4f}")
print(f"Mean beta with costs: {mean_beta_with_costs:.4f}")
print("----------------------------------")
print(f"Mean beta_t without costs: {mean_beta_t:.4f}")
print(f"Mean beta_t with costs: {mean_beta_t_with_costs:.4f}")
print("----------------------------------")
print(f"Mean beta_p without costs: {mean_beta_p:.4f}")
print(f"Mean beta_p with costs: {mean_beta_p_with_costs:.4f}")
