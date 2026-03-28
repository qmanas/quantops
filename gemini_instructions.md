# Algo Trader: AI Quant Instructions

You are the digital co-pilot for **Algo Trader v1**, a Quant Trade Ledger and Strategy Execution system.

## Core Terminology
- **Trade Ledger**: The DuckDB backend that records every decision, bar, and PnL event.
- **Trader Command**: The Vue 3 dashboard used for strategy visualization and historical simulation.
- **Strategy Windows**: Segmented time ranges used for testing specific algorithm configurations.
- **DAAE**: Dynamic Multi-Asset Allocation Engine.

## Core Philosophy
1.  **High-Probability Alpha**: Focus strictly on timeframes >= 3h. High-frequency noise (< 1h) is discarded to improve expectancy and reduce fee-drag.
2.  **Trade Ledger**: Every decision must be logged with its full state for forensics. We optimize for "Alpha over Volume".
3.  **Capital Readiness**: Real capital ($5+) is ONLY deployed once:
    -   The TCN stub is replaced with verified model weights.
    -   7-day backtest/paper win rate is > 55%.
    -   Average PnL per trade covers expected slippage/fees.

## Architecture

### 1. Data Layer (`backend/core/data.py`)
-   **Provider**: Dual-provider system.
    -   **Crypto**: Uses `ccxt` (Binance) for real-time OHLCV. Requires NO API keys for public data.
    -   **Stocks/Legacy**: Uses `yfinance`.
-   **Resampling**: Custom logic handles non-standard intervals (3h, 6h, 12h) by aggregating 1h bars.

### 2. Logic Engine
-   **Features** (`backend/core/features.py`): Transforms OHLCV into 64x12 sliding windows.
-   **Model** (`backend/core/model.py`): Causal TCN. *Currently a stub*; must be replaced for live trading.
-   **Risk** (`backend/core/risk.py`): Applies the logic described in Core Philosophy.

### 3. Backend & Storage
-   **API** (`backend/main.py`): FastAPI.
-   **DB** (`backend/db`): DuckDB.
-   **Integrity**: The `decisions` table uses a `PRIMARY KEY (ts, symbol, timeframe)` to prevent redundant logs for the same bar.
-   **Logging**: `StorageManager.log_decision` uses `ON CONFLICT DO NOTHING` to gracefully handle duplicate scan attempts.
-   **Structure**: Uses `DecisionObject` (defined in `backend/core/risk.py`).

### 4. Execution Layer (`backend/execution/exchange.py`)
-   **Interface**: `ExchangeInterface` provides a unified API for data fetching and order creation.
-   **Clients**:
    -   `CCXTClient`: Fetches real-time crypto data.
    -   `PaperExchange`: Simulates market orders (fills, fees, slippage) without requiring user funds or keys.
-   **Integration**: Managed by `get_exchange()` helper which defaults to Paper Mode.

### 5. Interface (CLI)
-   **Tool**: `cli/trader.py`.
-   **Commands**:
    -   `predict <target>`: Manual snapshot inference.
    -   `scan --universe ...`: Multi-symbol screening.
    -   `replay`: Historical simulation.
    -   `analyze`: Review logs.

## Future Agent Instructions

### When Updating the Model
-   The current `TCNModel` in `backend/core/model.py` is a **STUB**.
-   When integrating real weights, load them in `__init__` and run actual inference in `predict()`.
-   Ensure output format matches the dictionary expected by `DecisionObject`.

### When Adding Data Sources
-   Update `DataProvider.fetch_bars` in `backend/core/data.py` to route the new symbol/category.
-   Ensure `fetch_bars` returns a standardized DataFrame: `[timestamp, open, high, low, close, volume]`.

### When Scaling Execution
-   The `PaperExchange` currently only prints logs.
-   To transition to live trading, implement a `LiveExchange` subclass in `backend/execution/exchange.py` using `ccxt` with API keys.

### When Deploying / Scaling Infrastructure
-   DuckDB is local. For multiple concurrent writers or remote deployment, consider migrating `StorageManager` to PostgreSQL or using DuckDB in a more concurrency-friendly mode (currently file-lock issues occur if API and CLI run simultaneously).

### Frontend
-   A generic Vite+React structure exists in `frontend/` but is unused. The focus is CLI. Revive only if visual charts are explicitly requested.
