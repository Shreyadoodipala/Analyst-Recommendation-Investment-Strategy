import sys
from pathlib import Path

import pandas_gbq
import numpy as np 
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import PROJECT_ID, DATASET_ID, REC_TABLE_ID
import src.Data_Retrieval as dr
import src.Data_Cleaning_And_Feature_Engineering as dcfe
import src.Load_Dates_And_AdjClose as ldac
import src.Load_Risk_Free_Rates as lrf
import src.Parameters_Backtest as pb

# Data Retrieval
dr.data_retrieval()

# Data Cleaning
dcfe.data_cleaning()

# Feature Engineering
dcfe.standardize_ratings()
dcfe.add_rec_type()

# Create train and test datasets
full_df = pandas_gbq.read_gbq(f"SELECT * FROM `{PROJECT_ID}.{DATASET_ID}.{REC_TABLE_ID}`", project_id=PROJECT_ID)
full_df['Date'] = pd.to_datetime(full_df['Date'])
train_df = full_df[full_df['Date'] < '2023-01-01']
test_df = full_df[full_df['Date'] >= '2023-01-01']

# Load Dates and Adjusted Close Prices
dates_df = ldac.generate_ticker_date_ranges()
ldac.download_prices(dates_df)
ldac.download_benchmark_data(dates_df)
ldac.build_merged_prices()

prices_df = pd.read_csv(PROJECT_ROOT / 'data' / 'processed' / 'prices_with_benchmark.csv')
prices_df['Date'] = pd.to_datetime(prices_df['Date'])
train_prices_df = prices_df[prices_df['Date'] < '2023-01-01']
test_prices_df = prices_df[prices_df['Date'] >= '2023-01-01']
benchmark_returns = (
    test_prices_df[["Date", "Mkt_Log_Returns"]]
    .drop_duplicates(subset="Date", keep="first")
    .set_index("Date")["Mkt_Log_Returns"]
)

# Load Risk-Free Rates
lrf.load_risk_free_rates()
lrf.convert_to_daily_rate()

rf_df = pd.read_csv(PROJECT_ROOT / 'data' / 'processed' / 'risk_free_rate.csv')
rf = rf_df.set_index('Date')['Daily_rf']

# Backtest Strategy variations with grid search
drift_days = (21, 29, 45)
sigma_prior = (0.02, 0.05, 0.1, 0.2, 0.3)

grid_search_results = pb.run_grid_search(train_df, train_prices_df, test_df, test_prices_df,
    benchmark_returns, rf, drift_days, sigma_prior,
    signal_variations=("default", "shadow_sell"),
    pos_sizings=("equal", "signal_weight"),
    n_jobs=-1, verbose=10)
grid_search_results.to_csv(PROJECT_ROOT / "outputs" / "grid_search_results.csv", index=False)

# Correlation heatmap of grid search results
grid_res_encoded = grid_search_results.copy()
grid_res_encoded['signal_method'] = grid_res_encoded['signal_method'].map({'default': 1, 'shadow_sell': 0})
grid_res_encoded['position_sizing'] = grid_res_encoded['position_sizing'].map({'equal': 1, 'signal_weight': 0})

# Drop columns that are highly correlated or not needed to simplify correlation analysis
grid_res_encoded.drop(columns=['sortino', 'alpha_p', 'beta_p', 'sharpe_ci_low', 'sharpe_ci_high'], inplace=True)
corr = grid_res_encoded.corr()
mask = np.triu(np.ones_like(corr, dtype=bool))
               
plt.figure(figsize=(20, 10))
sns.heatmap(corr, annot=True, cmap='coolwarm', fmt=".3f", mask=mask)
plt.savefig(PROJECT_ROOT / "outputs" / "grid_search_correlation_heatmap.png", bbox_inches='tight')
