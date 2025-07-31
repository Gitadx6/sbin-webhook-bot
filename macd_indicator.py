import logging
import traceback

# Configure logging for this module
logger = logging.getLogger(__name__)

def calculate_ema(data, period):
    """
    Calculates the Exponential Moving Average (EMA) for a given data set and period.
    
    Args:
        data (list): A list of closing prices.
        period (int): The number of periods for the EMA calculation.
        
    Returns:
        float: The final EMA value, or None if there's not enough data.
    """
    if len(data) < period:
        return None
    
    # Calculate the smoothing factor
    alpha = 2 / (period + 1)
    
    # Calculate the initial EMA (first data point is simple moving average)
    ema = sum(data[:period]) / period
    
    # Iterate through the rest of the data to calculate the EMA
    for price in data[period:]:
        ema = (price * alpha) + (ema * (1 - alpha))
        
    return ema

def calculate_macd(data):
    """
    Calculates the MACD line and the Signal line.
    
    Args:
        data (list): A list of closing prices.
        
    Returns:
        tuple: A tuple containing (macd_line, signal_line) or (None, None) if there's
               not enough data to perform the calculation.
    """
    try:
        # MACD Line: (12-day EMA - 26-day EMA)
        ema_12 = calculate_ema(data, 12)
        ema_26 = calculate_ema(data, 26)
        
        if ema_12 is None or ema_26 is None:
            return None, None
            
        macd_line = ema_12 - ema_26

        # Signal Line: 9-day EMA of the MACD Line
        # We need to simulate the MACD line over time to calculate its EMA
        macd_history = []
        for i in range(26, len(data)):
            short_data = data[i-12:i]
            long_data = data[i-26:i]
            
            short_ema = calculate_ema(short_data, 12)
            long_ema = calculate_ema(long_data, 26)
            
            if short_ema and long_ema:
                macd_history.append(short_ema - long_ema)
        
        signal_line = calculate_ema(macd_history, 9)

        return macd_line, signal_line

    except Exception as e:
        logger.error(f"Error calculating MACD: {e}\n{traceback.format_exc()}")
        return None, None

def is_bullish_crossover(historical_data):
    """
    Checks for a bullish crossover, which is when the MACD line crosses above the signal line.
    This corresponds to the MACD histogram turning green.
    
    Args:
        historical_data (list): A list of recent closing prices for the symbol.
        
    Returns:
        bool: True if a bullish crossover is detected, False otherwise.
    """
    try:
        if len(historical_data) < 35:
            logger.warning("Not enough historical data to check for MACD bullish crossover.")
            return False
            
        # Get the two most recent MACD and Signal values
        current_macd, current_signal = calculate_macd(historical_data)
        previous_macd, previous_signal = calculate_macd(historical_data[:-1])

        if (current_macd is not None and current_signal is not None and
            previous_macd is not None and previous_signal is not None):
            
            # Check for the crossover condition
            if previous_macd <= previous_signal and current_macd > current_signal:
                logger.info("MACD Bullish Crossover (histogram turned green) detected!")
                return True
                
        return False

    except Exception as e:
        logger.error(f"Error checking for MACD bullish crossover: {e}\n{traceback.format_exc()}")
        return False

def is_bearish_crossover(historical_data):
    """
    Checks for a bearish crossover, which is when the MACD line crosses below the signal line.
    This corresponds to the MACD histogram turning red.
    
    Args:
        historical_data (list): A list of recent closing prices for the symbol.
        
    Returns:
        bool: True if a bearish crossover is detected, False otherwise.
    """
    try:
        if len(historical_data) < 35:
            logger.warning("Not enough historical data to check for MACD bearish crossover.")
            return False
            
        # Get the two most recent MACD and Signal values
        current_macd, current_signal = calculate_macd(historical_data)
        previous_macd, previous_signal = calculate_macd(historical_data[:-1])

        if (current_macd is not None and current_signal is not None and
            previous_macd is not None and previous_signal is not None):
            
            # Check for the crossover condition
            if previous_macd >= previous_signal and current_macd < current_signal:
                logger.info("MACD Bearish Crossover (histogram turned red) detected!")
                return True
                
        return False

    except Exception as e:
        logger.error(f"Error checking for MACD bearish crossover: {e}\n{traceback.format_exc()}")
        return False
