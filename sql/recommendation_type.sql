-- add new column Recommendation_Type
ALTER TABLE `{PROJECT_ID}.{DATASET_ID}.{REC_TABLE_ID}`
ADD COLUMN IF NOT EXISTS Recommendation_Type STRING;

-- populate Recommendation_Type
UPDATE `{PROJECT_ID}.{DATASET_ID}.{REC_TABLE_ID}`
SET Recommendation_Type = CASE

    -- True Initiation — no prior rating but has new rating
    WHEN (Numeric_Rating_Before IS NULL AND Numeric_Rating_After IS NOT NULL)
    AND (Price_Target_Before IS NULL AND Price_Target_After IS NOT NULL)
        THEN 'Initiation' 
    -- Upgrade (rating improved)
    WHEN Numeric_Rating_After > Numeric_Rating_Before 
        THEN 'Upgrade'
    -- Downgrade (rating worsened)
    WHEN Numeric_Rating_After < Numeric_Rating_Before 
        THEN 'Downgrade'
    -- Same rating — check price target
    WHEN Numeric_Rating_After = Numeric_Rating_Before THEN
        CASE
            -- Both PTs null → Reiteration
            WHEN Price_Target_Before IS NULL 
            AND Price_Target_After IS NULL 
                THEN 'Reiteration'
            -- PT raised
            WHEN Price_Target_After > Price_Target_Before 
                THEN 'PT Raise'
            -- PT cut
            WHEN Price_Target_After < Price_Target_Before 
                THEN 'PT Cut'
            -- PT same
            WHEN Price_Target_After = Price_Target_Before 
                THEN 'Reiteration'
        ELSE 'Reiteration'
        END

    -- Rating_Before exists, Rating_After is null
    WHEN (Numeric_Rating_After IS NULL AND Numeric_Rating_Before IS NOT NULL) -- add brackets for clarity
    OR (Numeric_Rating_After IS NULL AND Numeric_Rating_Before IS NULL)
    OR (Price_Target_After IS NOT NULL AND Price_Target_Before IS NOT NULL)
        THEN CASE
            WHEN Price_Target_After > Price_Target_Before
                THEN 'Reprice Up'
            WHEN Price_Target_After < Price_Target_Before
                THEN 'Reprice Down'
            WHEN Price_Target_After = Price_Target_Before
                THEN 'Reiteration'
            ELSE NULL
        END
    ELSE NULL
END
WHERE TRUE;