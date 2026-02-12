# 💹 QuantOps: Autonomous Trading Execution & PnL Verification Engine

**QuantOps** is a high-reliability backend engine designed for the autonomous execution of quantitative trading strategies. Built with a "Reliability-First" philosophy, this suite handles the mission-critical plumbing of a trading system - orchestration, signal verification, risk management, and service persistence - allowing developers to focus on strategy research rather than infrastructure.

---

## 🔥 The Problem: The "Hobbyist to Professional" Gap
Most trading bots are simple scripts that fail during network instability or provide unverified performance data. **QuantOps** bridges this gap by introducing **Transactional Verification**: every signal generated is tracked, timestamped, and verified against real-world price discovery (via `yfinance`) before impacting the internal ledger.

---

## 🛡️ Architecture: High-Availability Execution
1.  **Autonomous Worker Hub**: The core background service (`worker.py`) performs continuous asset scanning across multiple timeframes (3h, 6h, 1d) using a modular **Alpha Scoring** system.
2.  **Risk Orchestration**: Implements deterministic slot management and correlation checks, ensuring that no single asset class over-exposes the portfolio.
3.  **Self-Healing Service Manager**: Includes a robust `service_manager.sh` for Unix-like systems that monitors worker health, handles PID management, and manages high-volume log rotation.
4.  **Deterministic PnL Verification**: A standalone service (`verify_pnl.py`) pulls ground-truth data from external APIs to audit the execution engine's performance, eliminating "simulated bias."

---

## 🛠️ Core Components
- **`backend/worker.py`**: The central strategy and execution orchestrator.
- **`backend/core/risk.py`**: Logic for position sizing and portfolio correlation management.
- **`scripts/simulate_returns.py`**: Engine for probabilistic backtesting and return modeling.
- **`service_manager.sh`**: Production-grade service persistence and monitoring logic.

---

## ✨ Engineering Wins
- **Mission-Critical Reliability**: Successfully managed 24/7 background execution with automated crash recovery and state persistence.
- **Data Integrity**: Developed a zero-trust verification loop that reconciles internal trade logs with external market truth.
- **Systemic Scalability**: Modular "Universe" configuration allows for scaling across crypto, stocks, and forex with zero architecture changes.

---

**Built for the high-stakes quantitative architect. 💹🛠️**
