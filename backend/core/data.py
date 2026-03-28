import yfinance as yf
import pandas as pd
from typing import Optional
from datetime import datetime, timedelta

class DataProvider:
    """Provides market data using yfinance."""
    
    def __init__(self):
        # Import here to avoid circular dependency if any, 
        # though we should probably inject this.
        from execution.exchange import CCXTAdapter
        self.ccxt_client = CCXTAdapter()

    def fetch_bars(self, symbol: str, interval: str = "1h", period: str = "1mo") -> pd.DataFrame:
        """
        Fetch historical bars for a given symbol.
        Routes to CCXT for crypto (-USD) and yfinance for others.
        """
        fetch_interval = interval
        if interval in ["3h", "6h", "12h"]:
            fetch_interval = "1h"

        if symbol.endswith("-USD"):
            print(f"Fetching {symbol} via CCXT ({fetch_interval} resampled to {interval}) for {period}...")
            # CCXT expects standard timeframes (1h, 1d, etc.)
            df = self.ccxt_client.fetch_ohlcv(symbol, timeframe=fetch_interval, period=period)
        else:
            print(f"Fetching {symbol} via yfinance ({fetch_interval} resampled to {interval}) for {period}...")
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=fetch_interval)
            
            if df.empty:
                raise ValueError(f"No data found for symbol {symbol}")
                
            # Standardize column names
            df = df.reset_index()
            df.columns = [c.lower() for c in df.columns]
        
        # Ensure timestamp column is named 'timestamp'
        if 'datetime' in df.columns:
            df = df.rename(columns={'datetime': 'timestamp'})
        elif 'date' in df.columns:
            df = df.rename(columns={'date': 'timestamp'})
        elif 'Date' in df.columns:
             df = df.rename(columns={'Date': 'timestamp'})

        # Custom Resampling for 3h, 6h, 12h
        if interval in ["3h", "6h", "12h"]:
            df = self._resample(df, interval)

        return df

    def _resample(self, df: pd.DataFrame, interval: str) -> pd.DataFrame:
        """
        Resample 1h data into higher timeframes.
        """
        # Set index to timestamp for resampling
        df = df.set_index('timestamp')
        
        # Aggregation logic
        agg_dict = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }
        
        # Resample
        # interval string '3h' works directly in pandas
        resampled = df.resample(interval).agg(agg_dict)
        
        # Drop incomplete bins (if any, usually last one)
        resampled = resampled.dropna()
        
        return resampled.reset_index()

if __name__ == "__main__":
    # Quick test
    provider = DataProvider()
    data = provider.fetch_bars("AAPL", interval="1h", period="5d")
    print(data.head())
    print(f"Columns: {data.columns.tolist()}")
