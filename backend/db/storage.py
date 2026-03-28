import duckdb
import pandas as pd
from typing import List, Dict
import os
from datetime import datetime
from core.risk import DecisionObject

class StorageManager:
    """
    Manages DuckDB storage for the Quant Flight Recorder.
    Stores both market bars and model decisions.
    """
    
    def __init__(self, db_path: str = None, read_only: bool = False):
        # Resolve DB path
        # Standard way to find project_root/data/trader.db
        # storage.py is in backend/db/, so we need dirname(dirname(dirname(abspath(__file__))))
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_path = os.path.join(base_dir, "data", "trader.db")
            
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self.read_only = read_only
        self._init_conn()
        if not read_only:
            self._init_db()

    def _init_conn(self):
        import time
        for i in range(3):
            try:
                if self.read_only:
                    # Use a separate in-memory connection and ATTACH the file as read-only
                    self.conn = duckdb.connect(":memory:")
                    self.conn.execute(f"ATTACH '{self.db_path}' AS db (READ_ONLY)")
                    self.conn.execute("USE db")
                else:
                    self.conn = duckdb.connect(self.db_path, read_only=False)
                return
            except Exception as e:
                if "Could not set lock" in str(e) and i < 2:
                    time.sleep(1)
                    continue
                raise e

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def _init_db(self):
        """Initialize tables if they don't exist."""
        # Decisions Table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                ts TIMESTAMP,
                symbol VARCHAR,
                timeframe VARCHAR,
                bar_index INTEGER,
                p_up DOUBLE,
                p_down DOUBLE,
                entropy DOUBLE,
                raw_signal DOUBLE,
                vol_forecast DOUBLE,
                vol_z DOUBLE,
                neutral_zone BOOLEAN,
                risk_scalar DOUBLE,
                exposure_cap DOUBLE,
                target_exposure DOUBLE,
                direction VARCHAR,
                realized_pnl DOUBLE,
                verified_at TIMESTAMP,
                model_version VARCHAR,
                risk_version VARCHAR,
                PRIMARY KEY (ts, symbol, timeframe)
            )
        """)
        
        # Bars Table (for replay)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS bars (
                timestamp TIMESTAMP,
                symbol VARCHAR,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume DOUBLE
            )
        """)

        # Wallets Table (replaces portfolios)
        self.conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS wallet_id_seq START 1;
            CREATE TABLE IF NOT EXISTS wallets (
                id INTEGER PRIMARY KEY DEFAULT nextval('wallet_id_seq'),
                user_id VARCHAR DEFAULT 'default',
                name VARCHAR NOT NULL,
                balance DOUBLE NOT NULL,
                initial_balance DOUBLE NOT NULL,
                currency VARCHAR NOT NULL,
                asset_class VARCHAR NOT NULL DEFAULT 'multi',
                provider VARCHAR NOT NULL DEFAULT 'paper',
                model_version VARCHAR,
                target_goal DOUBLE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Transactions Table (audit trail)
        self.conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS transaction_id_seq START 1;
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY DEFAULT nextval('transaction_id_seq'),
                wallet_id INTEGER NOT NULL,
                amount DOUBLE NOT NULL,
                type VARCHAR NOT NULL,
                symbol VARCHAR,
                decision_id INTEGER,
                metadata VARCHAR,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Missions Table (Flight Missions / Experiments)
        self.conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS mission_id_seq START 1;
            CREATE TABLE IF NOT EXISTS missions (
                id INTEGER PRIMARY KEY DEFAULT nextval('mission_id_seq'),
                name VARCHAR NOT NULL,
                start_ts TIMESTAMP NOT NULL,
                end_ts TIMESTAMP,
                params_json VARCHAR, -- Snapshot of config at start
                initial_roi DOUBLE,
                final_roi DOUBLE,
                notes TEXT,
                status VARCHAR DEFAULT 'ongoing', -- 'ongoing', 'completed', 'aborted'
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    def create_wallet(self, name: str, initial_balance: float, currency: str, 
                     asset_class: str = 'multi', provider: str = 'paper',
                     model_version: str = None, target_goal: float = None, user_id: str = 'default'):
        """Create a new wallet."""
        res = self.conn.execute("""
            INSERT INTO wallets (user_id, name, balance, initial_balance, currency, asset_class, provider, model_version, target_goal)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
        """, [user_id, name, initial_balance, initial_balance, currency, asset_class, provider, model_version, target_goal]).fetchone()
        return res[0]

    def get_wallets(self, user_id: str = None, model_version: str = None) -> pd.DataFrame:
        """Fetch wallets, optionally filtered by user_id or model_version."""
        query = "SELECT * FROM wallets WHERE 1=1"
        params = []
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        if model_version:
            query += " AND model_version = ?"
            params.append(model_version)
        return self.conn.execute(query, params).df() if params else self.conn.execute(query).df()

    def update_wallet_balance(self, wallet_id: int, new_balance: float):
        """Update wallet balance and timestamp."""
        self.conn.execute("""
            UPDATE wallets 
            SET balance = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        """, [new_balance, wallet_id])

    def log_transaction(self, wallet_id: int, amount: float, tx_type: str, 
                       symbol: str = None, decision_id: int = None, metadata: str = None):
        """Log a transaction to the audit trail."""
        self.conn.execute("""
            INSERT INTO transactions (wallet_id, amount, type, symbol, decision_id, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [wallet_id, amount, tx_type, symbol, decision_id, metadata])

    def get_transactions(self, wallet_id: int = None, limit: int = 100) -> pd.DataFrame:
        """Fetch transaction history."""
        if wallet_id:
            return self.conn.execute("""
                SELECT * FROM transactions WHERE wallet_id = ? ORDER BY timestamp DESC LIMIT ?
            """, [wallet_id, limit]).df()
        return self.conn.execute("SELECT * FROM transactions ORDER BY timestamp DESC LIMIT ?", [limit]).df()

    def log_decision(self, decision: DecisionObject):
        """Insert a decision object into the database."""
        # Convert Pydantic model to dict
        data = decision.dict()
        
        # Standardize timestamps
        data['ts'] = pd.to_datetime(data['ts'])
        if data.get('verified_at'):
            data['verified_at'] = pd.to_datetime(data['verified_at'])
            
        # Create a DataFrame with explicit column order to match the CREATE TABLE schema
        columns = [
            'ts', 'symbol', 'timeframe', 'bar_index', 
            'p_up', 'p_down', 'entropy', 'raw_signal', 
            'vol_forecast', 'vol_z', 'neutral_zone', 
            'risk_scalar', 'exposure_cap', 'target_exposure', 
            'direction', 'realized_pnl', 'verified_at', 
            'model_version', 'risk_version'
        ]
        
        df = pd.DataFrame([data])[columns]
        self.conn.execute("INSERT INTO decisions SELECT * FROM df ON CONFLICT DO NOTHING")

    def update_verification(self, symbol: str, ts: str, pnl: float):
        """Update a decision with realized PnL."""
        verified_at = datetime.now()
        # Convert incoming TS to a standardized string format for matching
        # DuckDB TIMESTAMP can match a string 'YYYY-MM-DD HH:MM:SS'
        ts_str = pd.to_datetime(ts).strftime('%Y-%m-%d %H:%M:%S')
        
        self.conn.execute("""
            UPDATE decisions 
            SET realized_pnl = ?, verified_at = ? 
            WHERE symbol = ? AND CAST(ts AS VARCHAR) LIKE ?
        """, [pnl, verified_at, symbol, f"{ts_str}%"])

    def save_bars(self, df: pd.DataFrame, symbol: str):
        """Save a batch of bars."""
        df_copy = df.copy()
        df_copy['symbol'] = symbol
        # Use relevant columns only
        cols = ['timestamp', 'symbol', 'open', 'high', 'low', 'close', 'volume']
        df_save = df_copy[cols]
        # DuckDB can register a pandas df as a virtual table
        self.conn.execute("INSERT INTO bars SELECT * FROM df_save")

    def get_decisions(self, symbol: str, start: str = None, end: str = None) -> pd.DataFrame:
        """Query decisions."""
        query = f"SELECT * FROM decisions WHERE symbol = '{symbol}'"
        if start:
            query += f" AND ts >= '{start}'"
        if end:
            query += f" AND ts <= '{end}'"
        query += " ORDER BY ts ASC"
        return self.conn.execute(query).df()

    def get_bars(self, symbol: str, start: str = None, end: str = None) -> pd.DataFrame:
        """Query bars."""
        query = f"SELECT * FROM bars WHERE symbol = '{symbol}'"
        if start:
            query += f" AND timestamp >= '{start}'"
        if end:
            query += f" AND timestamp <= '{end}'"
        query += " ORDER BY timestamp ASC"
        return self.conn.execute(query).df()

    def get_performance_stats(self, days: int = 30) -> pd.DataFrame:
        """Get win rates and avg pnl for all symbols in the last X days."""
        query = f"""
            SELECT 
                symbol, 
                COUNT(*) as total_trades, 
                AVG(realized_pnl) as avg_pnl, 
                SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as win_rate
            FROM decisions 
            WHERE verified_at >= CURRENT_TIMESTAMP - INTERVAL '{days} days' 
            AND realized_pnl IS NOT NULL 
            GROUP BY symbol
        """
        return self.conn.execute(query).df()

    def get_recent_returns(self, symbols: List[str], days: int = 7) -> pd.DataFrame:
        """Get realized returns sequence for symbols to calculate correlation."""
        symbols_str = "', '".join(symbols)
        query = f"""
            SELECT ts, symbol, realized_pnl 
            FROM decisions 
            WHERE symbol IN ('{symbols_str}') 
            AND realized_pnl IS NOT NULL 
            AND ts >= CURRENT_TIMESTAMP - INTERVAL '{days} days'
            ORDER BY ts ASC
        """
        df = self.conn.execute(query).df()
        if df.empty:
            return pd.DataFrame()
        return df.pivot_table(index='ts', columns='symbol', values='realized_pnl')

    def get_active_slots(self) -> List[str]:
        """Get symbols of currently 'active' predictions (not yet verified)."""
        query = "SELECT DISTINCT symbol FROM decisions WHERE verified_at IS NULL"
        res = self.conn.execute(query).fetchall()
        return [r[0] for r in res]

    # Mission Management
    def create_mission(self, name: str, start_ts: str, params: Dict = None, notes: str = None):
        """Register a new Flight Mission."""
        import json
        params_str = json.dumps(params) if params else None
        res = self.conn.execute("""
            INSERT INTO missions (name, start_ts, params_json, notes)
            VALUES (?, ?, ?, ?)
            RETURNING id
        """, [name, start_ts, params_str, notes]).fetchone()
        return res[0]

    def get_missions(self) -> pd.DataFrame:
        """Fetch all missions."""
        return self.conn.execute("SELECT * FROM missions ORDER BY start_ts DESC").df()

    def update_mission_status(self, mission_id: int, status: str, end_ts: str = None, final_roi: float = None):
        """Close or update a mission."""
        self.conn.execute("""
            UPDATE missions 
            SET status = ?, end_ts = ?, final_roi = ?
            WHERE id = ?
        """, [status, end_ts, final_roi, mission_id])

if __name__ == "__main__":
    # Test storage
    sm = StorageManager("data/test_trader.db")
    
    # Mock data
    mock_decision = DecisionObject(
        ts="2026-01-31T14:30:00Z",
        symbol="SPY",
        bar_index=1,
        p_up=0.6,
        p_down=0.4,
        entropy=0.67,
        raw_signal=0.2,
        vol_forecast=0.01,
        vol_z=1.0,
        neutral_zone=False,
        risk_scalar=1.0,
        exposure_cap=0.25,
        target_exposure=0.1,
        direction="long",
        model_version="v1",
        risk_version="v1"
    )
    
    sm.log_decision(mock_decision)
    res = sm.get_decisions("SPY")
    print("Logged Decisions:")
    print(res)
