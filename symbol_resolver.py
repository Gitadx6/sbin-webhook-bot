import logging
import datetime
from kiteconnect import KiteConnect

# --- Project-specific Imports ---
# Import the entire config module to access the 'instrument' variable
import config

# Configure logging for this module
logger = logging.getLogger(__name__)

# Days before expiry to roll over to the next month's contract
# A value of 2 means the rollover happens on the second-to-last trading day of the month.
# You can set this as an environment variable or in your config.py
ROLLOVER_DAYS = 2 

def get_expiry_date(month, year):
    """
    Finds the last Thursday of a given month and year, which is the expiry date for NSE futures.
    Returns a datetime.date object.
    """
    d = datetime.date(year, month, 1)
    # Loop to the last day of the month
    d = datetime.date(year, month, 28)
    while d.weekday() != 3: # 3 represents Thursday
        d += datetime.timedelta(days=1)
    
    # We are now on a Thursday, find the last one.
    while d.month == month:
        d += datetime.timedelta(days=7)
    
    # Backtrack by one week to get the last Thursday
    d -= datetime.timedelta(days=7)
    return d

def resolve_current_month_symbol():
    """
    Generates the full futures contract symbol for the current or next month's expiry,
    based on the rollover logic and the instrument from config.py.
    
    Returns:
        str: The full futures symbol (e.g., "SBIN24DEC").
    """
    # Get the base symbol from your config.py file
    base_symbol = config.Instrument
    
    now = datetime.datetime.now()
    
    # Get the expiry date for the current month
    current_expiry_date = get_expiry_date(now.month, now.year)
    
    # Determine the rollover date based on the expiry date
    rollover_date = current_expiry_date - datetime.timedelta(days=ROLLOVER_DAYS)
    
    # If today's date is on or after the rollover date, use the next month's contract
    if now.date() >= rollover_date:
        # Calculate next month's year and month
        if now.month == 12:
            next_month = 1
            next_year = now.year + 1
        else:
            next_month = now.month + 1
            next_year = now.year
    else:
        # Otherwise, stick to the current month's contract
        next_month = now.month
        next_year = now.year
        
    # Get the last two digits of the year
    year_str = str(next_year)[-2:]
    
    # Get the three-letter abbreviation for the month
    month_abbr = datetime.date(next_year, next_month, 1).strftime('%b').upper()
    
    # Construct the full symbol name
    future_symbol = f"{base_symbol}{year_str}{month_abbr}FUT"
    return future_symbol

def resolve_token(symbol):
    """
    Resolves the instrument token for a given symbol from the instrument dump.
    
    Args:
        symbol (str): The trading symbol (e.g., "BANKNIFTY24DEC48000CE").
        
    Returns:
        int: The instrument token if found, otherwise None.
    """
    # Assuming 'kite' is imported from your config.py as per your original code.
    from config import kite

    try:
        # Note: For futures, it's more efficient to specify the exchange as 'NFO'
        instruments = kite.instruments(exchange='NFO')
        for instrument in instruments:
            if instrument['tradingsymbol'] == symbol:
                return instrument['instrument_token']
        logger.warning(f"Instrument token not found for symbol: {symbol}")
        return None
    except Exception as e:
        logger.error(f"Error resolving token for {symbol}: {e}")
        return None

