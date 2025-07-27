import datetime
import pandas as pd
from kiteconnect import KiteConnect
from config import kite, resolve_token

# ========== Get Previous Expiry Symbol ==========

def get_previous_expiry_symbol(current_symbol):
    import re

    match = re.match(r"SBIN(\d{2})([A-Z]{3})FUT", current_symbol)
    if not match:
        return None

    year = int(match.group(1))
    month_str = match.group(2).upper()

    months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
              "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    month_index = months.index(month_str)

    prev_index = (month_index - 1) % 12
    prev_month_str = months[prev_index]

    if month_index == 0:
        year -= 1

    return f"SBIN{year:02d}{prev_month_str}FUT"

# ========== Get Candles ==========

def get_candles(symbol, lookback=30):
    try:
        to_date = datetime.datetime.now()
        from_date = to_date - datetime.timedelta(minutes=lookback * 30)
        instrument_token = resolve_token(symbol)

        candles = kite.historical_data(
            instrument_token=instrument_token,
            from_date=from_date,
            to_date=to_date,
            interval="30minute"
        )
        return candles
    except Exception as e:
        print(f"❌ Error fetching candles for {symbol}: {e}")
        return []

# ========== Fetch Histogram ==========

def fetch_histogram(symbol, lookback=30):
    fallback_symbol = get_previous_expiry_symbol(symbol)
    
    candles = get_candles(symbol, lookback)
    used_symbol = symbol

    if len(candles) < 26:
        print(f"⚠️ Not enough candles for {symbol}, trying fallback {fallback_symbol}")
        candles = get_candles(fallback_symbol, lookback)
        used_symbol = fallback_symbol

    if len(candles) < 26:
        print("❌ Not enough candles even in fallback.")
        return None, "not_enough_data"

    try:
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
        print(f"❌ Error in MACD histogram calculation: {e}")
        return None, "error"
