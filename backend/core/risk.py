from pydantic import BaseModel
from typing import Literal, Optional
from datetime import datetime

class DecisionObject(BaseModel):
    model_config = {'protected_namespaces': ()}
    ts: str
    symbol: str
    bar_index: int

    # model
    p_up: float
    p_down: float
    entropy: float
    raw_signal: float

    # forecast uncertainty
    vol_forecast: float
    vol_z: float

    # risk map outputs
    neutral_zone: bool
    risk_scalar: float
    exposure_cap: float

    # final action
    target_exposure: float
    direction: Literal["long", "short", "neutral"]
    timeframe: str # e.g. "1h", "3h"

    # verification (optional, filled later)
    realized_pnl: Optional[float] = None
    verified_at: Optional[str] = None

    # meta
    model_version: str
    risk_version: str

class RiskMap:
    """
    Applies the "secret sauce" risk map logic.
    - Neutral Zone Deadband
    - Inverse Volatility Scaling
    - Exposure Capping
    """
    
    def __init__(
        self, 
        deadband: float = 0.1, 
        base_vol: float = 0.02, 
        max_exposure: float = 0.25,
        halt_limit: float = 0.25,  # Relaxed to 25% to allow "Buy the Dip"; scaling handles the sizing.
        version: str = "rm_1.2"
    ):
        self.deadband = deadband
        self.base_vol = base_vol
        self.max_exposure = max_exposure
        self.halt_limit = halt_limit
        self.version = version

    def apply(self, raw_signal: float, vol_forecast: float) -> dict:
        """
        raw_signal: float between -1.0 (strong short) and 1.0 (strong long)
        vol_forecast: float representing predicted volatility
        """
        # 0. Virtual Circuit Breaker (Abnormal Market Volatility)
        if vol_forecast > self.halt_limit:
            return {
                "neutral_zone": True,
                "risk_scalar": 0.0,
                "exposure_cap": self.max_exposure,
                "target_exposure": 0.0,
                "direction": "neutral",
                "metadata": "VOLATILITY_HALT_TRIGGERED"
            }

        # 1. Neutral Zone Deadband
        # If signal is weak, we don't trade.
        neutral_zone = abs(raw_signal) < self.deadband
        
        if neutral_zone:
            signal_after_deadband = 0.0
        else:
            # Shift signal so it starts from 0 after deadband
            sign = 1 if raw_signal > 0 else -1
            signal_after_deadband = (abs(raw_signal) - self.deadband) / (1.0 - self.deadband) * sign

        # 2. Inverse Volatility Scaling
        # scale = base_vol / current_vol. If vol is high, we trade less.
        risk_scalar = min(1.0, self.base_vol / max(vol_forecast, 1e-6))
        
        scaled_exposure = signal_after_deadband * risk_scalar
        
        # 3. Exposure Cap
        # Ensure we never bet more than X% of the account.
        target_exposure = max(-self.max_exposure, min(self.max_exposure, scaled_exposure))
        
        direction = "neutral"
        if target_exposure > 0.01:
            direction = "long"
        elif target_exposure < -0.01:
            direction = "short"

        return {
            "neutral_zone": neutral_zone,
            "risk_scalar": risk_scalar,
            "exposure_cap": self.max_exposure,
            "target_exposure": round(target_exposure, 4),
            "direction": direction
        }

# SQL schema definition for decisions table
DECISIONS_TABLE_SCHEMA = """
    CREATE TABLE IF NOT EXISTS decisions (
        id INTEGER PRIMARY KEY,
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
        risk_version VARCHAR
    )
"""
# Ensure we have a sequence for ID if needed, but DuckDB handles bit-increment or we can just use ROWID.
# Let's just use regular columns for now.

if __name__ == "__main__":
    # Test cases
    rm = RiskMap(deadband=0.15, base_vol=0.015, max_exposure=0.5)
    
    # Case 1: Strong signal, low vol
    print("Strong signal, low vol:", rm.apply(raw_signal=0.8, vol_forecast=0.01))
    
    # Case 2: Weak signal (inside deadband)
    print("Weak signal:", rm.apply(raw_signal=0.1, vol_forecast=0.01))
    
    # Case 3: Strong signal, extreme vol
    print("Strong signal, high vol:", rm.apply(raw_signal=0.8, vol_forecast=0.05))
