# 💹 QuantOps: Trading Execution & Verification

A Python-based backend service for automating the execution of trading strategies. This suite provides the infrastructure needed for signal verification, position tracking, and service management.

- ⚙️ **Execution Hub**: A background worker (`worker.py`) that handles scanning and order placement.
- 🧪 **Verification Suite**: A standalone utility (`verify_pnl.py`) for auditing execution results against market data.
- 📦 **Service Manager**: Shell scripts for 24/7 background execution and PID management.

### Key Logic
The worker scans specified assets and timeframes (3h, 6h, 1d), scores signals, and manages order slots. Every completed trade is audited to reconcile internal logs with external market truth.

### Components
- `backend/worker.py`: Strategy and execution orchestrator.
- `backend/core/risk.py`: Position sizing and correlation logic.
- `service_manager.sh`: Service persistence and monitoring logic for Unix systems.
