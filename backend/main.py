from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import uvicorn
import pandas as pd
from datetime import datetime

# Core imports
from core.data import DataProvider
from core.features import FeatureGenerator
from core.model import TCNModel
from core.risk import RiskMap, DecisionObject
from db.storage import StorageManager

app = FastAPI(title="Algo-Trader Research Engine")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
data_provider = DataProvider()
feature_gen = FeatureGenerator()
model = TCNModel()
risk_map = RiskMap()
storage = StorageManager(read_only=True)

@app.get("/health")
def health_check():
    return {"status": "ok", "components": "initialized"}

@app.get("/decision/latest")
def get_latest_decision(symbol: str = "SPY"):
    try:
        # 1. Fetch latest data
        df = data_provider.fetch_bars(symbol, period="1mo", interval="1h")
        
        # 2. Generate features
        windows = feature_gen.generate_features(df)
        if len(windows) == 0:
            raise HTTPException(status_code=400, detail="Not enough data to generate features")
            
        current_window = windows[-1]
        
        # 3. Model Inference
        prediction = model.predict(current_window)
        
        # 4. Risk Map Application
        risk_output = risk_map.apply(
            raw_signal=prediction["raw_signal"],
            vol_forecast=prediction["vol_forecast"]
        )
        
        # 5. Construct Decision Object
        last_bar = df.iloc[-1]
        decision = DecisionObject(
            ts=last_bar["timestamp"].isoformat(),
            symbol=symbol,
            bar_index=len(df), # In a real system, this would be a cumulative ID
            **prediction,
            **risk_output,
            model_version=model.version,
            risk_version=risk_map.version
        )
        
        # 6. Log it
        storage.log_decision(decision)
        
        return decision
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/decision/range")
def get_decisions_range(
    symbol: str, 
    start: Optional[str] = None, 
    end: Optional[str] = None
):
    import numpy as np
    df = storage.get_decisions(symbol, start, end)
    # Handle NaN for JSON serialization
    df = df.replace({np.nan: None})
    # Convert numpy/pandas types to standard python types for JSON serialization
    records = df.to_dict(orient="records")
    return records

@app.get("/replay/bars")
def get_replay_bars(
    symbol: str,
    start: Optional[str] = None,
    end: Optional[str] = None
):
    # For now, we can just fetch from data provider if not in DB, 
    # but strictly we should query DB. 
    # Let's populate DB on demand for now for simplicity
    try:
        # Fetch data to ensure populate
        # In a real app we'd have a separate ingestion process
        pass 
    except:
        pass
        
    data = data_provider.fetch_bars(symbol, period="1y", interval="1h")
    # Store relevant slice would happen here in a real ingestion pipeline
    
    # Filter memory dataframe for return
    if start:
        data = data[data['timestamp'] >= start]
    if end:
        data = data[data['timestamp'] <= end]
        
    return data.to_dict(orient="records")

from pydantic import BaseModel

class ReplayRequest(BaseModel):
    symbol: str
    start: Optional[str] = None
    end: Optional[str] = None

@app.post("/replay/run")
def run_replay(req: ReplayRequest):
    try:
        # 1. Fetch Data
        df = data_provider.fetch_bars(req.symbol, period="2y", interval="1h")
        
        # Filter
        if req.start:
            df = df[df['timestamp'] >= pd.to_datetime(req.start).tz_localize(df['timestamp'].dt.tz)]
        if req.end:
            df = df[df['timestamp'] <= pd.to_datetime(req.end).tz_localize(df['timestamp'].dt.tz)]
            
        if len(df) < 65:
            return {"status": "error", "message": "Not enough data"}

        # 2. Generate Features
        all_windows = feature_gen.generate_features(df)
        
        decisions = []
        
        # 3. Inference Loop
        # We start from where windows enable us to (index 64-1)
        # But windows array is aligned such that windows[i] is for bar at (i + 64 - 1)
        
        for i, window in enumerate(all_windows):
            bar_idx = i + 64 - 1
            # Ensure index within bounds (it should be)
            if bar_idx >= len(df):
                break
                
            current_bar = df.iloc[bar_idx]
            
            # Predict
            pred = model.predict(window)
            
            # Risk
            risk = risk_map.apply(pred["raw_signal"], pred["vol_forecast"])
            
            # Decision
            decision = DecisionObject(
                ts=current_bar["timestamp"].isoformat(),
                symbol=req.symbol,
                bar_index=bar_idx, # TODO: Handle global indexing
                **pred,
                **risk,
                model_version=model.version,
                risk_version=risk_map.version
            )
            decisions.append(decision)
            
            # Real-time logging (optional, here we batch at end for speed in replay)
            # storage.log_decision(decision) 
            
        # Batch Log
        # We need a batch insert which StorageManager doesn't formally expose efficiently yet
        # But we can loop:
        for d in decisions:
            storage.log_decision(d)
            
        return {
            "status": "success", 
            "count": len(decisions), 
            "first": decisions[0].ts if decisions else None,
            "last": decisions[-1].ts if decisions else None
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/missions")
def get_missions():
    import numpy as np
    df = storage.get_missions()
    # Handle NaN for JSON serialization
    df = df.replace({np.nan: None})
    return df.to_dict(orient="records")

class MissionRequest(BaseModel):
    name: str
    start_ts: str
    notes: Optional[str] = None
    params: Optional[dict] = None

@app.post("/mission")
def create_mission(req: MissionRequest):
    mission_id = storage.create_mission(
        name=req.name,
        start_ts=req.start_ts,
        params=req.params,
        notes=req.notes
    )
    return {"status": "success", "mission_id": mission_id}

@app.get("/mission/simulate")
def simulate_range(start: str, end: Optional[str] = None):
    """Calculate theoretical PnL for a given time window."""
    try:
        # If end is not provided, use now
        if not end:
            end = datetime.now().isoformat()
            
        # 1. Pull all decisions in range
        # We'll use the 'Crypto-Paper-Test' model equivalence logic (sum of realized_pnl)
        query = f"""
            SELECT realized_pnl 
            FROM decisions 
            WHERE ts >= '{start}' AND ts <= '{end}' AND realized_pnl IS NOT NULL
        """
        pnls = storage.conn.execute(query).df()['realized_pnl']
        
        if pnls.empty:
            return {"roi_ratio": 1.0, "roi_pct": 0.0, "count": 0}
            
        import numpy as np
        roi_ratio = np.prod(1 + pnls.values)
        if np.isnan(roi_ratio):
            roi_ratio = 1.0
        roi_pct = (roi_ratio - 1) * 100
        
        return {
            "roi_ratio": float(roi_ratio),
            "roi_pct": float(roi_pct),
            "count": len(pnls),
            "start": start,
            "end": end
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/debug/inventory")
def get_data_inventory():
    """Summary of available data for charting."""
    try:
        query = """
            SELECT 
                symbol, 
                count(*) as total_decisions,
                count(realized_pnl) as signals_with_pnl,
                min(ts) as first_seen,
                max(ts) as last_seen
            FROM decisions 
            GROUP BY symbol
            ORDER BY total_decisions DESC
        """
        df = storage.conn.execute(query).df()
        import numpy as np
        df = df.replace({np.nan: None})
        return df.to_dict(orient="records")
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
