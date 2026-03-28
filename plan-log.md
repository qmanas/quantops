# Plan Log

Every log entry MUST be made with the current development device system time (ISO 8601 or similar). Each entry should include a concise "git-commit" style summary of the changes.

*Note: Timestamps are critical for forensic audit and performance tracking.*

This file tracks the development history, decisions, and future improvement plans for the Algo-Trader "Quant Flight Recorder" application.

## 2026-01-31

### [ACTION] Project Inception & Scaffolding
- **Initialized Project**: Created directory structure for `backend/`, `frontend/`, `cli/`, `data/`, and `scripts/`.
- **Environment**: Set up Python virtual environment and installed dependencies (`fastapi`, `duckdb`, `yfinance`, `uvicorn`, `pandas`, `numpy`, `scipy`).
- **Frontend**: Initialized Vite + React project (currently paused per user request to focus on CLI).

### [ACTION] Core Logic Implementation
- **Data Layer**: Implemented `DataProvider` in `backend/core/data.py` using `yfinance`. Added support for custom intervals (3h, 6h, 12h) via manual resampling.
- **Feature Engineering**: Created `FeatureGenerator` in `backend.core.features` to produce 64x12 sliding windows.
- **Model Stub**: implemented `TCNModel` in `backend/core/model.py` simulating probabilistic output.
- **Risk Engine**: Implemented `RiskMap` in `backend/core/risk.py` with Neutral Zone, Volatility Scaling, and Exposure Capping logic.
- **Schema**: Defined `DecisionObject` for unified logging.

### [ACTION] Backend & Storage
- **Database**: Set up `DuckDB` in `backend/db/storage.py` to store `decisions` and `bars`.
- **API**: Created FastAPI server in `backend/main.py` with endpoints for live inference (`/decision/latest`), replay (`/replay/run`), and retrieval.

### [ACTION] CLI Development
- **Tool**: Built `cli/trader.py` as the primary interface.
- **Commands**:
    - `predict`: Run inference on current market or CSV snapshot.
    - `scan`: iterate through a universe of symbols.
    - `replay`: Historical simulation.
    - `analyze`: Review logged performance.
- **Resampling**: Added `--interval` support to `scan` command.

### [ACTION] Verification
- **Verified**: Ran predictive scans on `BTC-USD`, `ETH-USD`, `NVDA`, `COIN` across 1h, 3h, 6h, 12h, 1d timeframes.
- **Results**: Logged successful predictions to `trader.db`.
- **Simulation**: Created `simulate_returns.py` to project returns on ₹2000 investment.
- **Initial PnL Check (3:18 AM IST)**:
    - `BTC-USD` (1h): +0.011% (Long)
    - `ETH-USD` (1h): -0.189% (Long)
    - `COIN` (1h): 0.000% (Short)
    - `NVDA/SPY`: Correctly identified as Neutral/No Trade.

### [ACTION] Prediction Stack Summary
- **Data**: `yfinance` with custom internal resampling (up to 72h).
- **Feature Gen**: 64-bar window, multi-feature (returns, RSI, MA distances, Vol).
- **Inference**: Causal TCN (Currently stubbed with intelligent momentum + noise).
- **Risk**: Dynamic scaling via inverse volatility, deadband exclusion, and hard exposure caps.
- **Storage**: DuckDB "Flight Recorder".

### [ACTION] Commencing Automation
- Initiating `backend/worker.py` to automate scanning and prediction verification for the next 24 hours.


## 2026-02-17

### [ACTION] Pilot Status Analysis & Data Repair
- **Audit**: Discovered the background worker had stopped on 2026-02-08, leaving 15,000+ unverified decisions.
- **Forensics**: Identified a critical duplication bug where 17,000+ redundant decision rows were causing balance drainage during verification.
- **Repair**:
    - Deduplicated `decisions` table (reduced from 33k to 15k rows).
    - Implemented `PRIMARY KEY (ts, symbol, timeframe)` on `decisions` table in DuckDB.
    - Updated `StorageManager.log_decision` to use `ON CONFLICT DO NOTHING`.
    - Reset `wallets` and `transactions` to replay a clean verification.
- **Optimization**: Updated `worker.py` to use a batch limit (500) and prioritized recent verification (ORDER BY ts DESC) to clear the backlog faster.
- **Results**: Corrected Pilot ROI from ~2.9% to **+16.2%** after removing redundant loss deductions.

### [ACTION] Pilot Resumption
- Restarted `backend/worker.py` in accelerated verification mode (1-min cycles).

### [ACTION] Auto-Connect Crypto Integration
- **Data Migration**: Migrated crypto data fetching from `yfinance` to **CCXT** (Binance) for improved reliability and real-time access.
- **Execution Layer**: Built a unified `ExchangeInterface` in `backend/execution/exchange.py`.
- **Paper Trading**: Implemented `PaperExchange` to simulate live execution of signaled trades (fills, fees, slippage) without requiring user funds or keys.
- **Worker Upgrade**: Enhanced `backend/worker.py` to create paper orders immediately upon high-probability signals.
- **Verification**: Validated real-time BTC-USD data fetching and order fill simulation via `scripts/verify_crypto_logic.py`.

### [ACTION] Phase 1: Infrastructure & Segmentation
- **Architecture**: Implemented a modular `ProviderFactory` to support multiple broker APIs (Binance, Alpaca, etc.) in a unified way.
- **Segmentation**: Added `asset_class` and `provider` fields to wallets. Trades are now filtered so that Crypto signals only execute on Crypto-dedicated wallets.
- **Universe**: Expanded the scan universe to include the Top 20 Binance assets + 7 Tech stocks.
- **Forensics**: Built `backend/core/risk_audit.py` to serve as a risk optimization loop, providing data-driven exposure suggestions based on past performance.
### [ACTION] Deployment & Reliability (macOS Native)
- **Service**: Successfully migrated background worker to a native macOS `launchd` service (`com.user.algotrader.plist`). 
- **Management**: Created `service_manager.sh` for standardized lifecycle management.

## 2026-02-28T16:04:48+05:30
### [FEAT] Implemented DAAE (Dynamic Multi-Asset Allocation Engine)
- **Deployment**: Migrated from a simple scanner to a **Priority Slot** architecture (`MAX_ACTIVE_SLOTS=4`).
- **Alpha Scoring**: Implemented a ranking system where assets compete for capital based on `Signal Strength * Win Rate`.
- **Correlation Decoupling**: Added a 7-day correlation guard (>0.8 limit) to prevent redundant "effective" bets and "Cluster Crashes".
- **Tooling**: Built `scripts/potential_returns.py` for multi-currency (USD/INR) ROI projection.
- **Audit**: Corrected ROI "Ground Truth" to **-27.6%** after auditing the Feb 23rd systemic market flush.
- **Reliability**: Verified DAAE logic stability on the native macOS `launchd` service.

## 2026-02-28T16:28:15+05:30
### [REBRAND] Rebranded to Algo Trader v1
- **Themes**: Removed "Pilot/Mission" terminology. System is now branded as **Algo Trader v1**.
- **Dashboard**: Renamed "Mission Control" to **Trader Command**. Found in `frontend-trader`.
- **Registry**: Renamed "Flight Missions" to **Strategy Windows**.
- **Frontend**: Fixed Tailwind CSS v4 compatibility issues by migrating to `@tailwindcss/postcss` and the new `@import "tailwindcss";` syntax.
- **Visuals**: Replaced rocket iconography with **BarChart3** to emphasize professional quant analysis.

## Future Improvements / Todo
- [x] **Frontend**: Build the "Trader Command" dashboard in Vue 3.
- [ ] **Live Execution**: Add a secure vault for API keys to enable real financial execution on Binance.
- [ ] **Backtesting**: Implement a proper vectorized backtester instead of bar-by-bar replay.
- [ ] **Risk Policy**: Formalize the approval flow for `risk_audit` suggestions.
