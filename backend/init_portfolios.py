from db.storage import StorageManager
import os
from datetime import datetime

def init_user_portfolios():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, "data", "trader.db")
    storage = StorageManager(db_path=db_path)
    
    # Drop and recreate to ensure schema is fresh
    storage.conn.execute("DROP TABLE IF EXISTS portfolios")
    storage._init_db()
    
    # Use Jan 31st as the start date for catch-up
    # Use Jan 30th as the start date for catch-up to capture earliest verified trades
    
    portfolios = [
        {
            "name": "Starter-5-USD", 
            "balance": 5.0, 
            "initial_balance": 5.0,
            "currency": "USD", 
            "model_version": "chronos-chronos-bolt-tiny", 
            "target_goal": 10.0,
            "last_synced_at": "2026-01-30 00:00:00"
        },
        {
            "name": "Alpha-45k-INR", 
            "balance": 45000.0, 
            "initial_balance": 45000.0,
            "currency": "INR", 
            "model_version": "chronos-chronos-bolt-tiny", 
            "target_goal": 50000.0,
            "last_synced_at": "2026-01-30 00:00:00"
        }
    ]
    
    storage.initialize_portfolios(portfolios)
    print(f"Reset and Initialized {len(portfolios)} portfolios in {db_path}")

if __name__ == "__main__":
    init_user_portfolios()
