import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from core.data import DataProvider
from execution.exchange import get_exchange

def test_ccxt_data():
    print("--- Testing CCXT Data Fetching ---")
    provider = DataProvider()
    try:
        # Test BTC-USD (should use CCXT)
        df = provider.fetch_bars("BTC-USD", interval="1h", period="1d")
        print(f"BTC-USD Data (CCXT):\n{df.head(2)}")
        print(f"Columns: {df.columns.tolist()}")
        if not df.empty and 'close' in df.columns:
            print("[SUCCESS] CCXT data fetched correctly.")
        else:
            print("[FAIL] CCXT data empty or missing columns.")
    except Exception as e:
        print(f"[ERROR] CCXT data fetch failed: {e}")

def test_paper_execution():
    print("\n--- Testing Paper Trading Execution ---")
    exchange = get_exchange()
    try:
        order = exchange.create_order("BTC-USD", type="market", side="buy", amount=0.01)
        print(f"Order Result: {order}")
        if order['status'] == 'closed':
            print("[SUCCESS] Paper order executed correctly.")
        else:
            print("[FAIL] Paper order status unexpected.")
    except Exception as e:
        print(f"[ERROR] Paper order execution failed: {e}")

if __name__ == "__main__":
    test_ccxt_data()
    test_paper_execution()
