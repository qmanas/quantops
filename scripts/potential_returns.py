import sys
import duckdb
import argparse
from datetime import datetime

# Current Constants
USD_TO_INR = 83.0 # Simplified fixed rate for projection

def calculate_returns(amount, currency, start_date='2026-02-19'):
    db_path = 'data/trader.db'
    try:
        conn = duckdb.connect(db_path, read_only=True)
        # We use the 'Crypto-Paper-Test' wallet as the benchmark for ROI
        res = conn.execute("SELECT initial_balance, balance FROM wallets WHERE name = 'Crypto-Paper-Test'").fetchone()
        if not res:
            return "No performance data found."
        
        initial, current = res
        roi_ratio = current / initial
        
        projected = amount * roi_ratio
        change = projected - amount
        roi_pct = (roi_ratio - 1) * 100
        
        return {
            "amount": amount,
            "currency": currency.upper(),
            "projected": round(projected, 2),
            "change": round(change, 2),
            "roi_pct": round(roi_pct, 2)
        }
    except Exception as e:
        return f"Error: {e}"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calculate potential returns for a given investment.")
    parser.add_argument("--amount", type=float, required=True, help="Amount invested.")
    parser.add_argument("--currency", type=str, default="USD", help="Currency (USD/INR/etc).")
    
    args = parser.parse_args()
    
    res = calculate_returns(args.amount, args.currency)
    if isinstance(res, dict):
        print(f"\n--- POTENTIAL RETURNS (Native Service Era) ---")
        print(f"Initial Investment: {res['amount']} {res['currency']}")
        print(f"Projected Current Value: {res['projected']} {res['currency']}")
        print(f"Net Change: {res['change']} {res['currency']} ({res['roi_pct']}%)")
    else:
        print(res)
