import pandas as pd
from config import kite
import datetime

def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calculate_macd_histogram(close_prices):
    macd_line = ema(close_prices, 12) - ema(close_prices, 26)
    signal_line = ema(macd_line, 9)
    hist = macd_line - signal_line
    return macd_line.iloc[-1], signal_line.iloc[-1], hist.iloc[-1], hist.iloc[-2]

def fetch_histogram(symbol):
    now = datetime.datetime.now()
    from_dt = now - datetime.timedelta(days=5)
    token = kite.ltp(f"NFO:{symbol}")[f"NFO:{symbol}"]["instrument_token"]
    candles = kite.historical_data(token, from_dt, now, "30minute")
    df = pd.DataFrame(candles)
    df.set_index(pd.to_datetime(df['date']), inplace=True)
    return calculate_macd_histogram(df['close'])
