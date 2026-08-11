import numpy as np
import pandas as pd
from scipy import stats
from typing import Optional

# Core metrics
def annualized_return(returns: pd.Series, freq: int = 252) -> float:
    """Geometric annualized return from a daily return series."""
    returns = returns.dropna()
    if returns.empty:
        return np.nan
    cum = (1 + returns).prod()
    n_years = len(returns) / freq
    if n_years <= 0:
        return np.nan
    return cum ** (1 / n_years) - 1

def annualized_vol(returns: pd.Series, freq: int = 252) -> float:
    return returns.dropna().std(ddof=1) * np.sqrt(freq)

def sharpe_sortino_ratios(returns: pd.Series, rf: pd.Series, freq: int = 252) -> tuple[float, float]:
    """Sharpe and Sortino ratios of a daily return series, given a daily risk-free rate series."""
    returns.index = pd.to_datetime(returns.index)
    rf.index = pd.to_datetime(rf.index)
    df = pd.concat([returns, rf], axis=1, join="inner").dropna()
    df.columns = ["strat_returns", "rf"]

    excess_returns = df["strat_returns"] - df["rf"]
    mean_excess = excess_returns.mean()
    std_excess = excess_returns.std(ddof=1)
    downside_returns = np.minimum(excess_returns, 0)
    std_downside = downside_returns.std(ddof=1)

    sharpe_ratio = (mean_excess / std_excess) * np.sqrt(freq) if std_excess != 0 else np.nan
    sortino_ratio = (mean_excess / std_downside) * np.sqrt(freq) if std_downside != 0 else np.nan

    return sharpe_ratio, sortino_ratio

def max_drawdown(returns: pd.Series) -> float:
    """Largest peak-to-trough decline in cumulative equity, as a negative fraction."""
    equity = (1 + returns.dropna()).cumprod()
    running_max = equity.cummax()
    drawdown = equity / running_max - 1
    return drawdown.min() if not drawdown.empty else np.nan

def calmar_ratio(returns: pd.Series, freq: int = 252) -> float:
    mdd = max_drawdown(returns)
    if mdd == 0 or np.isnan(mdd):
        return np.nan
    return annualized_return(returns, freq) / abs(mdd)

def hit_rate(trade_returns: pd.Series) -> float:
    """Fraction of individual trades (not daily returns) that were profitable."""
    trade_returns = trade_returns.dropna()
    if trade_returns.empty:
        return np.nan
    return (trade_returns > 0).mean()

def win_loss_ratio(trade_returns: pd.Series) -> float:
    trade_returns = trade_returns.dropna()
    wins = trade_returns[trade_returns > 0]
    losses = trade_returns[trade_returns < 0]
    if losses.empty or wins.empty:
        return np.nan
    return wins.mean() / abs(losses.mean())

# Cost adjustement
def apply_transaction_costs(returns: pd.Series, positions: pd.DataFrame, 
    prices_df: pd.DataFrame, cost_bps: float = 10.0) -> pd.Series:
    """
    Deduct estimated transaction costs from daily portfolio returns based on 
    dollar value turnover. Both positions and prices_df are expected in long format.
    """
    if positions.empty or prices_df.empty:
        return returns

    # 1. Pivot positions into a wide grid (Rows: Date, Columns: Ticker)
    shares_pivot = positions.pivot_table(index="Date", columns="Ticker", values="position", fill_value=0)
    
    # 2. Pivot prices into the same wide grid layout
    prices_pivot = prices_df.pivot_table(index="Date", columns="Ticker", values="Adj_Close")
    
    # 3. Align the price grid to perfectly match the position grid's dates and tickers
    aligned_prices = prices_pivot.reindex(index=shares_pivot.index, columns=shares_pivot.columns)
    
    # Forward-fill and backward-fill missing prices to avoid NaN gaps breaking the math
    aligned_prices = aligned_prices.ffill().bfill().fillna(0)
    
    # 4. Convert share counts to dollar values (Shares * Price)
    dollar_values = shares_pivot * aligned_prices
    
    # 5. Calculate dollar turnover (value traded today vs yesterday)
    dollar_turnover = dollar_values.diff().abs().sum(axis=1).fillna(0)
    
    # 6. Calculate total portfolio value to normalize the turnover
    total_portfolio_value = dollar_values.abs().sum(axis=1).replace(0, np.nan)
    
    # 7. Calculate the fee drag ratio
    cost_drag = (dollar_turnover / total_portfolio_value).fillna(0) * (cost_bps / 10000)

    # 8. Deduct the cost drag from your returns
    adjusted = returns.copy()
    adjusted = adjusted.sub(cost_drag.reindex(adjusted.index, fill_value=0), fill_value=0)
    
    return adjusted

# Statistical significance
def bootstrap_sharpe_ci(returns: pd.Series, rf: pd.Series, n_boot: int = 5000, freq: int = 252,
    ci: float = 0.90, seed: Optional[int] = 42) -> tuple[float, float, float]:
    returns_clean = returns.dropna()   
    values = returns_clean.values      

    rng = np.random.default_rng(seed)
    n = len(values)
    if n < 10:
        return np.nan, np.nan, np.nan

    boot_sharpes = np.empty(n_boot)
    for i in range(n_boot):
        sample = rng.choice(values, size=n, replace=True)
        vol = sample.std(ddof=1)
        boot_sharpes[i] = (sample.mean() / vol) * np.sqrt(freq) if vol > 0 else np.nan

    boot_sharpes = boot_sharpes[~np.isnan(boot_sharpes)]
    alpha = (1 - ci) / 2
    lower = np.percentile(boot_sharpes, 100 * alpha)
    upper = np.percentile(boot_sharpes, 100 * (1 - alpha))

    point, _ = sharpe_sortino_ratios(returns_clean, rf, freq=freq)
    return point, lower, upper

# Benchmark Comparison
def alpha_beta_stats(returns: pd.Series, benchmark: pd.Series, rf: pd.Series, freq: int = 252) -> dict:
    """
    OLS regression of strategy excess returns on benchmark excess returns,
    with standard errors, t-stats, and p-values for alpha and beta.
    """
    returns.index = pd.to_datetime(returns.index)
    benchmark.index = pd.to_datetime(benchmark.index)
    rf.index = pd.to_datetime(rf.index)

    df = pd.concat([returns, benchmark, rf], axis=1, keys=["strategy", "bench", "rf"], sort=True).dropna()
    n = len(df)
    if n < 3:
        return {k: np.nan for k in
                ["alpha_annualized", "beta", "alpha_t", "alpha_p", "beta_t", "beta_p", "n"]}

    excess_strat = df["strategy"] - df["rf"]
    excess_bench = df["bench"] - df["rf"]

    x = excess_bench.values
    y = excess_strat.values
    x_mean, y_mean = x.mean(), y.mean()

    var_x = ((x - x_mean) ** 2).sum()
    beta = ((x - x_mean) * (y - y_mean)).sum() / var_x
    alpha_daily = y_mean - beta * x_mean

    resid = y - (alpha_daily + beta * x)
    dof = n - 2
    resid_var = (resid ** 2).sum() / dof
    se_alpha = np.sqrt(resid_var * (1 / n + x_mean**2 / var_x))
    se_beta = np.sqrt(resid_var / var_x)

    alpha_t = alpha_daily / se_alpha
    beta_t = beta / se_beta
    alpha_p = 2 * (1 - stats.t.cdf(abs(alpha_t), dof))
    beta_p = 2 * (1 - stats.t.cdf(abs(beta_t), dof))

    return {
        "alpha_annualized": alpha_daily * freq,
        "beta": beta,
        "alpha_t": alpha_t, "alpha_p": alpha_p,
        "beta_t": beta_t, "beta_p": beta_p,
        "n": n,
    }

def information_ratio(returns: pd.Series, benchmark: pd.Series, freq: int = 252) -> float:
    """Active return over active risk vs a benchmark."""
    df = pd.concat([returns, benchmark], axis=1, keys=["strategy", "bench"], sort=True).dropna()
    active = df["strategy"] - df["bench"]
    if active.std(ddof=1) == 0:
        return np.nan
    return (active.mean() / active.std(ddof=1)) * np.sqrt(freq)