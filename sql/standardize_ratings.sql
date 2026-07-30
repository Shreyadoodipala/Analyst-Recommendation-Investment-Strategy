CREATE OR REPLACE FUNCTION `{PROJECT_ID}.{DATASET_ID}.standardize_rating`(raw STRING)
RETURNS STRING AS (
    CASE UPPER(TRIM(raw))
    -- STRONG BUY
    WHEN 'STRONG BUY'        THEN 'Strong Buy'
    WHEN 'STRONGBUY'         THEN 'Strong Buy'
    WHEN 'CONVICTION BUY'    THEN 'Strong Buy'
    WHEN 'CONVICTIONBUY'     THEN 'Strong Buy'
    WHEN 'TOP PICK'          THEN 'Strong Buy'
    WHEN 'TOPPICK'           THEN 'Strong Buy'

    -- BUY 
    WHEN 'BUY'               THEN 'Buy'
    WHEN 'OUTPERFORM'        THEN 'Buy'
    WHEN 'OVERWEIGHT'        THEN 'Buy'
    WHEN 'ACCUMULATE'        THEN 'Buy'
    WHEN 'POSITIVE'          THEN 'Buy'
    WHEN 'OUTPERFORMER'      THEN 'Buy'
    -- Broker-specific "Buy" variants
    WHEN 'MKT OUTPERFORM'    THEN 'Buy'
    WHEN 'MKTOUTPERFORM'     THEN 'Buy'
    WHEN 'MARKET OUTPERFORM' THEN 'Buy'
    WHEN 'MARKETOUTPERFORM'  THEN 'Buy'
    WHEN 'MARKETOUTP'        THEN 'Buy'
    WHEN 'SECTOR OUTPERFORM' THEN 'Buy'
    WHEN 'SECTOROUTPERFORM'  THEN 'Buy'
    WHEN 'SECTOR OUTP'       THEN 'Buy'
    WHEN 'SECTOROUTP'        THEN 'Buy'
    WHEN 'SECTOR OUTPERF'    THEN 'Buy'
    WHEN 'SECTOROUTPERF'     THEN 'Buy'
    WHEN 'MARKET OUTP'       THEN 'Buy'
    WHEN 'MARKET OUTPERF'    THEN 'Buy'
    WHEN 'MARKETOUTPERF'     THEN 'Buy'
    WHEN 'R PERFORM TO OUTPERFORM' THEN 'Buy' 
    WHEN 'RPERFORMTOOUTPERFORM' THEN 'Buy'  

    -- HOLD 
    WHEN 'HOLD'              THEN 'Hold'
    WHEN 'NEUTRAL'           THEN 'Hold'
    WHEN 'EQUAL WEIGHT'      THEN 'Hold'
    WHEN 'EQUALWEIGHT'       THEN 'Hold'
    WHEN 'MARKET PERFORM'    THEN 'Hold'
    WHEN 'MARKETPERFORM'     THEN 'Hold'
    WHEN 'MARKET PERFO'      THEN 'Hold'
    WHEN 'MARKETPERFO'       THEN 'Hold'
    WHEN 'SECTOR PERFORM'    THEN 'Hold'
    WHEN 'SECTORPERFORM'     THEN 'Hold'
    WHEN 'SECTOR PERFO'      THEN 'Hold'
    WHEN 'SECTORPERFO'       THEN 'Hold'
    WHEN 'PEER PERFORM'      THEN 'Hold'
    WHEN 'PEERPERFORM'       THEN 'Hold'
    WHEN 'PERFORM'           THEN 'Hold'
    WHEN 'IN LINE'           THEN 'Hold'
    WHEN 'INLINE'            THEN 'Hold'
    WHEN 'MKT PERFORM'       THEN 'Hold'
    WHEN 'MKTPERFORM'        THEN 'Hold'
    WHEN 'MARKET PERF'       THEN 'Hold'
    WHEN 'MARKETPERF'        THEN 'Hold'
    WHEN 'SEC'               THEN 'Hold'
    WHEN 'SECTOR PERF'       THEN 'Hold'
    WHEN 'SECTORPERF'        THEN 'Hold'
    WHEN 'SECTOR WEIGHT'     THEN 'Hold'
    WHEN 'SECTORWEIGHT'      THEN 'Hold'
    WHEN 'FAIR VALUE'        THEN 'Hold'
    WHEN 'FAIRVALUE'         THEN 'Hold'
    WHEN 'MIXED'             THEN 'Hold'


    -- SELL 
    WHEN 'SELL'              THEN 'Sell'
    WHEN 'UNDERPERFORM'      THEN 'Sell'
    WHEN 'UNDERWEIGHT'       THEN 'Sell'
    WHEN 'REDUCE'            THEN 'Sell'
    WHEN 'NEGATIVE'          THEN 'Sell'
    WHEN 'UNDERPERFORMER'    THEN 'Sell'
    WHEN 'UNDER PERFORM'     THEN 'Sell'
    WHEN 'MKT UNDERPERFORM'  THEN 'Sell'
    WHEN 'MKTUNDERPERFORM'   THEN 'Sell'
    WHEN 'R PERFORM TO UNDERPERFORM' THEN 'Sell'
    WHEN 'RPERFORMTOUNDERPERFORM' THEN 'Sell'
    WHEN 'BELOWAVERAGE'      THEN 'Hold'

    -- STRONG SELL 
    WHEN 'STRONG SELL'       THEN 'Strong Sell'
    WHEN 'STRONGSELL'        THEN 'Strong Sell'
    WHEN 'SHORT'             THEN 'Strong Sell'
    WHEN 'AVOID'             THEN 'Strong Sell'

    --  UNMAPPABLE → NULL
    -- blanks, encoding artifacts
    ELSE NULL

  END
);

-- Main Query
CREATE OR REPLACE TABLE `{PROJECT_ID}.{DATASET_ID}.{REC_TABLE_ID}` AS
WITH standardized AS (
  SELECT *,
    `{PROJECT_ID}.{DATASET_ID}.standardize_rating`(Rating_Before) AS Rating_Before_Standardized,
    `{PROJECT_ID}.{DATASET_ID}.standardize_rating`(Rating_After)  AS Rating_After_Standardized
  FROM `{PROJECT_ID}.{DATASET_ID}.{REC_TABLE_ID}`
)

SELECT
  *,
  CASE Rating_Before_Standardized
    WHEN 'Strong Buy'  THEN  2
    WHEN 'Buy'         THEN  1
    WHEN 'Hold'        THEN  0
    WHEN 'Sell'        THEN -1
    WHEN 'Strong Sell' THEN -2
    ELSE NULL
  END AS Numeric_Rating_Before,
  CASE Rating_After_Standardized
    WHEN 'Strong Buy'  THEN  2
    WHEN 'Buy'         THEN  1
    WHEN 'Hold'        THEN  0
    WHEN 'Sell'        THEN -1
    WHEN 'Strong Sell' THEN -2
    ELSE NULL
  END AS Numeric_Rating_After
FROM standardized;

-- Audit table for unmapped ratings
CREATE OR REPLACE TABLE `{PROJECT_ID}.{DATASET_ID}.unmapped_ratings` AS
SELECT 
    'Rating_Before' AS Column_Name, 
    Rating_Before AS Unmapped_Rating,
    COUNT(*) AS Occurrences
FROM `{PROJECT_ID}.{DATASET_ID}.{REC_TABLE_ID}`
WHERE Rating_Before_Standardized IS NULL
AND Rating_Before IS NOT NULL
GROUP BY Rating_Before

UNION ALL

SELECT
    'Rating_After' AS Column_Name, 
    Rating_After AS Unmapped_Rating,
    COUNT(*) AS Occurrences
FROM `{PROJECT_ID}.{DATASET_ID}.{REC_TABLE_ID}`
WHERE Rating_After_Standardized IS NULL
AND Rating_After IS NOT NULL
GROUP BY Rating_After

ORDER BY Occurrences DESC;