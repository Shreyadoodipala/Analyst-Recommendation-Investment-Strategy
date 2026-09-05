# Methodology: Analyst Recommendation Bayesian Strategy

## 1. Data Sources and Coverage
The analysis combines analyst-level recommendation data with daily equity and benchmark price data.

### 1.1 Analyst recommendation data
The raw recommendation table from Anachart contains fields such as:
- Date
- Company_Name and Ticker
- Broker
- Analyst
- Rating_Before and Rating_After
- Price_Target_Before and Price_Target_After

This information is copied from the source dataset into a cleaned working table, where the rating strings and price targets are normalized before being classified into recommendation events.

### 1.2 Equity and benchmark data
For each stock appearing in the recommendation data, the daily adjusted close data is downloaded from Yahoo Finance for a window around the earliest and latest recommendation dates. A broad market proxy, QQQ, is also downloaded as the benchmark series.   
The merged files form the daily return universe used to compute idiosyncratic returns, benchmark-adjusted performance, and daily portfolio P&L.

### 1.3 Risk-free rate data
4 week T-bill rates are dwnloaded from FRED and converted to a daily series for Sharpe and Sortino calculations, as well as benchmark-adjusted excess-return analysis.

---

## 2. Data Cleaning and Feature Engineering

### 2.1 Rating standardization

Raw analyst rating labels are highly inconsistent across brokers and systems. The project normalizes them into a common five-category scale:
- Strong Buy
- Buy
- Hold
- Sell
- Strong Sell

A custom SQL mapping function is used to convert a wide range of broker-specific labels such as Outperform, Overweight, Market Perform, Underperform, Top Pick, and others into a standard taxonomy.  
Unmapped values are flagged for auditing rather than silently dropped.

### 2.2 Numeric rating conversion
Once standardized, each rating is converted into a numeric score:
- Strong Buy = 2
- Buy = 1
- Hold = 0
- Sell = -1
- Strong Sell = -2

This numeric scale enables directional comparisons and supports the recommendation signal construction.

### 2.3 Price target cleaning
Price targets are cleaned by stripping non-numeric characters and casting to a numeric float. This lets the system compare target changes and classify events like price-target raises, cuts, and re-pricings consistently.

### 2.4 Recommendation-type classification
Each recommendation event is classified into one of several event types, including:
- Upgrade *(both Rating_Before and Rating_After are present)*
- Downgrade *(both Rating_Before and Rating_After are present)*
- Initiation *(no previous rating or price target)*
- Reprice Up *(Ratings information is missing or incomplete)*
- Reprice Down *(Ratings information is missing or incomplete)*
- Reiteration *(Rating_Before and Rating_After are same)*
- Price Target Raise *(Rating_Before and Rating_After are same, but price targets are different)*
- Price Target Cut *(Rating_Before and Rating_After are same, but price targets are different)*

This classification is important because not all analyst actions are equivalent. Some events reflect a pure rating revision, while others represent a change in valuation guidance without a rating change.

---

## 3. Signal Construction
Each recommendation event is translated into a signed investment signal using the following methodology:

### 3.1 Signal coding
The project evaluates two signal forms:
- default
- shadow_sell

The default encoding maps recommendation actions to a directional signal:

- Upgrade / Reprice Up = +1
- Downgrade / Reprice Down = -1
- Price Target Raise = +0.5
- Price Target Cut = -0.5
- Initiation with improved rating = +1
- Initiation with worsened rating = -1
- (Remaining) = 0

The shadow_sell variant adds an extra negative signal for initiation events with a neutral rating, capturing the possibility that a neutral initiation may be interpreted as a negative signal relative to a previous lack of coverage.

This step produces a Signal variable used downstream for both the Bayesian strength estimation and the execution logic.

---

## 4. Impact and Drift Measurement
The strategy measures the return response around each recommendation event using idiosyncratic returns, which isolate the stock-specific component of price movement from broad market moves.

### 4.1 Beta and idiosyncratic return
For each stock, daily log returns are regressed against market log returns using a rolling window:

$$
R_{i,t} - \beta_i R_{m,t}
$$

where:
- $R_{i,t}$ is the stock's daily log return;
- $R_{m,t}$ is the benchmark's daily log return;
- $\beta_i$ is the rolling beta estimated from the prior window.

The resulting idiosyncratic return is the stock-level residual return after removing market exposure.

### 4.2 Idiosyncratic volatility normalization
To compare events with different volatility characteristics, the cumulative idiosyncratic returns are normalized by rolling idiosyncratic volatility estimated from prior daily residuals. 
The normalization is applied once at the start of each measurement window rather than cumulatively each day, which preserves comparability across time windows.

### 4.3 Event windows
For each recommendation date, the code computes two windows:
- Impact window: the period immediately around the recommendation date
- Drift window: the period after the immediate impact window.

The implementation uses a market-trading-day offset structure to ensure that recommendations are matched to the nearest available equity trading dates rather than calendar days alone.

The key event-return logic is:
- Impact return = cumulative idiosyncratic return in the short window around the recommendation,
- Drift return = cumulative idiosyncratic return in the subsequent drift window.

These windows are expressed in units of daily idiosyncratic volatility, making them directly comparable across different stock-factor regimes and event lengths.

---

## 5. Bayesian Analyst Strength Estimation
The central modeling step is the estimation of each analyst's latent skill or “strength.”

### 5.1 Bayesian shrinkage idea
The strategy assumes analysts have a latent ability parameter that is only imperfectly observed. Analysts with limited historical coverage should be shrunk toward zero because their estimated skill is noisy. This avoids overfitting to sparse recommendation histories.

The project estimates ex-ante analyst strength using a ridge-style Bayesian update:

$$
\hat{\mu} = \frac{\sum_i s_i r_i}{\lambda + \sum_i s_i^2}
$$

where:
- $s_i$ is the signed recommendation signal;
- $r_i$ is the observed impact or drift return associated with the event;
- $\lambda = 1 / \sigma_{prior}^2$ is the regularization term.

The prior standard deviation $\sigma_{prior}$ is a model parameter chosen over a grid, and it controls how strongly analyst-level estimates are shrunk toward zero.

### 5.2 Separate impact and drift strengths
For each analyst, the model computes two ex-ante strengths:
- impact strength
- drift strength

This distinction is essential because some analysts may identify strong immediate impact but weak post-event continuation, while others may be more valuable for the slower drift component.

### 5.3 Historical using only past recommendations
For each recommendation, the analyst's estimated strength is based only on recommendations that occurred before the current event. This avoids look-ahead bias and ensures the strategy uses only information available at the time of the decision.

---

## 6. Analyst Selection and Portfolio Construction

### 6.1 Analyst ranking
Once Bayesian strengths are computed, analysts are summarized by:
- average drift strength,
- average impact strength,
- number of recommendations.

Analysts with very few recommendations are removed, and the top-ranked analysts by average drift strength are selected. In the project, the default selection is the top 15 analysts by drift strength after filtering out analysts with fewer than 10 recommendations.

### 6.2 Test-period recommendation universe
The selected analyst list is applied to the out-of-sample period. Recommendations from non-selected analysts are excluded so the portfolio only trades the recommendations of analysts with evidence of persistent drift predictive power.

### 6.3 Trade creation
For each recommendation signal from the selected analysts, the code converts the signal into a trade using a directional rule:
- positive signal => long the stock;
- negative signal => short the stock.

Two position-sizing schemes are tested:
- equal: each trade is ±1 position size regardless of signal magnitude;
- signal_weight: the magnitude of the position scales with the signal strength.

### 6.4 Trade horizon and execution assumption
The backtest assumes the recommendation is invested at the next available trading session after the event date, which is a conservative timing assumption designed to be look-ahead safe. The strategy then holds the position for a prescribed number of trading days, denoted by drift_days.

For each trade, the exit date is the position's entry date plus the holding horizon, using the specific ticker's own trading calendar so missing or non-trading days are handled properly.

### 6.5 Daily portfolio aggregation
Daily positions are aggregated across overlapping trades in the same stock and date. Portfolio returns are then computed as a weighted average of stock returns under the net open-position structure, with daily exposure adjusted for position size.

---

## 7. Backtest and Performance Evaluation

### 7.1 Train/test split
The project uses a temporal split:
- train: before 2023-01-01
- test: from 2023-01-01 onward

This ensures that the analyst-strength ranking and model inputs are estimated on historical data only, with evaluation on a later out-of-sample period.

### 7.2 Portfolio metrics
The strategy is evaluated using standard risk-adjusted metrics:
- annualized return
- annualized volatility
- Sharpe ratio
- Sortino ratio
- maximum drawdown
- Calmar ratio
- hit rate of profitable trades
- win/loss ratio
- alpha and beta relative to the benchmark

These are computed on the daily portfolio return series and on the trade return series.

### 7.3 Transaction cost adjustment
The implementation also evaluates a transaction-cost-adjusted version of the portfolio using a 10 basis point assumption. Costs are estimated from daily portfolio turnover and deducted from the return stream.

### 7.4 Statistical inference
To assess uncertainty around Sharpe performance, the project uses a bootstrap confidence interval for the Sharpe ratio. It also performs a benchmark regression to estimate alpha and beta, with t-statistics and p-values for significance.

---

## 8. Grid Search and Model Selection
The backtest tests a grid of model configurations to identify which combination performs best in-sample and out-of-sample.

### 8.1 Parameter grid
- drift_days = 21, 29, 45
- sigma_prior = 0.02, 0.05, 0.1, 0.2, 0.3
- signal_method = default or shadow_sell
- position_sizing = equal or signal_weight

This yields a structured set of strategy variants for comparison.

### 8.2 Search process
The expensive signal construction and return-window calculations are precomputed once per signal method and drift-day configuration, then reused across sigma-prior and position-sizing combinations. This reduces repeated computation while preserving the same underlying logic.

The grid search ranks variants by Sharpe ratio and exports results to CSV files in the outputs directory.

---

## 9. Interpretation and Research Implications
The methodology is designed to test a specific and economically relevant hypothesis: that recommendation quality varies materially by analyst, and that the most informative analysts are those whose signals produce persistent post-event drift after accounting for idiosyncratic return dynamics and market exposure.

The strategy is intentionally conservative in several ways:

- it uses only past information for analyst strength estimation;
- it filters to analysts with enough history to be statistically meaningful;
- it avoids same-day trading assumptions that may create look-ahead bias;
- it evaluates both raw and cost-adjusted performance.

---
