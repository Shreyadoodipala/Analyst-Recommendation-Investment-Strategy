import pandas_gbq
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from config import PROJECT_ID, DATASET_ID, REC_TABLE_ID, ORIGINAL_DATASET, ORIGINAL_TABLE


# Stage 1: Pull the data AND cast types
def data_retrieval():
    print("▶ Stage 1: Copying data and casting types...")
    query = f"""
    SELECT 
        Date, 
        Company_Name AS Ticker, 
        Ticker AS Company_Name, 
        Broker, Analyst, 
        Rating_Before, Rating_After, Price_Target_Before, Price_Target_After 
    FROM `{PROJECT_ID}.{ORIGINAL_DATASET}.{ORIGINAL_TABLE}`
    """

    print("Fetching and casting data...")
    # This reads the data directly into computer's local memory
    df = pandas_gbq.read_gbq(query, project_id=PROJECT_ID)

    print(f"Successfully retrieved {len(df)} records. Writing to database...")
    # Write the dataframe back up into the new writable dataset
    pandas_gbq.to_gbq(
        df, 
        destination_table=f"{DATASET_ID}.{REC_TABLE_ID}", 
        project_id=PROJECT_ID, 
        if_exists="replace"
    )

    print(f"Written to {PROJECT_ID}.{DATASET_ID}.{REC_TABLE_ID}")


# ── Run pipeline ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    data_retrieval()
    print("\n✓ Data retrieval complete.")
