import numpy as np
import pandas as pd
import requests
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from config import FRED_API_KEY

def load_risk_free_rates(series_id: str = "DTB4WK", start_date: str = "2020-01-01", end_date: str = "2026-03-31", file_path = PROJECT_ROOT / "data" / "raw" / "4_week_tbills_filled.csv") -> pd.DataFrame:
    """Load risk-free rates from FRED API and save to a CSV file."""

    # 1. Set up the API request to FRED
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "observation_start": start_date,
        "observation_end": end_date,
    }

    # 2. Make the API request
    response = requests.get(url, params=params)

    if response.status_code == 200:
        data = response.json()
        df = pd.DataFrame(data["observations"])[["date", "value"]]
        df.columns = ["Date", "4_Week_T_Bill_Rate"]

        # 3. Clean and Forward-Fill Data
        # Replace FRED's missing data string '.' with actual NaN values
        df["4_Week_T_Bill_Rate"] = df["4_Week_T_Bill_Rate"].replace(".", np.nan)

        # Convert the rate column from text to numeric format
        df["4_Week_T_Bill_Rate"] = pd.to_numeric(df["4_Week_T_Bill_Rate"])

        # Forward-fill missing values with the last valid market rate
        df["4_Week_T_Bill_Rate"] = df["4_Week_T_Bill_Rate"].ffill()

        # 4. Save to CSV
        df.to_csv(file_path, index=False)
        print(f"Success! Forward-filled data saved to {file_path}")

    else:
        print(f"Error: {response.status_code}: {response.text}")
