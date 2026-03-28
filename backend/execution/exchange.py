import ccxt
import pandas as pd
from datetime import datetime
import os
from typing import List, Optional, Dict

class ExchangeInterface:
    """Base interface for exchange operations."""
    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
        raise NotImplementedError

    def create_order(self, symbol: str, type: str, side: str, amount: float, price: Optional[float] = None) -> Dict:
        raise NotImplementedError

class CCXTAdapter(ExchangeInterface):
    """Real-time data fetching and execution using CCXT."""
    def __init__(self, exchange_id: str = 'binance', api_key: str = None, secret: str = None):
        exchange_class = getattr(ccxt, exchange_id)
        config = {
            'enableRateLimit': True,
        }
        if api_key and secret:
            config['apiKey'] = api_key
            config['secret'] = secret
            
        self.client = exchange_class(config)

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100, period: Optional[str] = None) -> pd.DataFrame:
        # Map yfinance-style symbols to CCXT if needed (e.g., BTC-USD -> BTC/USDT)
        ccxt_symbol = symbol.replace("-USD", "/USDT")
        
        if period:
            if 'mo' in period: limit = 1000
            elif 'y' in period: limit = 2000
            elif 'd' in period: 
                days = int(period.replace('d', ''))
                if timeframe == '1h': limit = days * 24
                elif timeframe == '1d': limit = days
                else: limit = 500
        
        ohlcv = self.client.fetch_ohlcv(ccxt_symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df

    def create_order(self, symbol: str, type: str, side: str, amount: float, price: Optional[float] = None) -> Dict:
        ccxt_symbol = symbol.replace("-USD", "/USDT")
        # Real execution logic would go here
        return self.client.create_order(ccxt_symbol, type, side, amount, price)

class PaperExchange(ExchangeInterface):
    """Simulated execution engine."""
    def __init__(self, data_provider: ExchangeInterface):
        self.data_provider = data_provider

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
        return self.data_provider.fetch_ohlcv(symbol, timeframe, limit)

    def create_order(self, symbol: str, type: str, side: str, amount: float, price: Optional[float] = None) -> Dict:
        if price is None:
            df = self.fetch_ohlcv(symbol, timeframe='1m', limit=1)
            price = df.iloc[-1]['close']
        
        order = {
            'id': f"paper_{datetime.now().timestamp()}",
            'symbol': symbol,
            'side': side,
            'amount': amount,
            'price': price,
            'status': 'closed',
            'timestamp': datetime.now().isoformat()
        }
        print(f"[PAPER] Order Executed: {side.upper()} {amount} {symbol} @ {price}")
        return order

class ProviderFactory:
    """Manages creation of different exchange/broker providers."""
    @staticmethod
    def get_provider(provider_name: str) -> ExchangeInterface:
        if provider_name == 'binance':
            api_key = os.getenv("BINANCE_API_KEY")
            secret = os.getenv("BINANCE_SECRET")
            return CCXTAdapter('binance', api_key, secret)
        elif provider_name == 'paper':
            # Default to binance for paper data
            data_client = CCXTAdapter('binance')
            return PaperExchange(data_provider=data_client)
        else:
            # Fallback for stocks or other providers
            return CCXTAdapter('binance') # Placeholder

def get_exchange(provider_name: str = 'paper'):
    """Helper to get the appropriate exchange client."""
    return ProviderFactory.get_provider(provider_name)
