import duckdb
import pandas as pd
import numpy as np
import os

PORTFOLIO_SIZE = 2000.0 # INR

# Resolve DB
base_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(base_dir, "backend", "data", "trader.db")
conn = duckdb.connect(db_path)

# Get latest decisions (distinct by symbol to avoid duplicates, get newest)
query = """
SELECT 
    symbol, 
    direction, 
    target_exposure, 
    vol_forecast,
    p_up
FROM decisions 
ORDER BY ts DESC 
LIMIT 50
"""
df = conn.execute(query).df()
# Dedup by symbol, taking first (latest)
df = df.drop_duplicates(subset=['symbol'], keep='first')

# Annualization factors for volatility
# Stub model assumed annualized vol output.
# We need period volatility for the PnL estimate.
# Assuming forecast was roughly annualized.
PERIOD_FACTOR = np.sqrt(252 * 8) # Approx for ~3h-4h check timeframe (conservative)

print(f"\nPotential Returns on ₹{PORTFOLIO_SIZE} Investment\n")
print(f"{'SYMBOL':<10} {'DIR':<6} {'RISK BET (₹)':<12} {'FULL BET (₹)':<12} {'EXP MOVE (±%)':<14} {'EST PnL (Risk)':<15}")
print("-" * 80)

for _, row in df.iterrows():
    if row['direction'] == 'neutral':
        continue
        
    # 1. Risk Managed Bet
    # exposure is fraction (e.g. 0.08)
    risk_bet_amt = abs(row['target_exposure']) * PORTFOLIO_SIZE
    
    # 2. Expected Move (1 Sigma)
    # De-annualize the volatility
    period_vol = row['vol_forecast'] / PERIOD_FACTOR
    
    # 3. PnL Scenarios
    # On Risk Managed Bet
    pnl_risk_positive = risk_bet_amt * period_vol
    pnl_risk_negative = risk_bet_amt * -period_vol
    
    # On Full Bet (If user puts entire 2000 into this one trade)
    pnl_full_positive = PORTFOLIO_SIZE * period_vol
    pnl_full_negative = PORTFOLIO_SIZE * -period_vol
    
    direction = row['direction'].upper()
    print(f"{row['symbol']:<10} {direction:<6} ₹{risk_bet_amt:<11.2f} ₹{PORTFOLIO_SIZE:<11.0f} {period_vol*100:<13.2f}% ₹{pnl_risk_positive:<.2f} to ₹{pnl_full_positive:<.2f}")

print("-" * 80)
print("Note: 'Risk Bet' is what the bot suggests. 'Full Bet' is if you YOLO the whole ₹2000.")
print("Values are based on 1-Standard-Deviation volatility (approx 68% probability range).")
