from google.cloud import bigquery
import os
from config import PROJECT_ID, DATASET_ID, REC_TABLE_ID, ORIGINAL_TABLE

# Stage 2: Clean the data
def data_cleaning():
    print("▶ Stage 2: Cleaning Data...")

    # Read the SQL cleaning script
    sql_path = os.path.join(os.path.dirname(__file__), "clean_ratings_PTs.sql")
    with open(sql_path, "r", encoding='utf-8') as f:
        template = f.read()

    # Inject env vars — SQL file contains no credentials, only {placeholders}
    sql = (template
        .replace("{PROJECT_ID}", PROJECT_ID)
        .replace("{DATASET_ID}", DATASET_ID)
        .replace("{REC_TABLE_ID}", REC_TABLE_ID)
        .replace("{ORIGINAL_TABLE}", ORIGINAL_TABLE)
    )

    client = bigquery.Client(project=PROJECT_ID)
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    for i, stmt in enumerate(statements, 1):
        print(f"  Running statement {i}/{len(statements)}...")
        job = client.query(stmt)
        job.result()  # wait for completion

    print(f"✓ Data cleaned and written to {PROJECT_ID}.{DATASET_ID}.{REC_TABLE_ID}")

# Stage 3: Standardize ratings
def standardize_ratings():
    print("▶ Stage 3: Standardizing Ratings...")

    # Read the SQL standardization script
    sql_path = os.path.join(os.path.dirname(__file__), "standardize_ratings.sql")
    with open(sql_path, "r", encoding='utf-8') as f:
        template = f.read()

    # Inject env vars — SQL file contains no credentials, only {placeholders}
    sql = (template
        .replace("{PROJECT_ID}", PROJECT_ID)
        .replace("{DATASET_ID}", DATASET_ID)
        .replace("{REC_TABLE_ID}", REC_TABLE_ID)
    )
    client = bigquery.Client(project=PROJECT_ID)

    statements = [s.strip() for s in sql.split(";") if s.strip()]
    for i, stmt in enumerate(statements, 1):
        print(f"  Running statement {i}/{len(statements)}...")
        job = client.query(stmt)
        job.result()  # wait for completion

    print(f"✓ Ratings standardized and written to {PROJECT_ID}.{DATASET_ID}.{REC_TABLE_ID}")

# Stage 4: Add Recommendation Type
def add_rec_type():
    print("▶ Stage 4: Adding Recommendation Type...")

    sql_path = os.path.join(os.path.dirname(__file__), "recommendation_type.sql")
    with open(sql_path, 'r', encoding='utf-8') as f:
        template = f.read()
 
    # Inject env vars — SQL file contains no credentials, only {placeholders}
    sql = template.format(
        PROJECT_ID      = PROJECT_ID,
        DATASET_ID      = DATASET_ID,
        REC_TABLE_ID    = REC_TABLE_ID,
    )
 
    client = bigquery.Client(project=PROJECT_ID)
 
    # BigQuery requires each statement to be run separately
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    for i, stmt in enumerate(statements, 1):
        print(f"  Running statement {i}/{len(statements)}...")
        job = client.query(stmt)
        job.result()  # wait for completion
 
    print(f"  Final table ready: {PROJECT_ID}.{DATASET_ID}.{REC_TABLE_ID}")

# ── Run pipeline ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    data_cleaning()
    standardize_ratings()
    add_rec_type()
    print("\n✓ Data cleaning and feature engineering complete.")