import datetime
import pandas as pd
from config import kite, current_position, monitor_frequency, TIME_INTERVAL, config_logger
from bot_utils import get_instrument_token

# --- Global Variables for Indicator State ---
# Using a dictionary to hold the last calculated values to avoid recalculation
last_indicator_values = {
    "RSI_VALUE": None,
    "EMA_SHORT": None,
    "EMA_LONG": None
}

# --- Indicator Calculation Functions ---
def calculate_rsi(data, window=14):
    """
    Calculates the Relative Strength Index (RSI).

    Args:
        data (pd.DataFrame): DataFrame with 'close' prices.
        window (int): The number of periods to use for the RSI calculation.

    Returns:
        float: The latest RSI value.
    """
    delta = data['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.ewm(com=window - 1, min_periods=window).mean()
    avg_loss = loss.ewm(com=window - 1, min_periods=window).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

def calculate_ema(data, window=12):
    """
    Calculates the Exponential Moving Average (EMA).

    Args:
        data (pd.DataFrame): DataFrame with 'close' prices.
        window (int): The number of periods to use for the EMA calculation.

    Returns:
        float: The latest EMA value.
    """
    ema = data['close'].ewm(span=window, adjust=False).mean()
    return ema.iloc[-1]

def get_historical_data(symbol, token):
    """
    Fetches historical data for a given symbol.

    Args:
        symbol (str): The trading symbol (e.g., "SBIN").
        token (str): The instrument token.

    Returns:
        pd.DataFrame: A DataFrame containing the historical OHLC data, or None on error.
    """
    to_date = datetime.date.today()
    from_date = to_date - datetime.timedelta(days=20) # Fetch enough data for 14-period RSI and EMAs

    try:
        # Use the TIME_INTERVAL variable for chart data from config.py
        data = kite.historical_data(
            instrument_token=token,
            from_date=from_date,
            to_date=to_date,
            interval=TIME_INTERVAL,
            continuous=False,
            oci=False
        )
        if not data:
            config_logger.warning(f"No historical data returned for {symbol}.")
            return None

        df = pd.DataFrame(data)
        df.set_index('date', inplace=True)
        return df

    except Exception as e:
        config_logger.error(f"Failed to fetch historical data for {symbol}: {e}", exc_info=True)
        return None

def calculate_indicators(symbol):
    """
    Main function to calculate and update all necessary indicators.

    Args:
        symbol (str): The trading symbol.

    Returns:
        dict: A dictionary containing the latest indicator values.
    """
    token = get_instrument_token(symbol)
    if not token:
        config_logger.error(f"Could not find instrument token for {symbol}.")
        return None

    data = get_historical_data(symbol, token)
    if data is None:
        return None

    try:
        last_indicator_values["RSI_VALUE"] = calculate_rsi(data)
        last_indicator_values["EMA_SHORT"] = calculate_ema(data, window=12)
        last_indicator_values["EMA_LONG"] = calculate_ema(data, window=26)
        config_logger.info(f"Indicators calculated: RSI={last_indicator_values['RSI_VALUE']:.2f}, EMA_Short={last_indicator_values['EMA_SHORT']:.2f}, EMA_Long={last_indicator_values['EMA_LONG']:.2f}")

        return last_indicator_values
    except Exception as e:
        config_logger.error(f"Error calculating indicators: {e}", exc_info=True)
        return None

def check_entry_signal():
    """
    Checks for a buy or sell signal based on indicator values.

    Returns:
        str: 'BUY', 'SELL', or 'NONE'.
    """
    if last_indicator_values["RSI_VALUE"] is None or \
       last_indicator_values["EMA_SHORT"] is None or \
       last_indicator_values["EMA_LONG"] is None:
        config_logger.warning("Indicators not yet calculated. Cannot check for signals.")
        return 'NONE'

    # Example strategy:
    # BUY signal: Short EMA crosses above Long EMA AND RSI is below 70 (not overbought)
    # SELL signal: Short EMA crosses below Long EMA AND RSI is above 30 (not oversold)

    if last_indicator_values["EMA_SHORT"] > last_indicator_values["EMA_LONG"] and \
       last_indicator_values["RSI_VALUE"] < 70:
        return 'BUY'
    elif last_indicator_values["EMA_SHORT"] < last_indicator_values["EMA_LONG"] and \
         last_indicator_values["RSI_VALUE"] > 30:
        return 'SELL'
    else:
        return 'NONE'
