from google.cloud import bigquery
import pandas as pd
import numpy as np
import yfinance as yf
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from config import PROJECT_ID, DATASET_ID, REC_TABLE_ID

def generate_ticker_date_ranges(file_path = PROJECT_ROOT / "data" / "processed" / "ticker_date_ranges.csv") -> pd.DataFrame:
    if file_path.exists():
        dates_df = pd.read_csv(file_path, parse_dates=["min_date", "max_date"])
        return dates_df

    dates_query = f"""
    SELECT Ticker, MIN(Date) AS min_date, MAX(Date) AS max_date
    FROM `{PROJECT_ID}.{DATASET_ID}.{REC_TABLE_ID}`
    GROUP BY Ticker
    """

    client = bigquery.Client(project=PROJECT_ID)
    dates_df = client.query(dates_query).to_dataframe()

    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    dates_df.to_csv(file_path, index=False)
    return dates_df


def download_prices(dates_df, file_path = PROJECT_ROOT / "data" / "raw" / "adj_close_prices.csv"):
    dates_df = dates_df.copy()
    # Ensure date columns are always datetime, even when loaded as strings from CSV.
    dates_df["min_date"] = pd.to_datetime(dates_df["min_date"], errors="coerce")
    dates_df["max_date"] = pd.to_datetime(dates_df["max_date"], errors="coerce")
    dates_df = dates_df.dropna(subset=["min_date", "max_date"])

    df_prices = pd.DataFrame()

    for _, row in dates_df.iterrows():
        row_min_date = pd.to_datetime(row["min_date"], errors="coerce")
        row_max_date = pd.to_datetime(row["max_date"], errors="coerce")
        
        if pd.isna(row_min_date) or pd.isna(row_max_date):
            continue

        min_date = (row_min_date + pd.Timedelta(days=-366-2)).strftime("%Y-%m-%d")
        max_date = (row_max_date + pd.Timedelta(days=60)).strftime("%Y-%m-%d")

        print(f"Fetching data for {row['Ticker']} from {min_date} to {max_date}...")
        data = yf.download(row["Ticker"], start=min_date, end=max_date, auto_adjust=False, progress=False)

        if data.empty:
            print(f"No data returned for {row['Ticker']}. Skipping.")
            continue

        data.reset_index(inplace=True)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = [col[0] if isinstance(col, tuple) else col for col in data.columns]

        # price_col = "Adj Close" if "Adj Close" in data.columns else "Close"
        if "Adj Close" in data.columns:
            price_col = "Adj Close"
        else:
            price_col = "Close"
            print(f"Warning: 'Adj Close' not found for {row['Ticker']}. Using 'Close' instead.")
        if "Date" not in data.columns or price_col not in data.columns:
            print(f"Expected columns not found for {row['Ticker']}: {list(data.columns)}. Skipping.")
            continue

        data = data[["Date", price_col]].rename(columns={price_col: "Adj_Close"})
        data["Ticker"] = row["Ticker"]
        data["Log_Returns"] = np.log(data["Adj_Close"] / data["Adj_Close"].shift(1))
        data = data[["Ticker", "Date", "Adj_Close", "Log_Returns"]]

        df_prices = pd.concat([df_prices, data], ignore_index=True)

    # Save the final DataFrame to a CSV file
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    df_prices.to_csv(file_path, index=False)


def download_benchmark_data(dates_df, benchmark_ticker = "QQQ", file_path = PROJECT_ROOT / "data" / "raw" / "benchmark_data.csv"):
    min_date = (pd.to_datetime(dates_df["min_date"].min()) + pd.Timedelta(days=-366-2)).strftime("%Y-%m-%d")
    max_date = (pd.to_datetime(dates_df["max_date"].max()) + pd.Timedelta(days=60)).strftime("%Y-%m-%d")
    benchmark = yf.download(benchmark_ticker, start=min_date, end=max_date, auto_adjust=False, progress=False, multi_level_index=False)
    benchmark_prices = benchmark[["Adj Close"]].reset_index()
    benchmark_prices = benchmark_prices.rename(columns={"Adj Close": "Mkt_Adj_Close"})
    benchmark_prices["Mkt_Log_Returns"] = np.log(benchmark_prices["Mkt_Adj_Close"] / benchmark_prices["Mkt_Adj_Close"].shift(1))

    benchmark_prices = benchmark_prices[["Date", "Mkt_Adj_Close", "Mkt_Log_Returns"]]
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    benchmark_prices.to_csv(file_path, index=False)

def build_merged_prices(prices_path = PROJECT_ROOT / "data" / "raw" / "adj_close_prices.csv", benchmark_path = PROJECT_ROOT / "data" / "raw" / "benchmark_data.csv", file_path = PROJECT_ROOT / "data" / "processed" / "prices_with_benchmark.csv"):
    prices = pd.read_csv(prices_path, parse_dates=["Date"])
    benchmark = pd.read_csv(benchmark_path, parse_dates=["Date"])

    merged = prices.merge(benchmark, on="Date", how="left")
    merged = merged.sort_values(["Ticker", "Date"]).reset_index(drop=True)

    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(file_path, index=False)


if __name__ == "__main__":
    dates_df = generate_ticker_date_ranges()
    download_prices(dates_df)
    download_benchmark_data(dates_df)
    build_merged_prices()