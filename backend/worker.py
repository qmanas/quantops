import time
import os
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta, timezone
from typing import List

# Core and DB imports
from core.data import DataProvider
from core.features import FeatureGenerator
from core.model import TradingStrategyModel # Renamed from original alpha
from core.risk import RiskOrchestrator, DecisionObject # Renamed from original risk map
from db.storage import StorageManager
from execution.exchange import get_exchange

# Configuration
# Asset Universe Configuration
# In production, these should be dynamically fetched or specified via config
CRYPTO_UNIVERSE = ["BTC-USD", "ETH-USD"] # Example Assets
STOCK_UNIVERSE = ["TSLA", "AAPL"] # Example Assets
UNIVERSE = CRYPTO_UNIVERSE + STOCK_UNIVERSE

TIMEFRAMES = ["3h", "6h", "12h", "1d"]
SCAN_INTERVAL_MINUTES = 15 # How often to scan for broad opportunities
VERIFY_INTERVAL_MINUTES = 1 # Accelerated verification to clear backlog

def get_asset_class(symbol: str) -> str:
    if symbol in CRYPTO_UNIVERSE:
        return "crypto"
    return "stocks"

class AlgoWorker:
    def __init__(self, db_path: str = "data/trader.db"):
        self.storage = StorageManager(db_path=db_path)
        self.provider = DataProvider()
        self.feature_gen = FeatureGenerator()
        self.model = TradingStrategyModel()
        self.risk_map = RiskOrchestrator()
        self.exchange = get_exchange()
        self.max_active_slots = 4
        self.performance_stats = None
        
    def scan_universe(self):
        """Perform a scan across all instruments and timeframes with DAAE Slot Ranking."""
        print(f"\n[{datetime.now()}] --- STARTING DAAE SCAN CYCLE ---")
        
        # 0. Prep Performance Stats for Alpha Scoring
        self.performance_stats = self.storage.get_performance_stats(days=30)
        
        candidates = []
        
        # Phase 1: Signal Generation
        for symbol in UNIVERSE:
            for tf in TIMEFRAMES:
                try:
                    period = "1mo"
                    if tf in ["1d", "12h"]: period = "2y"
                    elif tf in ["3h", "6h"]: period = "6mo"
                    
                    df = self.provider.fetch_bars(symbol, interval=tf, period=period)
                    if len(df) < 65: continue
                        
                    current_bar = df.iloc[-1]
                    ts_iso = current_bar["timestamp"].isoformat()
                    
                    # Already decided?
                    check_query = "SELECT COUNT(*) FROM decisions WHERE symbol = ? AND ts = ? AND timeframe = ?"
                    exists = self.storage.conn.execute(check_query, [symbol, ts_iso, tf]).fetchone()[0]
                    if exists > 0: continue
                        
                    windows = self.feature_gen.generate_features(df)
                    if len(windows) == 0: continue
                    latest_window = windows[-1]
                    
                    pred = self.model.predict(latest_window)
                    risk = self.risk_map.apply(pred["raw_signal"], pred["vol_forecast"])
                    
                    if risk['direction'] != 'neutral':
                        # Alpha Scoring = abs(Signal) * WinRate (default to 0.5 if no stats)
                        stats = self.performance_stats[self.performance_stats['symbol'] == symbol]
                        win_rate = stats['win_rate'].iloc[0] if not stats.empty else 0.5
                        alpha_score = abs(pred['raw_signal']) * win_rate
                        
                        candidates.append({
                            "symbol": symbol,
                            "timeframe": tf,
                            "ts": ts_iso,
                            "pred": pred,
                            "risk": risk,
                            "alpha": alpha_score
                        })
                        
                except Exception as e:
                    print(f"Error gathering signal for {symbol} [{tf}]: {e}")

        # Phase 2: Allocation & Slot Management
        if not candidates:
            print("No new signals found.")
            return

        # Sort candidates by Alpha Score
        candidates.sort(key=lambda x: x['alpha'], reverse=True)
        print(f"Found {len(candidates)} signals. Ranking top candidates...")

        active_symbols = self.storage.get_active_slots()
        
        for cand in candidates:
            symbol = cand['symbol']
            
            # If already active, just log the decision (no double-entry)
            if symbol in active_symbols:
                self.log_and_skip(cand)
                continue
            
            # Correlation Check
            if active_symbols:
                corr_df = self.storage.get_recent_returns(active_symbols + [symbol], days=7)
                if not corr_df.empty and symbol in corr_df.columns:
                    correlations = corr_df.corr()[symbol]
                    high_corr = correlations[(correlations > 0.8) & (correlations.index != symbol)]
                    if not high_corr.empty:
                        print(f"   [!] {symbol} Disqualified: Highly correlated with {high_corr.index.tolist()}")
                        continue

            # Slot Availability
            if len(active_symbols) < self.max_active_slots:
                self.execute_entry(cand)
                active_symbols.append(symbol)
            else:
                # Slot Swap Logic (New must be 1.5x better than weakest)
                # For now, we compare against active decisions. 
                # This is complex because we don't 'Alpha Score' existing ones easily without current signals.
                # Let's simple-cap for now but prioritize the best ones from the scan.
                print(f"   [!] Slots full ({self.max_active_slots}/4). Skipping {symbol} (Alpha: {cand['alpha']:.3f})")
                self.log_and_skip(cand)

        print(f"[{datetime.now()}] --- DAAE SCAN CYCLE COMPLETE ---")

    def log_and_skip(self, cand):
        """Log decision but do not execute trade."""
        decision = DecisionObject(
            ts=cand['ts'], symbol=cand['symbol'], timeframe=cand['timeframe'],
            bar_index=0, **cand['pred'], **cand['risk'],
            model_version=self.model.version, risk_version=self.risk_map.version
        )
        self.storage.log_decision(decision)

    def execute_entry(self, cand):
        """Log decision and execute order."""
        symbol = cand['symbol']
        risk = cand['risk']
        print(f"[*] DAAE ENTRY: {symbol} [{cand['timeframe']}] -> {risk['direction'].upper()} (Alpha: {cand['alpha']:.3f})")
        
        decision = DecisionObject(
            ts=cand['ts'], symbol=symbol, timeframe=cand['timeframe'],
            bar_index=0, **cand['pred'], **cand['risk'],
            model_version=self.model.version, risk_version=self.risk_map.version
        )
        self.storage.log_decision(decision)
        
        try:
            side = 'buy' if risk['direction'] == 'long' else 'sell'
            amount = abs(risk['target_exposure']) 
            self.exchange.create_order(symbol, type='market', side=side, amount=amount)
        except Exception as ee:
            print(f"   [!] Execution Error: {ee}")

    def verify_maturities(self):
        """Check for and verify matured predictions."""
        print(f"\n[{datetime.now()}] --- STARTING VERIFICATION CYCLE ---")
        
        # Get a batch of unverified decisions, prioritizing recent ones
        query = "SELECT symbol, ts, timeframe, direction, target_exposure, model_version FROM decisions WHERE verified_at IS NULL ORDER BY ts DESC LIMIT 500"
        unverified = self.storage.conn.execute(query).df()
        
        if unverified.empty:
            print("No new predictions to verify.")
            return

        now_utc = datetime.now(timezone.utc)
        print(f"Checking {len(unverified)} unverified decisions. Current UTC: {now_utc}")
        
        # Weekend check for stocks
        is_weekend = now_utc.weekday() >= 5
        
        for _, row in unverified.iterrows():
            symbol = row['symbol']
            try:
                # 0. Check if stock on weekend
                is_stock = not symbol.endswith("-USD")
                if is_stock and is_weekend:
                    # We can't verify stocks on weekend. 
                    # Optionally mark them as "SKIPPED_WEEKEND" or just wait.
                    # Let's just continue to avoid log clutter.
                    continue

                # 1. Maturation Time Calculation
                pred_ts = pd.to_datetime(row['ts'])
                # Force aware UTC
                if pred_ts.tzinfo is None:
                    pred_ts = pred_ts.replace(tzinfo=timezone.utc)
                else:
                    pred_ts = pred_ts.tz_convert('UTC')
                
                tf = row['timeframe']
                offset_map = {
                    '5m': '5min', '15m': '15min', '30m': '30min', 
                    '1h': '1h', '3h': '3h', '6h': '6h', '12h': '12h', '1d': '1d'
                }
                maturation_time = pred_ts + pd.Timedelta(offset_map.get(tf, '1h'))

                if now_utc < maturation_time:
                    # Still waiting for this bar to close
                    continue
                
                print(f"-> Verifying {symbol} [{tf}] (Logged: {pred_ts.strftime('%H:%M')} -> Mature: {maturation_time.strftime('%H:%M')} UTC)")
                
                # 2. Fetch Price Discovery
                ticker = yf.Ticker(symbol)
                # Fetch data covering 1 day to be safe
                start_fetch = (maturation_time - timedelta(days=1)).strftime('%Y-%m-%d')
                end_fetch = (maturation_time + timedelta(days=1)).strftime('%Y-%m-%d')
                
                # Fetch 5m or 1m data
                hist = ticker.history(start=start_fetch, end=end_fetch, interval='5m')
                if hist.empty:
                    hist = ticker.history(period='2d', interval='1h') # Fallback to hourly
                
                if hist.empty:
                    print(f"   [!] No price data available for {symbol}")
                    continue
                    
                # Fix index timezone
                if hist.index.tz is None:
                    hist.index = hist.index.tz_localize('UTC')
                else:
                    hist.index = hist.index.tz_convert('UTC')
                
                # 3. PnL Calculation
                # Find entry price (at or just before pred_ts)
                entry_idx = hist.index.get_indexer([pred_ts], method='nearest')[0]
                entry_price = hist['Close'].iloc[entry_idx]
                entry_time = hist.index[entry_idx]
                
                # Find exit price (at or just after maturation_time)
                exit_idx = hist.index.get_indexer([maturation_time], method='nearest')[0]
                exit_price = hist['Close'].iloc[exit_idx]
                exit_time = hist.index[exit_idx]
                
                # Sanity check: if exit_time is before entry_time, something is wrong
                if exit_time <= entry_time:
                    print(f"   [!] Time overlap issue for {symbol}: Entry {entry_time} >= Exit {exit_time}")
                    continue

                pnl_pct = (exit_price - entry_price) / entry_price
                if row['direction'] == 'short':
                    pnl_pct = -pnl_pct

                # 4. Persistence
                self.storage.update_verification(symbol, row['ts'], pnl_pct)
                print(f"   [SUCCESS] {symbol} [{tf}]: PnL {pnl_pct*100:.3f}% (Verified)")
                
                # 5. Update Wallets in Real-Time
                self.apply_trade_to_wallets(
                    symbol=symbol,
                    pnl=pnl_pct,
                    exposure=row['target_exposure'],
                    model_version=row['model_version']
                )
                
            except Exception as e:
                print(f"   [ERROR] Verifying {symbol} [{tf}]: {e}")

    def apply_trade_to_wallets(self, symbol: str, pnl: float, exposure: float, model_version: str):
        """Apply verified trade P&L to all wallets using this model."""
        wallets = self.storage.get_wallets(model_version=model_version)
        trade_class = get_asset_class(symbol)
        
        for _, wallet in wallets.iterrows():
            # Skip if asset class doesn't match and wallet is not 'multi'
            if wallet['asset_class'] != 'multi' and wallet['asset_class'] != trade_class:
                continue
                
            # Calculate profit/loss in currency units
            position_size = wallet['balance'] * abs(exposure)
            profit = position_size * pnl
            fee = position_size * 0.002  # 0.1% each way (entry + exit)
            net_change = profit - fee
            
            # Update wallet balance
            new_balance = wallet['balance'] + net_change
            self.storage.update_wallet_balance(wallet['id'], new_balance)
            
            # Log transaction
            self.storage.log_transaction(
                wallet_id=wallet['id'],
                amount=net_change,
                tx_type='trade_pnl',
                symbol=symbol,
                metadata=f"exposure={exposure:.4f}, pnl={pnl:.4f}, fee={fee:.4f}"
            )
            
            roi = ((new_balance - wallet['initial_balance']) / wallet['initial_balance']) * 100
            print(f"   [WALLET] {wallet['name']}: {wallet['currency']} {new_balance:.2f} (ROI: {roi:+.2f}%)")

    def run(self):
        """Main loop."""
        print("Algo-Trader Background Worker Started.")
        print(f"Universe: {UNIVERSE}")
        print(f"Timeframes: {TIMEFRAMES}")
        
        last_scan = 0
        last_verify = 0
        
        while True:
            try:
                if self.storage.conn is None:
                    self.storage._init_conn()
                    
                now = time.time()

                # 1. Scan for new predictions
                if now - last_scan > SCAN_INTERVAL_MINUTES * 60:
                    self.scan_universe()
                    last_scan = now
                    
                # 2. Verify matured predictions (this updates wallets in real-time)
                if now - last_verify > VERIFY_INTERVAL_MINUTES * 60:
                    self.verify_maturities()
                    last_verify = now
                    
                self.storage.close()
                
            except Exception as e:
                print(f"Global Worker Error: {e}")
                
            # Sleep a bit
            time.sleep(30)

if __name__ == "__main__":
    worker = AlgoWorker()
    worker.run()
