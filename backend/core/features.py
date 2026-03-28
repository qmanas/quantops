import pandas as pd
import numpy as np
from typing import Tuple

class FeatureGenerator:
    """
    Transforms raw OHLCV data into a 64x12 feature window.
    Window size: 64 (time steps)
    Features: 12 (ohlcv + technical indicators/returns)
    """
    
    def __init__(self, window_size: int = 64):
        self.window_size = window_size

    def generate_features(self, df: pd.DataFrame) -> np.ndarray:
        """
        Input: DataFrame with columns [timestamp, open, high, low, close, volume]
        Output: Numpy array of shape (N, 64, 12)
        """
        # 1. Calculate returns (relative change is better for models than absolute price)
        df['ret_close'] = df['close'].pct_change()
        df['ret_open'] = df['open'].pct_change()
        df['ret_high'] = df['high'].pct_change()
        df['ret_low'] = df['low'].pct_change()
        df['ret_vol'] = df['volume'].pct_change()
        
        # 2. Add some basic "context" features (e.g., range, body size)
        df['range_pct'] = (df['high'] - df['low']) / df['low']
        df['body_pct'] = (df['close'] - df['open']) / df['open']
        
        # 3. Add moving average distances
        df['ma_20_dist'] = (df['close'] - df['close'].rolling(20).mean()) / df['close'].rolling(20).mean()
        df['ma_50_dist'] = (df['close'] - df['close'].rolling(50).mean()) / df['close'].rolling(50).mean()
        
        # 4. Volatility (standardized)
        df['volatility_20'] = df['ret_close'].rolling(20).std()
        
        # 5. RSI (normalized)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        df['rsi'] = df['rsi'] / 100.0 # Normalize 0-1
        
        # 6. Volume intensity
        df['vol_ma_20_ratio'] = df['volume'] / df['volume'].rolling(20).mean()

        # Drop NaNs created by rolling windows
        df = df.dropna().reset_index(drop=True)
        
        # The 12 features we'll use:
        feature_cols = [
            'ret_close', 'ret_open', 'ret_high', 'ret_low', 'ret_vol',
            'range_pct', 'body_pct', 'ma_20_dist', 'ma_50_dist',
            'volatility_20', 'rsi', 'vol_ma_20_ratio'
        ]
        
        if len(df) < self.window_size:
            return np.array([])

        data = df[feature_cols].values
        
        # Create sliding windows
        windows = []
        for i in range(len(data) - self.window_size + 1):
            windows.append(data[i : i + self.window_size])
            
        return np.array(windows)

if __name__ == "__main__":
    # Test with dummy data
    from data import DataProvider
    provider = DataProvider()
    data = provider.fetch_bars("TSLA", interval="1h", period="1mo")
    
    gen = FeatureGenerator()
    windows = gen.generate_features(data)
    print(f"Windows shape: {windows.shape}") # Should be (N, 64, 12)
