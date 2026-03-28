import duckdb
import pandas as pd
import os

# Resolve DB path
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db_path = os.path.join(base_dir, "data", "trader.db")

try:
    conn = duckdb.connect(db_path, read_only=True)
except Exception as e:
    print(f"Could not connect to DB (likely locked by worker): {e}")
    # Retry once after a short sleep if you were running this manually
    import time
    time.sleep(2)
    conn = duckdb.connect(db_path, read_only=True)

# Query to get the latest decision for each symbol. 
# Since we ran multiple intervals, we'll see multiple entries per symbol with slightly different timestamps (due to bar opens) 
# or we just show the last 20 entries to cover the recent batch scans.

query = """
SELECT 
    symbol, 
    ts, 
    timeframe,
    direction, 
    target_exposure, 
    realized_pnl,
    verified_at
FROM decisions 
ORDER BY ts DESC 
LIMIT 30
"""

df = conn.execute(query).df()

print("\n=== LATEST PREDICTIONS (Logged in Flight Recorder) ===")
print(df.to_markdown(index=False))
