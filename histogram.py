import datetime
import pandas as pd
from kiteconnect import KiteConnect
from config import kite, resolve_token
from symbol_resolver import resolve_sbin_future

# ========== Get Candles ==========

def get_candles(symbol, days_back=7):
    try:
        to_date = datetime.datetime.now()
        from_date = to_date - datetime.timedelta(days=days_back)
        instrument_token = resolve_token(symbol)

        candles = kite.historical_data(
            instrument_token=instrument_token,
            from_date=from_date,
            to_date=to_date,
            interval="30minute"
        )
        print(f"📊 Got {len(candles)} candles for {symbol}")
        return candles
    except Exception as e:
        print(f"❌ Error fetching candles for {symbol}: {e}")
        return []

# ========== Fetch Histogram ==========

def fetch_histogram(symbol=None, days_back=7):
    try:
        if symbol is None:
            symbol = resolve_sbin_future()

        candles = get_candles(symbol, days_back)
        used_symbol = symbol

        if len(candles) < 26:
            raise Exception("Not enough candles")

        df = pd.DataFrame(candles)
        df.columns = ["date", "open", "high", "low", "close", "volume"]

        # MACD Calculation
        df['ema12'] = df['close'].ewm(span=12, adjust=False).mean()
        df['ema26'] = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = df['ema12'] - df['ema26']
        df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['hist'] = df['macd'] - df['signal']

        latest_hist = df['hist'].iloc[-1]
        prev_hist = df['hist'].iloc[-2]

        cross_to_green = latest_hist > 0 and prev_hist <= 0
        cross_to_red = latest_hist < 0 and prev_hist >= 0

        return {
            "hist": latest_hist,
            "cross_to_green": cross_to_green,
            "cross_to_red": cross_to_red,
            "used_symbol": used_symbol
        }, "ok"

    except Exception as e:
        print(f"❌ Error in MACD histogram calculation for {symbol}: {e}")
        return None, "error"
