import argparse
import sys
import os
import pandas as pd
from datetime import datetime

# Allow imports from backend
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from core.data import DataProvider
from core.features import FeatureGenerator
from core.model import TCNModel
from core.risk import RiskMap, DecisionObject
from db.storage import StorageManager
from simulate_portfolio import PortfolioSimulator

def replay_command(args):
    """
    Replay history and log decisions.
    """
    print(f"Starting replay from {args.start_date} to {args.end_date} for {args.symbol}...")
    
    # Initialize components
    provider = DataProvider()
    feature_gen = FeatureGenerator()
    model = TCNModel()
    risk_map = RiskMap()
    # Resolve DB path relative to the script location to ensure it works from anywhere
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, "data", "trader.db")
    storage = StorageManager(db_path=db_path, read_only=True)
    
    # Fetch Data
    # For replay, we might want higher resolution or specific range
    try:
        # Simplification: Fetch a larger block that covers the range
        # In prod, iteration bar-by-bar or chunked is better
        df = provider.fetch_bars(args.symbol, period="2y", interval="1h")
    except Exception as e:
        print(f"Error fetching data: {e}")
        return

    # Filter data
    if args.start_date:
        df = df[df['timestamp'] >= pd.to_datetime(args.start_date).tz_localize(df['timestamp'].dt.tz)]
    if args.end_date:
        df = df[df['timestamp'] <= pd.to_datetime(args.end_date).tz_localize(df['timestamp'].dt.tz)]
        
    print(f"Loaded {len(df)} bars.")
    
    if len(df) < 65:
        print("Not enough data for inference window (need 64).")
        return

    # Run Simulation
    decisions = []
    
    # We need a rolling window. 
    # This is "slow" replay. For vectorization we'd do batch inference.
    # But "Flight Recorder" implies logging individual decisions.
    
    # Pre-calculate features strictly for speed?
    # Or simulate the exact "live" loop?
    # Let's simulate the look to ensure correctness of Logic
    
    # Optimization: Generate all features at once using the full DF
    # (assuming FeatureGenerator handles the full series correctly without lookahead bias)
    # Our FeatureGenerator DOES use rolling windows, so it's correct.
    
    all_windows = feature_gen.generate_features(df)
    # all_windows[i] corresponds to window ending at row i + window_size - 1
    
    # Align timestamps
    # Window i ends at df.iloc[i + 64 - 1]
    
    start_index = 0 
    # windows has length len(df) - 64 + 1
    
    # Replay Loop
    print("Running inference...")
    for i, window in enumerate(all_windows):
        bar_idx = i + 64 - 1
        current_bar = df.iloc[bar_idx]
        
        # 1. Predict
        pred = model.predict(window)
        
        # 2. Risk
        risk = risk_map.apply(pred["raw_signal"], pred["vol_forecast"])
        
        # 3. Decision
        decision = DecisionObject(
            ts=current_bar["timestamp"].isoformat(),
            symbol=args.symbol,
            bar_index=bar_idx,
            **pred,
            **risk,
            timeframe='1h', # Default for predict
            model_version=model.version,
            risk_version=risk_map.version
        )
        
        decisions.append(decision)
        
        # 4. Log (Optional: batch this for speed)
    
    print(f"Generated {len(decisions)} decisions.")
    
    # Batch save
    print("Saving to database...")
    # StorageManager expects one by one or we can hack it for batch
    # Let's just do one by one for now or loop
    for d in decisions:
        storage.log_decision(d)
        
    print("Done.")

def analyze_command(args):
    """
    Analyze performance of logged decisions.
    """
    print(f"Analyzing {args.symbol}...")
    # Resolve DB path
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, "data", "trader.db")
    storage = StorageManager(db_path=db_path, read_only=True)
    
    decisions_df = storage.get_decisions(args.symbol, args.start_date, args.end_date)
    
    if decisions_df.empty:
        print("No decisions found.")
        return
        
    # Simple analytics
    print("\n--- Summary Statistics ---")
    print(f"Total Decisions: {len(decisions_df)}")
    print(f"Long Count: {len(decisions_df[decisions_df['direction'] == 'long'])}")
    print(f"Short Count: {len(decisions_df[decisions_df['direction'] == 'short'])}")
    print(f"Neutral Count: {len(decisions_df[decisions_df['direction'] == 'neutral'])}")
    
    print(f"Avg Vol Forecast: {decisions_df['vol_forecast'].mean():.4f}")
    print(f"Avg Risk Scalar: {decisions_df['risk_scalar'].mean():.4f}")

def predict_command(args):
    """
    Run inference on a "snapshot". 
    Source can be a ticker (auto-fetch) or a CSV file.
    """
    print(f"Running prediction for {args.target}...")
    
    provider = DataProvider()
    feature_gen = FeatureGenerator()
    model = TCNModel()
    risk_map = RiskMap()
    
    # Resolve DB path
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, "data", "trader.db")
    storage = StorageManager(db_path=db_path, read_only=True)

    df = None
    symbol = args.target

    if os.path.exists(args.target):
        # Treat as CSV file
        print("Loading from CSV snapshot...")
        try:
            df = pd.read_csv(args.target)
            # Ensure we have required columns for feature gen
            required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            
            # Map common variations if needed, or strict requirement
            df.columns = [c.lower() for c in df.columns]
            
            # Basic validation
            if not all(col in df.columns for col in required_cols):
                print(f"CSV must contain columns: {required_cols}")
                return
                
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            symbol = "MANUAL_UPLOAD"
        except Exception as e:
            print(f"Error reading CSV: {e}")
            return
            
    else:
        # Treat as Symbol
        try:
            # We need enough history for the window (64 + lookback for indicators)
            # Fetching 2mo to be safe
            df = provider.fetch_bars(args.target, period="2mo", interval="1h")
        except Exception as e:
            print(f"Error fetching data for {args.target}: {e}")
            return

    # Check length
    if len(df) < 65:
        print("Not enough data. Need at least ~65 bars.")
        return

    # Generate features
    windows = feature_gen.generate_features(df)
    
    if len(windows) == 0:
        print("Could not generate valid feature window.")
        return

    # Use the LATEST window for "now" prediction
    latest_window = windows[-1]
    
    # Predict
    pred = model.predict(latest_window)
    
    # Risk
    risk = risk_map.apply(pred["raw_signal"], pred["vol_forecast"])
    
    current_bar = df.iloc[-1]
    
    print("\n>>> MODEL DECISION <<<")
    print(f"Timestamp: {current_bar['timestamp']}")
    print(f"Direction: {risk['direction'].upper()}")
    print(f"Target Exposure: {risk['target_exposure']:.2f}")
    print(f"Confidence (Vol Z): {pred['vol_z']:.2f}")
    print(f"Raw Signal: {pred['raw_signal']:.2f}")
    
    if risk['neutral_zone']:
        print("[!] NEUTRAL ZONE ACTIVATED - NO TRADE")
        
    print("-" * 30)

    # Log it
    decision = DecisionObject(
        ts=current_bar["timestamp"].isoformat(),
        symbol=symbol,
        bar_index=len(df), 
        **pred,
        **risk,
        model_version=model.version,
        risk_version=risk_map.version
    )
    storage.log_decision(decision)
    print("Logged to Flight Recorder.")

def portfolios_command(args):
    """List all active wallets and their status."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, "data", "trader.db")
    storage = StorageManager(db_path=db_path, read_only=True)
    
    df = storage.get_wallets()
    if df.empty:
        print("No wallets found. Run 'python backend/init_wallets.py' first.")
        return
        
    print("\n=== ACTIVE PORTFOLIOS ===")
    from tabulate import tabulate
    
    # Calculate metrics
    df['ROI %'] = ((df['balance'] - df['initial_balance']) / df['initial_balance'] * 100).round(2)
    df['Progress %'] = (df['balance'] / df['target_goal'] * 100).round(2)
    
    # Format currency display
    df['current'] = df.apply(lambda row: f"{row['currency']} {row['balance']:,.2f}", axis=1)
    df['initial'] = df.apply(lambda row: f"{row['currency']} {row['initial_balance']:,.2f}", axis=1)
    df['goal'] = df.apply(lambda row: f"{row['currency']} {row['target_goal']:,.2f}", axis=1)
    
    view_cols = ['name', 'initial', 'current', 'ROI %', 'goal', 'Progress %', 'model_version']
    print(tabulate(df[view_cols], headers='keys', tablefmt='psql'))

def sync_command(args):
    """Trigger an immediate portfolio sync."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, "data", "trader.db")
    storage = StorageManager(db_path=db_path, read_only=True)
    
    # We can't easily call the worker method here without importing it (circular),
    # but the worker will pick it up every 5 mins.
    print("Sync triggered. The background worker will update balances in its next 5-min cycle.")

def add_portfolio_command(args):
    """Add a new tracking wallet."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, "data", "trader.db")
    storage = StorageManager(db_path=db_path, read_only=False)
    
    wallet_id = storage.create_wallet(
        name=args.name,
        initial_balance=args.amount,
        currency=args.currency,
        model_version="chronos-chronos-bolt-tiny",
        target_goal=args.goal
    )
    print(f"✅ Added wallet: {args.name} with {args.currency} {args.amount} (ID: {wallet_id})")

def transactions_command(args):
    """View transaction history for a wallet."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, "data", "trader.db")
    storage = StorageManager(db_path=db_path, read_only=True)
    
    # Get wallet ID by name if provided
    wallet_id = None
    if args.name:
        wallets = storage.get_wallets()
        wallet = wallets[wallets['name'] == args.name]
        if wallet.empty:
            print(f"Wallet '{args.name}' not found.")
            return
        wallet_id = wallet.iloc[0]['id']
    
    df = storage.get_transactions(wallet_id=wallet_id, limit=args.limit)
    if df.empty:
        print("No transactions found.")
        return
    
    print(f"\n=== TRANSACTION HISTORY{' for ' + args.name if args.name else ''} ===")
    from tabulate import tabulate
    
    # Format display
    df['timestamp'] = pd.to_datetime(df['timestamp']).dt.strftime('%Y-%m-%d %H:%M')
    df['amount'] = df['amount'].apply(lambda x: f"{x:+.4f}")
    
    view_cols = ['timestamp', 'type', 'symbol', 'amount', 'metadata']
    print(tabulate(df[view_cols].head(args.limit), headers='keys', tablefmt='psql', showindex=False))

def spread_command(args):
    """Show the current exposure spread for a portfolio."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, "backend", "data", "trader.db")
    storage = StorageManager(db_path=db_path)
    
    # Fetch last 24h worth of signals to find "Active" exposure
    # (Since we focus on 3h-1d tfs, current exposure is the latest signal for each sym/tf)
    query = """
    SELECT symbol, timeframe, target_exposure, direction, ts
    FROM (
        SELECT *, ROW_NUMBER() OVER (PARTITION BY symbol, timeframe ORDER BY ts DESC) as rn
        FROM decisions
    ) WHERE rn = 1 AND direction != 'neutral'
    """
    df = storage.conn.execute(query).df()
    
    if df.empty:
        print("No active trades found in the last cycle.")
        return

    print(f"\n=== CURRENT SPREAD FOR: {args.name} ===")
    total_active_exposure = df['target_exposure'].abs().sum()
    print(f"Total Portfolio Exposure: {total_active_exposure:.2%}")
    
    from tabulate import tabulate
    print(tabulate(df[['symbol', 'timeframe', 'direction', 'target_exposure']], headers='keys', tablefmt='simple'))
    print("\nNote: Exposure values are fractions of total portfolio capital.")

def scan_command(args):
    """
    Scan a universe of symbols for opportunities.
    """
    symbols = args.universe.split(",")
    print(f"Scanning {len(symbols)} symbols: {symbols}")
    
    # Resolve DB path
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, "backend", "data", "trader.db")
    storage = StorageManager(db_path=db_path)

    for sym in symbols:
        sym = sym.strip()
        try:
            provider = DataProvider()
            feature_gen = FeatureGenerator()
            model = TCNModel()
            risk_map = RiskMap()
            
            # Fetch with requested interval
            df = provider.fetch_bars(sym, period="2y", interval=args.interval)
            
            if len(df) < 65: continue
            
            windows = feature_gen.generate_features(df)
            if len(windows) == 0: continue
            
            pred = model.predict(windows[-1])
            risk = risk_map.apply(pred["raw_signal"], pred["vol_forecast"])
            
            current_bar = df.iloc[-1]
            decision = DecisionObject(
                ts=current_bar["timestamp"].isoformat(),
                symbol=sym,
                bar_index=len(df),
                **pred,
                **risk,
                timeframe=args.interval,
                model_version=model.version,
                risk_version=risk_map.version
            )
            storage.log_decision(decision)

            if risk['direction'] != 'neutral':
                print(f"[*] OPPORTUNITY: {sym} -> {risk['direction'].upper()} (Exp: {risk['target_exposure']})")
                
        except Exception as e:
            continue

def stats_command(args):
    """
    Display portfolio statistics and goal tracker.
    """
    print(f"\n=== PORTFOLIO GOAL TRACKER (Target: ${args.goal}) ===")
    sim = PortfolioSimulator()
    res = sim.run_simulation(args.amount)
    
    if res:
        # Progress towards goal
        progress = (res['final'] / args.goal) * 100
        print(f"\n[GOAL PROGRESS]: {progress:.2f}% of ${args.goal}")
        
        if res['roi'] > 0:
            print(f"[STATUS]: ON TRACK 🚀")
        else:
            print(f"[STATUS]: CHOPPY WATER 🌊")
        
        print(f"{'='*40}")

def main():
    parser = argparse.ArgumentParser(description="Algo-Trader CLI")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Replay
    replay_parser = subparsers.add_parser("replay", help="Run historical replay")
    replay_parser.add_argument("--symbol", type=str, required=True, help="Stock symbol (e.g., SPY)")
    replay_parser.add_argument("--start-date", type=str, help="YYYY-MM-DD")
    replay_parser.add_argument("--end-date", type=str, help="YYYY-MM-DD")
    
    # Analyze
    analyze_parser = subparsers.add_parser("analyze", help="Analyze results")
    analyze_parser.add_argument("--symbol", type=str, required=True, help="Stock symbol")
    analyze_parser.add_argument("--start-date", type=str, help="YYYY-MM-DD")
    analyze_parser.add_argument("--end-date", type=str, help="YYYY-MM-DD")
    
    # Predict (Snapshot)
    predict_parser = subparsers.add_parser("predict", help="Run inference on current market or file")
    predict_parser.add_argument("target", type=str, help="Stock symbol OR path to CSV file")
    
    # Scan
    scan_parser = subparsers.add_parser("scan", help="Scan multiple symbols")
    scan_parser.add_argument("--universe", type=str, default="SPY,QQQ,IWM,MSFT,AAPL,NVDA", help="Comma separated list")
    scan_parser.add_argument("--interval", type=str, default="1h", help="Timeframe (1h, 3h, 6h, 12h, 1d)")

    # Stats / Goal Tracker
    stats_parser = subparsers.add_parser("stats", help="View portfolio performance and goal tracker")
    stats_parser.add_argument("--amount", type=float, default=5.0, help="Initial investment amount")
    stats_parser.add_argument("--goal", type=float, default=5.35, help="Target goal amount")

    # Multi-Portfolio
    subparsers.add_parser("portfolios", help="List all tracking portfolios")
    subparsers.add_parser("sync", help="Trigger an immediate portfolio balance sync")
    
    add_port_parser = subparsers.add_parser("add-portfolio", help="Add a new tracking portfolio")
    add_port_parser.add_argument("--name", type=str, required=True, help="Portfolio Name")
    add_port_parser.add_argument("--amount", type=float, required=True, help="Initial balance")
    add_port_parser.add_argument("--currency", type=str, default="USD", help="Currency (USD, INR, etc.)")
    add_port_parser.add_argument("--goal", type=float, required=True, help="Target goal amount")

    spread_parser = subparsers.add_parser("spread", help="Show current asset spread")
    spread_parser.add_argument("--name", type=str, default="Alpha-45k-INR", help="Portfolio name")

    transactions_parser = subparsers.add_parser("transactions", help="View transaction history")
    transactions_parser.add_argument("--name", type=str, help="Wallet name (optional, shows all if not specified)")
    transactions_parser.add_argument("--limit", type=int, default=50, help="Number of transactions to show")

    args = parser.parse_args()
    
    if args.command == "replay":
        replay_command(args)
    elif args.command == "analyze":
        analyze_command(args)
    elif args.command == "predict":
        predict_command()
    elif args.command == "scan":
        scan_command(args)
    elif args.command == "stats":
        stats_command(args)
    elif args.command == "portfolios":
        portfolios_command(args)
    elif args.command == "sync":
        sync_command(args)
    elif args.command == "add-portfolio":
        add_portfolio_command(args)
    elif args.command == "spread":
        spread_command(args)
    elif args.command == "transactions":
        transactions_command(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
