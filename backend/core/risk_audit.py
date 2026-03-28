import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime, timedelta

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.storage import StorageManager

class RiskAuditor:
    """
    Performs forensic analysis on past trades to suggest risk parameter optimizations.
    This fulfills the "Self-Learning" requirement by auditing the 'Flight Recorder' data.
    """
    def __init__(self, db_path: str = "data/trader.db"):
        self.storage = StorageManager(db_path=db_path, read_only=True)

    def generate_report(self, days: int = 30):
        """Analyze past trades and generate a risk adjustment report."""
        query = """
            SELECT symbol, timeframe, direction, realized_pnl, target_exposure 
            FROM decisions 
            WHERE realized_pnl IS NOT NULL 
            AND verified_at > ?
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        df = self.storage.conn.execute(query, [cutoff]).df()

        if df.empty:
            return "No verified trades found in the last 30 days."

        report = []
        report.append(f"# Risk Forensic Audit Report ({datetime.now().strftime('%Y-%m-%d')})")
        report.append(f"Analyzing {len(df)} verified trades from the last {days} days.\n")

        # 1. Performance by Symbol
        symbol_perf = df.groupby('symbol')['realized_pnl'].agg(['count', 'mean', 'sum']).reset_index()
        
        # Win rate calculation with proper alignment
        wins = df[df['realized_pnl'] > 0].groupby('symbol').size()
        total = df.groupby('symbol').size()
        win_rate_series = (wins / total).fillna(0)
        
        # Merge win rate into symbol_perf
        symbol_perf = symbol_perf.merge(win_rate_series.rename('win_rate'), on='symbol', how='left')
        symbol_perf['win_rate'] = symbol_perf['win_rate'].fillna(0)

        report.append("## 📈 Performance by Asset")
        
        # Suggestions Logic
        suggestions = []
        for _, row in symbol_perf.iterrows():
            sym = row['symbol']
            wr = row['win_rate']
            avg_pnl = row['mean']
            
            status = "✅ Healthy"
            if wr < 0.45:
                status = "⚠️ Underperforming"
                suggestions.append(f"- **{sym}**: Win rate is {wr*100:.1f}%. Consider reducing exposure multiplier to 0.5x.")
            elif wr > 0.60:
                status = "🚀 Outperforming"
                suggestions.append(f"- **{sym}**: Strong win rate ({wr*100:.1f}%). Strategy is highly effective here.")
            
            report.append(f"- **{sym}**: {row['count']} trades, Avg PnL: {avg_pnl*100:+.3f}%, Win Rate: {wr*100:.1f}% [{status}]")

        if suggestions:
            report.append("\n## 🛠️ Suggested Risk Adjustments")
            report.extend(suggestions)
        else:
            report.append("\n## 🛠️ Suggested Risk Adjustments\n- No adjustments needed. Strategy performing within expected bounds.")

        return "\n".join(report)

if __name__ == "__main__":
    # Get project root
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    db_path = os.path.join(base_dir, "data", "trader.db")
    
    auditor = RiskAuditor(db_path=db_path)
    print(auditor.generate_report())
