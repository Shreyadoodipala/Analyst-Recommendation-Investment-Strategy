import numpy as np
import pandas as pd

# 1. "Upgrade or downgrade?" -> Go long / Go short at close 
def build_trades(df_rec: pd.DataFrame, df_prices: pd.DataFrame, dh_trade: int, position_sizing: str, timing_assumption: str = "next_day") -> pd.DataFrame:
    """
    Turn each non-zero Signal into a trade with an entry date, an exit date (dh_trade trading days later, using that ticker's own price calendar), and a direction (+ve for long, -ve for short).

    timing_assumption controls when the trade is assumed to enter, 
    since the Date column carries no time-of-day information and 
    analyst notes can be issued before or after that day's close:
      - "next_day": enter at the FIRST close strictly after the signal date.
            This is the look-ahead-safe assumption -- it assumes the recommendation could have been published after that day's close, so the earliest tradeable price is the following session's close.
      - "same_day": enter at the signal date's own close. 
            This assumes the recommendation was known before that day's close (e.g. pre-market
            or intraday). 
            It will flatter results for any recommendations that were actually issued after close, since same-day closes may already reflect the news.

    position_sizing controls how the trade's direction is sized:
      - "equal": all trades are +1 or -1, regardless of the signal's magnitude.
      - "signal_weight": the trade's direction is equal to the signal value itself, so that stronger signals carry more weight in the portfolio.
    """
    if timing_assumption not in ("same_day", "next_day"):
        raise ValueError(
            f"timing_assumption must be 'same_day' or 'next_day', got {timing_assumption!r}"
        )

    if position_sizing not in ("equal", "signal_weight"):
        raise ValueError(
            f"position_sizing must be 'equal' or 'signal_weight', got {position_sizing!r}"
        )
    
    df_rec = df_rec.copy()
    df_prices = df_prices.copy()
    df_rec["Date"] = pd.to_datetime(df_rec["Date"])
    df_prices["Date"] = pd.to_datetime(df_prices["Date"])
 
    # Each ticker gets its own sorted trading calendar, in case tickers don't all trade on identical dates.
    calendars = {
        ticker: np.sort(group["Date"].unique())
        for ticker, group in df_prices.groupby("Ticker")
    }
 
    trades = []
    signals = df_rec[df_rec["Signal"] != 0]
 
    for _, row in signals.iterrows():
        ticker = row["Ticker"]
        cal = calendars.get(ticker)
        if cal is None or len(cal) == 0:
            continue  # no price data for this ticker, skip
 
        entry_idx = np.searchsorted(cal, row["Date"])
        if timing_assumption == "next_day":
            # first close STRICTLY after the signal date (searchsorted with side="right" already lands one past an exact match;
            # for a signal date that isn't itself a trading day, 
            # "left" behavior of searchsorted already points to the next available session,
            # so we only need to nudge forward when the signal date IS an exact trading day).
            if entry_idx < len(cal) and cal[entry_idx] == row["Date"]:
                entry_idx += 1
        if entry_idx >= len(cal):
            continue  # signal is after (or at) the last known price date
 
        exit_idx = min(entry_idx + dh_trade, len(cal) - 1)

        if position_sizing == "equal":
            direction = 1 if row["Signal"] > 0 else -1
        elif position_sizing == "signal_weight":
            direction = row["Signal"]  # use the actual signal value as the position size
 
        trades.append({
            "Ticker": ticker,
            "entry_date": cal[entry_idx],
            "exit_date": cal[exit_idx],
            "direction": direction,
            "timing_assumption": timing_assumption,
        })
 
    return pd.DataFrame(trades)

# 2. "Hold position for DH_trade days" -> expand each trade into daily rows
def get_daily_positions(trades: pd.DataFrame, df_prices: pd.DataFrame) -> pd.DataFrame:
    """
    Expand each trade into one row per held trading day, then net-sum direction across overlapping trades on the same ticker/day.
    Returns columns: Date, Ticker, position (net direction, can be >|1|).
    """
    if trades.empty:
        return pd.DataFrame(columns=["Date", "Ticker", "position"])
 
    df_prices = df_prices.copy()
    df_prices["Date"] = pd.to_datetime(df_prices["Date"])
    calendars = {
        ticker: np.sort(group["Date"].unique())
        for ticker, group in df_prices.groupby("Ticker")
    }
 
    rows = []
    for _, t in trades.iterrows():
        cal = calendars[t["Ticker"]]
        start_idx = np.searchsorted(cal, t["entry_date"])
        end_idx = np.searchsorted(cal, t["exit_date"])
        held_dates = cal[start_idx:end_idx + 1]
        for d in held_dates:
            rows.append({"Date": d, "Ticker": t["Ticker"], "direction": t["direction"]})
 
    daily = pd.DataFrame(rows)
    # "overlapping trades counted together" -> sum, don't just take one
    positions = (daily.groupby(["Date", "Ticker"], as_index=False)["direction"].sum()
        .rename(columns={"direction": "position"})
    )
    return positions

# 3. "Mark portfolio to market daily" -> daily portfolio return series
def mark_to_market(positions: pd.DataFrame, df_prices: pd.DataFrame) -> pd.Series:
    """
    Join positions to that day's return and equal-weight across all open positions (weighted by net direction size) to get one portfolio return per trading day.
    """
    df_prices = df_prices.copy()
    df_prices["Date"] = pd.to_datetime(df_prices["Date"])
 
    merged = positions.merge(df_prices[["Date", "Ticker", "Log_Returns"]], on=["Date", "Ticker"], how="left")
    merged["weighted_return"] = merged["position"] * merged["Log_Returns"]
  
    # (sum of weighted returns / number of open positions that day).
    # This lets a stacked position count more than once, per "overlapping trades counted together".
    daily = merged.groupby("Date").apply(
        lambda g: g["weighted_return"].sum() / g["position"].abs().sum()
        if g["position"].abs().sum() != 0 else 0.0
    )
    daily.name = "portfolio_return"
    return daily.sort_index()

def compute_trade_returns(trades, prices_df):
    lr = prices_df.pivot(index="Date", columns="Ticker", values="Log_Returns")

    def _ret(row):
        mask = (lr.index > row.entry_date) & (lr.index <= row.exit_date)
        cum_log = lr.loc[mask, row.Ticker].sum()
        return (np.exp(cum_log) - 1) * row.direction

    return trades.apply(_ret, axis=1)