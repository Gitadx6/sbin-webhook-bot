import pandas as pd

def calculate_rsi(prices: pd.Series, period: int) -> pd.Series:
    """
    Calculates the Relative Strength Index (RSI) using a Pandas Series of prices.
    :param prices: A Pandas Series containing the 'close' prices.
    :param period: The lookback period for the RSI calculation.
    :return: A Pandas Series with the calculated RSI values.
    """
    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period, min_periods=1).mean()
    avg_loss = loss.rolling(window=period, min_periods=1).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_atr(data: pd.DataFrame, period: int) -> pd.Series:
    """
    Calculates the Average True Range (ATR) using a Pandas DataFrame.
    :param data: A Pandas DataFrame with 'high', 'low', and 'close' columns.
    :param period: The lookback period for the ATR calculation.
    :return: A Pandas Series with the calculated ATR values.
    """
    high_low = data['high'] - data['low']
    high_close = (data['high'] - data['close'].shift()).abs()
    low_close = (data['low'] - data['close'].shift()).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = true_range.rolling(window=period, min_periods=1).mean()
    return atr
