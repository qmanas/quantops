import duckdb
import pandas as pd
import numpy as np
import os
from datetime import datetime

class PortfolioSimulator:
    """
    Simulates portfolio performance based on logged decisions.
    Supports multi-scale scenarios ($5, $10, $50).
    """
    
    def __init__(self, db_path: str = "data/trader.db"):
        self.db_path = db_path
        if not os.path.exists(self.db_path):
            # Try finding it relative to project root
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.db_path = os.path.join(base_dir, "data", "trader.db")

    def run_simulation(self, initial_balance: float, fee_pct: float = 0.001, model_version: str = "chronos-chronos-bolt-tiny"):
        """
        Runs a simulation for a specific initial balance and model version.
        Includes a basic fee model.
        """
        print(f"\n--- SIMULATING ${initial_balance} PORTFOLIO (Model: {model_version}) ---")
        
        conn = duckdb.connect(self.db_path, read_only=True)
        # Fetch verified decisions
        query = """
            SELECT ts, symbol, timeframe, direction, AVG(target_exposure) as target_exposure, MAX(realized_pnl) as realized_pnl 
            FROM decisions 
            WHERE realized_pnl IS NOT NULL 
            AND model_version = ?
            GROUP BY ts, symbol, timeframe, direction
            ORDER BY ts ASC
        """
        df = conn.execute(query, [model_version]).df()
        conn.close()
        
        if df.empty:
            print("No verified decisions found in database. Run the worker first!")
            return
            
        current_balance = initial_balance
        trades_count = 0
        winning_trades = 0
        total_pnl_usd = 0
        
        # We'll simulate trade by trade
        # Note: This is an approximation as it assumes we can enter multiple positions
        # In reality, we'd manage bankroll across instruments.
        
        for _, row in df.iterrows():
            if row['direction'] == 'neutral':
                continue
                
            exposure = abs(row['target_exposure'])
            # Position Size in USD = Balance * Exposure
            # (Cap exposure at 1.0 for sanity)
            pos_size = current_balance * min(exposure, 1.0)
            
            # Entry Fee
            current_balance -= pos_size * fee_pct
            
            # PnL (realized_pnl is a fractional return, e.g. 0.01 for 1%)
            pnl_usd = pos_size * row['realized_pnl']
            current_balance += pnl_usd
            
            # Exit Fee
            current_balance -= pos_size * fee_pct
            
            trades_count += 1
            if row['realized_pnl'] > 0:
                winning_trades += 1
            total_pnl_usd += pnl_usd
            
        win_rate = (winning_trades / trades_count) * 100 if trades_count > 0 else 0
        roi = ((current_balance - initial_balance) / initial_balance) * 100
        
        print(f"Total Trades: {trades_count}")
        print(f"Win Rate: {win_rate:.2f}%")
        print(f"Final Balance: ${current_balance:.2f}")
        print(f"Total Profit/Loss: ${current_balance - initial_balance:.2f}")
        print(f"ROI: {roi:.2f}%")
        
        return {
            "initial": initial_balance,
            "final": current_balance,
            "trades": trades_count,
            "win_rate": win_rate,
            "roi": roi
        }

if __name__ == "__main__":
    sim = PortfolioSimulator()
    scenarios = [5, 10, 50]
    results = []
    
    for amount in scenarios:
        res = sim.run_simulation(amount)
        if res:
            results.append(res)
            
    if results:
        print("\n=== SUMMARY TABLE ===")
        print(f"{'Initial':<10} | {'Final':<10} | {'ROI %':<10} | {'Trades':<10}")
        print("-" * 50)
        for r in results:
            print(f"${r['initial']:<9} | ${r['final']:<9.2f} | {r['roi']:<9.2f}% | {r['trades']:<10}")
