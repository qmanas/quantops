import duckdb
import pandas as pd
import yfinance as yf
import os
from datetime import datetime, timezone

# Resolve DB path
base_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(base_dir, "backend", "data", "trader.db")

conn = duckdb.connect(db_path)

# Query all decisions from today
query = """
SELECT symbol, ts, direction, target_exposure, raw_signal, vol_forecast
FROM decisions
WHERE ts >= '2026-01-31 00:00:00'
ORDER BY ts ASC
"""

df = conn.execute(query).df()

if df.empty:
    print("No decisions logged for today yet.")
    exit()

print(f"Found {len(df)} decisions. Verifying against current market data...")

results = []

for _, row in df.iterrows():
    symbol = row['symbol']
    if symbol == "MANUAL_UPLOAD":
        continue
        
    try:
        ticker = yf.Ticker(symbol)
        # Fetch 1h data for last 3 days to cover all timezones and boundaries
        hist_1h = ticker.history(period="3d", interval="1h")
        if hist_1h.empty:
            continue
            
        # Get current price
        current_data = ticker.history(period="1d", interval="1m")
        current_price = current_data['Close'].iloc[-1] if not current_data.empty else hist_1h['Close'].iloc[-1]
        
        # Pred timestamp handling
        pred_ts = pd.to_datetime(row['ts'])
        if pred_ts.tzinfo is None:
            pred_ts = pred_ts.replace(tzinfo=timezone.utc)
            
        # Align hist_1h index to UTC if it isn't
        if hist_1h.index.tz is None:
            hist_1h.index = hist_1h.index.tz_localize('UTC')
        else:
            hist_1h.index = hist_1h.index.tz_convert('UTC')

        # Find entry price: the close of the bar at or just after pred_ts
        # yfinance index is the START of the bar. 
        # If we logged at 1:15 AM, the entry price should be based on the 1:00 AM bar's close.
        # Let's find the bar whose period contains or ends at pred_ts.
        
        # Simple method: find the bar closest to pred_ts
        closest_idx = hist_1h.index.get_indexer([pred_ts], method='nearest')[0]
        entry_price = hist_1h['Close'].iloc[closest_idx]
        actual_ts = hist_1h.index[closest_idx]
        
        if entry_price and current_price:
            pnl_pct = (current_price - entry_price) / entry_price
            if row['direction'] == 'short':
                pnl_pct = -pnl_pct
                
            results.append({
                "Symbol": symbol,
                "Timeframe": "1h", # Simplified for now
                "Pred Time (UTC)": pred_ts.strftime('%H:%M'),
                "Realized Bar (UTC)": actual_ts.strftime('%H:%M'),
                "Dir": row['direction'].upper(),
                "Entry": round(entry_price, 2),
                "Current": round(current_price, 2),
                "PnL %": round(pnl_pct * 100, 3)
            })
            
    except Exception as e:
        print(f"Error verifying {symbol}: {e}")

if results:
    res_df = pd.DataFrame(results)
    # Remove duplicates if multiple scans overlapped
    res_df = res_df.drop_duplicates(subset=['Symbol', 'Realized Bar (UTC)', 'Dir'])
    print("\n=== VERIFICATION RESULTS (Last 3 Hours) ===")
    print(res_df.to_string(index=False))
else:
    print("No matches found for verification.")

