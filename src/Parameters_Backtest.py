"""
Parallelized grid search for the analyst-drift backtest.

Key idea:
- encode_signal()/compute_returns() only depend on (signal_method, d), not on sigma or pos_sizing,
  so they're precomputed ONCE per (signal_method, d) pair instead of being redone inside every sigma/pos_sizing iteration.
- The (signal_method, d, sigma) grid is fanned out across worker processes with joblib. 
  pos_sizing (2 options) stays as a cheap sequential loop inside each worker task, since it reuses the same top_analysts/test encoding.
- joblib's "loky" backend is used because it relies on cloudpickle, which handles functions/objects defined in a notebook far better than plain multiprocessing.
"""

import os

# Avoid BLAS thread oversubscription: each worker process spawning its own
# multi-threaded BLAS calls on top of joblib's process-level parallelism can
# actually slow things down. Set this BEFORE importing numpy/pandas.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

from itertools import product

import pandas as pd
from joblib import Parallel, delayed

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

# Your existing modules — must be importable (i.e. not defined inline in the notebook)
# for loky to ship them to worker processes.
import src.Analyst_Bayesian_Strength as abs_  # renamed to avoid shadowing builtin `abs`
import src.Strategy as strat
import src.Backtest as bt


def build_rec_df_cache(train_df, train_prices_df, signal_variations, drift_days):
    """
    Precompute the expensive, sigma-independent step ONCE per (signal_method, d).
    This mirrors what the original loop already did (encode/compute_returns sit
    outside the sigma loop) — we're just materializing it into a dict so it can
    be handed to parallel workers instead of recomputed inside each one.
    """
    cache = {}
    for signal_method, d in product(signal_variations, drift_days):
        train_df_encoded = abs_.encode_signal(train_df.copy(), signal_method)
        rec_df = abs_.compute_returns(train_df_encoded, train_prices_df, drift_days=d)
        cache[(signal_method, d)] = rec_df
    return cache


def run_sigma_task(
    signal_method,
    d,
    sigma,
    rec_df,
    test_df,
    test_prices_df,
    benchmark_returns,
    rf,
    pos_sizings,
):
    """
    One unit of parallel work: everything downstream of a given
    (signal_method, d, sigma) combination, including the inner pos_sizing loop.
    Returns a list of result dicts (one per pos_sizing).
    """
    df_with_strength = abs_.bayesian_strength(rec_df, sigma_prior=sigma)

    analyst_profile = abs_.shrunk_drift_analysts(df_with_strength, sigma=sigma)
    analyst_profile = analyst_profile[~(analyst_profile["n_recs"] < 10)]
    top_analysts = abs_.top_drift_analysts(analyst_profile, top_n=15)
    analyst_list = top_analysts["Analyst"].tolist()

    test_df_rec = test_df[test_df["Analyst"].isin(analyst_list)]
    test_df_encoded = abs_.encode_signal(test_df_rec, signal_method)

    task_results = []
    for pos_sizing in pos_sizings:
        trades_df = strat.build_trades(
            test_df_encoded,
            test_prices_df,
            dh_trade=d,
            position_sizing=pos_sizing,
            timing_assumption="next_day",
        )
        trade_returns = strat.compute_trade_returns(trades_df, test_prices_df)
        trade_returns.name = "trade_return"
        positions = strat.get_daily_positions(trades_df, test_prices_df)
        daily_portfolio_returns = strat.mark_to_market(positions, test_prices_df)

        sharpe, sortino = bt.sharpe_sortino_ratios(daily_portfolio_returns, rf)
        point, lower, upper = bt.bootstrap_sharpe_ci(daily_portfolio_returns, rf)
        benchmark_stats = bt.alpha_beta_stats(daily_portfolio_returns, benchmark_returns, rf)

        task_results.append(
            {
                "signal_method": signal_method,
                "position_sizing": pos_sizing,
                "drift_days": d,
                "sigma_prior": sigma,
                "ann_return": bt.annualized_return(daily_portfolio_returns),
                "ann_vol": bt.annualized_vol(daily_portfolio_returns),
                "sharpe": sharpe,
                "sortino": sortino,
                "max_drawdown": bt.max_drawdown(daily_portfolio_returns),
                "calmar": bt.calmar_ratio(daily_portfolio_returns),
                "hit_rate": bt.hit_rate(trade_returns),
                "win_loss": bt.win_loss_ratio(trade_returns),
                "sharpe_ci_low": lower,
                "sharpe_ci_high": upper,
                "ann_alpha": benchmark_stats.get("alpha_annualized"),
                "alpha_t": benchmark_stats.get("alpha_t"),
                "alpha_p": benchmark_stats.get("alpha_p"),
                "beta": benchmark_stats.get("beta"),
                "beta_t": benchmark_stats.get("beta_t"),
                "beta_p": benchmark_stats.get("beta_p"),
                "n": benchmark_stats.get("n"),
            }
        )
    return task_results


def run_grid_search(
    train_df,
    train_prices_df,
    test_df,
    test_prices_df,
    benchmark_returns,
    rf,
    drift_days,
    sigma_prior,
    signal_variations=("default", "shadow_sell"),
    pos_sizings=("equal", "signal_weight"),
    n_jobs=-1,
    verbose=10,
):
    # Step 1: precompute the sigma-independent step once per (signal_method, d)
    rec_df_cache = build_rec_df_cache(
        train_df, train_prices_df, signal_variations, drift_days
    )

    # Step 2: fan out (signal_method, d, sigma) across worker processes
    tasks = list(product(signal_variations, drift_days, sigma_prior))

    nested_results = Parallel(n_jobs=n_jobs, backend="loky", verbose=verbose)(
        delayed(run_sigma_task)(
            signal_method,
            d,
            sigma,
            rec_df_cache[(signal_method, d)],
            test_df,
            test_prices_df,
            benchmark_returns,
            rf,
            pos_sizings
        )
        for signal_method, d, sigma in tasks
    )

    # Flatten list-of-lists into one list of result dicts
    results = [row for task_result in nested_results for row in task_result]

    results_df = pd.DataFrame(results).sort_values("sharpe", ascending=False).reset_index(drop=True)
    return results_df
