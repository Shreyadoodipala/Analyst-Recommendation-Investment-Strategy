CREATE OR REPLACE TABLE `{PROJECT_ID}.{DATASET_ID}.{REC_TABLE_ID}` AS
WITH split_values AS (
  SELECT
    *,
    -- Step 1: if value contains '»', keep only the part AFTER the last '»'
    TRIM(
      COALESCE(REGEXP_EXTRACT(Rating_Before, r'([^»]+)$'), Rating_Before)
    ) AS rating_before_split,
    TRIM(
      COALESCE(REGEXP_EXTRACT(Rating_After, r'([^»]+)$'), Rating_After)
    ) AS rating_after_split,
    TRIM(
      COALESCE(REGEXP_EXTRACT(Price_Target_Before, r'([^»]+)$'), Price_Target_Before)
    ) AS price_target_before_split,
    TRIM(
      COALESCE(REGEXP_EXTRACT(Price_Target_After, r'([^»]+)$'), Price_Target_After)
    ) AS price_target_after_split
  FROM `{PROJECT_ID}.{DATASET_ID}.{ORIGINAL_TABLE}`
),

cleaned_values AS (
  SELECT
    * EXCEPT (
      Rating_Before, Rating_After, Price_Target_Before, Price_Target_After,
      rating_before_split, rating_after_split,
      price_target_before_split, price_target_after_split
    ),

    -- Ratings: keep only alphabetic characters (after split + trim)
    REGEXP_REPLACE(rating_before_split, r'[^a-zA-Z]', '') AS Rating_Before,
    REGEXP_REPLACE(rating_after_split, r'[^a-zA-Z]', '') AS Rating_After,

    -- Price targets: keep only digits and decimal point (after split + trim)
    REGEXP_REPLACE(price_target_before_split, r'[^0-9.]', '') AS Price_Target_Before_str,
    REGEXP_REPLACE(price_target_after_split, r'[^0-9.]', '') AS Price_Target_After_str

  FROM split_values
)

SELECT
  * EXCEPT (Price_Target_Before_str, Price_Target_After_str),

  -- Safe cast cleaned price target strings to FLOAT64
  SAFE_CAST(Price_Target_Before_str AS FLOAT64) AS Price_Target_Before,
  SAFE_CAST(Price_Target_After_str AS FLOAT64) AS Price_Target_After

FROM cleaned_values;