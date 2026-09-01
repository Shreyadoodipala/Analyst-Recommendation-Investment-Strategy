import pandas as pd
import numpy as np
import pandas_gbq
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from config import PROJECT_ID, DATASET_ID, REC_TABLE_ID

prices_df = pd.read_csv(PROJECT_ROOT / "data" / "raw" / "adj_close_prices.csv", parse_dates=["Date"])
prices_df_train = prices_df[prices_df["Date"] < "2023-01-01"]

full_df = pandas_gbq.read_gbq(f"SELECT * FROM `{PROJECT_ID}.{DATASET_ID}.{REC_TABLE_ID}`", project_id=PROJECT_ID)
full_df['Date'] = pd.to_datetime(full_df['Date'])
train_df = full_df[full_df['Date'] < '2023-01-01']

def find_drift_days(prices_df, rec_df, window):
    # Build a rank of trading days per ticker
    prices_df['day_rank'] = prices_df.groupby('Ticker').cumcount()

    # Merge event date's rank
    event_ranks = rec_df.merge(
        prices_df[['Ticker', 'Date', 'day_rank']],
        left_on=['Ticker', 'Date'], right_on=['Ticker', 'Date'],
        how='left'
    ).rename(columns={'day_rank': 'event_rank'})

    results = []

    # Pre-sort and group prices by ticker for fast lookup
    prices_sorted = prices_df.sort_values(['Ticker', 'day_rank'])
    price_groups = {t: g.reset_index(drop=True) for t, g in prices_sorted.groupby('Ticker')}

    for ticker, ev in event_ranks.groupby('Ticker'):
        if ticker not in price_groups:
            continue
        
        pg = price_groups[ticker]
        ranks = pg['day_rank'].values
        returns = pg['Log_Returns'].values
        dates = pg['Date'].values
        
        for _, row in ev.iterrows():
            event_rank = row['event_rank']
            if pd.isna(event_rank):
                continue
            
            # find slice of rows with rank in (event_rank, event_rank + window]
            start = np.searchsorted(ranks, event_rank, side='right')
            end = np.searchsorted(ranks, event_rank + window, side='right')
            
            if start >= end:
                continue
            
            window_returns = returns[start:end]
            window_dates = dates[start:end]
            window_ranks = ranks[start:end]
            max_idx = np.argmax(window_returns)
            
            results.append({
                'Ticker': ticker,
                'Event_Date': row['Date'],
                'max_return_date': window_dates[max_idx],
                'max_return': window_returns[max_idx],
                'days_to_max': int(window_ranks[max_idx] - event_rank)  # <-- key addition
            })

    result_df = pd.DataFrame(results)
    result = result_df
    avg_days_df = (
        result.groupby('Ticker')['days_to_max']
        .mean()
        .reset_index()
    )
    return int(avg_days_df['days_to_max'].mean())

windows = [20,30, 45, 60, 90, 180]
for w in windows:
    print(f"Average max return days for window {w}:", find_drift_days(prices_df_train, train_df, window=w))