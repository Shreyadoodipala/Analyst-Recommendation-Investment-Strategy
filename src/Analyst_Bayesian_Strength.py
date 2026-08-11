import numpy as np
import pandas as pd

# Helper functions to compute returns
def _add_rolling_beta(group: pd.DataFrame, window: int) -> pd.Series:
    """
    Compute a rolling OLS beta (stock log returns ~ market log returns)
    for a single ticker group. Requires at least 30 observations in the
    window before emitting a non-NaN value.
    """

    log_ret = group['Log_Returns'].values
    mkt_ret = group['Mkt_Log_Returns'].values
    betas = np.full(len(group), np.nan)

    for i in range(window, len(group)):
        y = log_ret[i - window:i]
        x = mkt_ret[i - window:i]
        mask = ~np.isnan(x) & ~np.isnan(y)
        if mask.sum() < 30:
            continue
        cov = np.cov(y[mask], x[mask])
        var_x = np.var(x[mask])
        betas[i] = cov[0, 1] / var_x if var_x > 0 else np.nan

    return pd.Series(betas, index=group.index)

def _offset_date(sorted_dates, event_date, offset: int):
    """Return the trading date `offset` days from event_date, or None."""
    idx = np.searchsorted(sorted_dates, np.datetime64(event_date, 'ns'))
    target = idx + offset
    if target < 0 or target >= len(sorted_dates):
        return None
    return sorted_dates[target]

def _window_return(ticker_df: pd.DataFrame, start, end) -> float:
    """
    Cumulative idiosyncratic return over [start, end], normalized once by the idiosyncratic vol estimated at `start`.
 
    Normalization is done once at the window boundary (not day-by-day),
    so Impact and Drift are both expressed in units of daily idio vol and are directly comparable regardless of window length.
    """
    if start is None or end is None:
        return np.nan
    try:
        vol = ticker_df.loc[start, 'Idio_Vol']
    except KeyError:
        return np.nan
    if np.isnan(vol) or vol == 0:
        return np.nan
 
    mask = (ticker_df.index > start) & (ticker_df.index <= end)
    cumulative = ticker_df.loc[mask, 'Idio_Return'].dropna().sum()
    return float(cumulative / vol)

# Drift and Impact Returns
def compute_returns(rec_df: pd.DataFrame, merged_df: pd.DataFrame,
    impact_prior: int = 1, impact_post: int = 1,
    drift_days: int = 20, window: int = 252,
    idio_vol_window: int = 60, idio_vol_min_periods: int = 20) -> pd.DataFrame:
    """
    Attach Impact_Return and Drift_Return to every recommendation event in rec_df.
 
    Parameters
    ----------
    rec_df : recommendation events with at least ['Date', 'Ticker'] columns.
    merged_df : daily price data with at least ['Date', 'Ticker', 'Log_Returns', 'Mkt_Log_Returns'] columns.
    impact_prior : trading days before event for the impact window (default 1).
    impact_post  : trading days after  event for the impact window (default 1).
    drift_days   : trading days after  impact_post for the drift window (default 20).
    window       : rolling window (in days) for beta estimation (default 252).
    idio_vol_window : rolling window for idiosyncratic volatility (default 60).
    idio_vol_min_periods : minimum observations for vol estimate (default 20).
 
    Returns
    -------
    rec_df with two new columns: Impact_Return, Drift_Return
        Both are cumulative idiosyncratic returns over their respective windows,
        normalized once by the idiosyncratic vol at the window's start date.
        This makes Impact and Drift directly comparable in units of daily idio vol, regardless of window length — following Jaisson et al. (2021).
    """
    rec_df = rec_df.copy()
    rec_df['Date'] = pd.to_datetime(rec_df['Date'])
 
    merged_df = merged_df.copy()
    merged_df['Date'] = pd.to_datetime(merged_df['Date'])
    merged_df = merged_df.sort_values(['Ticker', 'Date'])

    merged_df['Beta'] = (merged_df
        .groupby('Ticker', group_keys=False)
        .apply(_add_rolling_beta, window=window)
        .reset_index(level=0, drop=True)
    )
 
    # Step 2: Idiosyncratic return = actual − beta × market
    merged_df['Idio_Return'] = (merged_df['Log_Returns'] 
                                - merged_df['Beta'] * merged_df['Mkt_Log_Returns'])
 
    # Step 3: Normalize by rolling idiosyncratic volatility
    # Shift by 1 to avoid look-ahead: vol on day t uses only days < t.
    merged_df['Idio_Vol'] = (merged_df.groupby('Ticker')['Idio_Return']
        .transform(lambda s: s.shift(1).rolling(idio_vol_window, min_periods=idio_vol_min_periods).std())
    )
 
    # Step 4: Build per-ticker DataFrames indexed by Date
    # Keeps Idio_Return and Idio_Vol separate so _window_return can normalize once per window (at the start date) rather than day-by-day.
    ticker_idio = {
        ticker: group.set_index('Date')[['Idio_Return', 'Idio_Vol']]
        for ticker, group in merged_df.groupby('Ticker')
    }
 
    sorted_dates = np.array(merged_df['Date'].sort_values().unique())
 
    # Step 5: Compute Impact and Drift for every recommendation event
    impact_returns = []
    drift_returns = []
 
    for _, row in rec_df.iterrows():
        ticker = row['Ticker']
        event_date = row['Date']
 
        if ticker not in ticker_idio:
            impact_returns.append(np.nan)
            drift_returns.append(np.nan)
            continue
 
        tdf = ticker_idio[ticker]
 
        # Impact window : (t − impact_prior, t + impact_post]
        d_start       = _offset_date(sorted_dates, event_date, -impact_prior)
        d_mid         = _offset_date(sorted_dates, event_date, +impact_post)
 
        # Drift window  : (t + impact_post, t + impact_post + drift_days]
        d_drift_end   = _offset_date(sorted_dates, event_date, +impact_post + drift_days)
 
        impact_returns.append(_window_return(tdf, d_start, d_mid))
        drift_returns.append(_window_return(tdf, d_mid, d_drift_end))
 
    rec_df['Impact_Return'] = impact_returns
    rec_df['Drift_Return']  = drift_returns
 
    return rec_df

def bayesian_strength(rec_df: pd.DataFrame, window_years: int | None = None, sigma_prior: float = 0.3) -> pd.DataFrame:
    """
    Compute Bayesian Strength for each recommendation event in rec_df.
 
    Parameters
    ----------
    rec_df : recommendation events with at least ['Date', 'Ticker', 'Analyst', 'Impact_Return', 'Drift_Return'] columns.
    window_years : rolling window (in years) for computing the analyst's prior mean and variance. If None, use all available history.
    sigma_prior : prior standard deviation of analyst strength (default 0.3).
 
    Returns
    -------
    rec_df with new columns: _ex_ante_strength_impact, _ex_ante_strength_drift
        _ex_ante_strength is the posterior mean of the analyst's skill, computed using a Bayesian update with a normal prior and normal likelihood.
        The prior is N(0, sigma_prior^2), and the likelihood is N(Return, sigma^2), where sigma^2 is the sample variance of the analyst's past Returns within the rolling window.
    """

    lambda_ridge = 1.0 / (sigma_prior ** 2)
    df = rec_df.copy()

    df["_year"] = pd.to_datetime(df["Date"]).dt.year
    df["_ex_ante_strength_impact"] = np.nan
    df["_ex_ante_strength_drift"] = np.nan

    # Sort by date so we can use expanding/rolling lookback
    df = df.sort_values("Date").reset_index(drop=True)

    for analyst, grp in df.groupby("Analyst"):
        idxs = grp.index.tolist()

        for pos, i in enumerate(idxs):
            t = pd.to_datetime(df.at[i, "Date"])

            # Use all past recommendations strictly before current
            past = grp.iloc[:pos]

            if window_years is not None:
                cutoff = t - pd.DateOffset(years=window_years)
                past = past[past["Date"] >= cutoff]
            # else: use full expanding history (no cutoff filter)

            R_impact = past["Impact_Return"].dropna()
            S_impact = past.loc[R_impact.index, 'Signal'].dropna()

            R_drift = past["Drift_Return"].dropna()
            S_drift = past.loc[R_drift.index, 'Signal'].dropna()

            common_impact = R_impact.index.intersection(S_impact.index)
            R_impact, S_impact = R_impact[common_impact], S_impact[common_impact]

            common_drift = R_drift.index.intersection(S_drift.index)
            R_drift, S_drift = R_drift[common_drift], S_drift[common_drift]

            # Ridge-regression formula for µ̃
            numerator   = (S_impact * R_impact).sum()
            denominator = lambda_ridge + (S_impact ** 2).sum()
            mu_hat      = numerator / denominator
            df.at[i, "_ex_ante_strength_impact"] = mu_hat

            # Repeat for drift
            numerator   = (S_drift * R_drift).sum()
            denominator = lambda_ridge + (S_drift ** 2).sum()
            mu_hat      = numerator / denominator
            df.at[i, "_ex_ante_strength_drift"] = mu_hat

    return df

def shrunk_drift_analysts(df_with_strength: pd.DataFrame, sigma: float = 0.3) -> pd.DataFrame:
    """
    Return a DataFrame of analysts sorted by shrunk drift.
    """

    analyst_profile = (df_with_strength.groupby("Analyst")
        .agg(
            avg_drift_strength=("_ex_ante_strength_drift", "mean"),
            avg_impact_strength=("_ex_ante_strength_impact", "mean"),
            n_recs=("Signal", "count")
        ).reset_index()
    )

    mean_drift_strength = analyst_profile["avg_drift_strength"].mean()
    mean_impact_strength = analyst_profile["avg_impact_strength"].mean()

    lambda_ridge = 1.0 / (sigma ** 2)

    analyst_profile["shrunk_drift"] = (analyst_profile["n_recs"] / (analyst_profile["n_recs"] + lambda_ridge)) * analyst_profile["avg_drift_strength"] + (lambda_ridge / (analyst_profile["n_recs"] + lambda_ridge)) * mean_drift_strength

    analyst_profile["shrunk_impact"] = (analyst_profile["n_recs"] / (analyst_profile["n_recs"] + lambda_ridge)) * analyst_profile["avg_impact_strength"] + (lambda_ridge / (analyst_profile["n_recs"] + lambda_ridge)) * mean_impact_strength

    return analyst_profile.sort_values(by=["shrunk_drift"], ascending=False).reset_index(drop=True)

def top_drift_analysts(analyst_profile: pd.DataFrame, top_n: int = 15) -> pd.DataFrame:
    """
    Return top analysts by shrunk drift strength.

    Parameters
    ----------
    analyst_profile : pd.DataFrame
        Must contain a "shrunk_drift" column.
    top_n : int, optional
        Number of analysts to return, ranked by shrunk_drift. Defaults to 15.

    Returns
    -------
    pd.DataFrame
        Sorted descending by shrunk_drift.
    """
    return analyst_profile.sort_values(by="shrunk_drift", ascending=False).reset_index(drop=True).head(top_n)