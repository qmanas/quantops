#!/usr/bin/env python3
"""
Initialize wallets and migrate from portfolios table.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db.storage import StorageManager
from datetime import datetime

def main():
    # Use project root data/trader.db
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, "data", "trader.db")
    
    storage = StorageManager(db_path=db_path)
    
    # Check if we need to migrate from portfolios
    try:
        portfolios = storage.conn.execute("SELECT * FROM portfolios").df()
        if not portfolios.empty:
            print(f"Found {len(portfolios)} existing portfolios. Migrating to wallets...")
            for _, p in portfolios.iterrows():
                wallet_id = storage.create_wallet(
                    name=p['name'],
                    initial_balance=p['initial_balance'],
                    currency=p['currency'],
                    model_version=p.get('model_version'),
                    target_goal=p.get('target_goal')
                )
                # Update balance to current value (preserving progress)
                storage.update_wallet_balance(wallet_id, p['balance'])
                print(f"  ✓ Migrated '{p['name']}': {p['currency']} {p['balance']:.2f}")
            
            # Drop old portfolios table
            storage.conn.execute("DROP TABLE portfolios")
            print("\n✅ Migration complete. Old portfolios table removed.")
            return
    except Exception as e:
        print(f"Migration note/error: {e}")
        pass  # portfolios table doesn't exist or other non-fatal error
    
    # Create default wallets if none exist
    wallets = storage.get_wallets()
    if wallets.empty:
        print("No wallets found. Creating Phase 1 crypto-focused wallets...")
        
        default_wallets = [
            {
                "name": "Crypto-Binance-Main",
                "initial_balance": 1.0,
                "currency": "BTC",
                "asset_class": "crypto",
                "provider": "binance",
                "model_version": "chronos-chronos-bolt-tiny",
                "target_goal": 2.0
            },
            {
                "name": "Crypto-Paper-Test",
                "initial_balance": 1000.0,
                "currency": "USD",
                "asset_class": "crypto",
                "provider": "paper",
                "model_version": "chronos-chronos-bolt-tiny",
                "target_goal": 2000.0
            },
            {
                "name": "Tech-Paper-Stocks",
                "initial_balance": 5000.0,
                "currency": "USD",
                "asset_class": "stocks",
                "provider": "paper",
                "model_version": "chronos-chronos-bolt-tiny",
                "target_goal": 10000.0
            }
        ]
        
        for w in default_wallets:
            wallet_id = storage.create_wallet(**w)
            print(f"  ✓ Created '{w['name']}': {w['currency']} {w['initial_balance']:.2f} ({w['provider']})")
        
        print(f"\n✅ Initialized {len(default_wallets)} wallets in {db_path}")
    else:
        print(f"Found {len(wallets)} existing wallets. No initialization needed.")

if __name__ == "__main__":
    main()
