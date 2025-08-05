import pandas as pd
import datetime
import time
import logging
import pytz
from functools import wraps
from config import (
    kite, Instrument, TRADE_QUANTITY, TIME_INTERVAL,
    RSI_PERIOD, ATR_PERIOD, ATR_MULTIPLIER, TRAILING_STOP_MULTIPLIER,
    current_position, shutdown_requested, LIVE_MODE
)
from indicators import calculate_rsi, calculate_atr
from patterns import is_bullish_engulfing, is_bearish_engulfing
from kite_client import KiteClient
from symbol_resolver import resolve_current_month_symbol, resolve_token
import threading

#--Fetch IP of render
import requests
try:
    ip = requests.get('https://api.ipify.org').text
    print(f"My public IP address is: {ip}")
except Exception as e:
    print(f"Could not get IP: {e}")
    
# --- Helper Functions for Robustness ---
def retry(max_retries=3, initial_delay=1.0):
    """
    Decorator to retry a function call with exponential backoff on exceptions.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            for i in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    logging.warning(
                        f"Attempt {i + 1} of {max_retries} failed for {func.__name__}: {e}. Retrying in {delay} seconds."
                    )
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
            logging.error(f"Function {func.__name__} failed after {max_retries} retries. Giving up.")
            return None
        return wrapper
    return decorator

# --- Main Live Trading Strategy Class ---
class LiveTradingBot:
    def __init__(self):
        # Use the initialized KiteConnect client from config.py
        self.client = KiteClient(kite)
        self.historical_data = pd.DataFrame()
        self.rsi_values = None
        self.atr_values = None
        self.logger = logging.getLogger(__name__)
        self.instrument_token = None
        self.futures_symbol = None
        self.order_id = None
        self.last_order_price = None

    def initialize(self):
        """
        Initializes the bot by fetching historical data to prime the indicators.
        Resolves the correct futures contract instrument token.
        """
        if not self.client.kite:
            self.logger.error("Kite client is not initialized. Please ensure your config.py has a valid access token.")
            return False
        
        self.logger.info("Resolving futures contract instrument token...")
        
        self.futures_symbol = resolve_current_month_symbol()
        
        if not self.futures_symbol:
            self.logger.error(f"Could not resolve a tradable futures symbol for {Instrument}.")
            return False
        
        self.instrument_token = resolve_token(self.futures_symbol)
        
        if not self.instrument_token:
            self.logger.error(f"Could not resolve instrument token for {self.futures_symbol}.")
            return False
            
        self.logger.info(f"Resolved instrument token {self.instrument_token} for futures symbol: {self.futures_symbol}")
        
        end_date = datetime.datetime.now()
        start_date = end_date - datetime.timedelta(days=30)
        self.historical_data = self.client.get_historical_data(
            self.instrument_token, TIME_INTERVAL, start_date, end_date
        )
        if self.historical_data.empty:
            self.logger.error("Failed to fetch historical data. Exiting.")
            return False
            
        self.logger.info("Historical data loaded. Calculating initial indicators.")
        self.rsi_values = calculate_rsi(self.historical_data['close'], RSI_PERIOD)
        self.atr_values = calculate_atr(self.historical_data, ATR_PERIOD)
        self.logger.info("Indicators calculated successfully.")
        return True

    def check_initial_position(self):
        """
        Checks the Kite API for any existing positions on startup.
        """
        try:
            positions = self.client.kite.positions().get('net', [])
            for pos in positions:
                if pos['tradingsymbol'] == self.futures_symbol and pos['quantity'] != 0:
                    self.logger.info(f"Found active position for {self.futures_symbol} from Kite API.")
                    
                    # Update global position state based on API data
                    current_position.update({
                        "symbol": pos['tradingsymbol'],
                        "token": pos['instrument_token'],
                        "side": "LONG" if pos['quantity'] > 0 else "SHORT",
                        "active": True,
                        "quantity": abs(pos['quantity']),
                        "entry_price": pos['average_price'],
                        "initial_sl": 0,
                        "effective_sl": 0
                    })
                    return True
            self.logger.info("No active position found on Kite API. Starting fresh.")
            return False
        except Exception as e:
            self.logger.error(f"Error checking initial position from API: {e}", exc_info=True)
            return False

    @retry(max_retries=5)
    def _check_and_update_order_status(self):
        """
        Polls the Kite API to check the status of a pending order.
        Returns True if the order is filled, False otherwise.
        """
        if not self.order_id:
            return True # No order to check
            
        try:
            orders = self.client.kite.orders()
            order_info = next((o for o in orders if o['order_id'] == self.order_id), None)
            
            if order_info and order_info['status'] == 'COMPLETE':
                self.logger.info(f"Order {self.order_id} filled successfully. Price: {order_info['average_price']}")
                self.last_order_price = order_info['average_price']
                self.order_id = None # Clear the order ID
                return True
            else:
                self.logger.info(f"Order {self.order_id} is still pending. Current status: {order_info['status']}")
                return False
        except Exception as e:
            self.logger.error(f"Error checking order status: {e}", exc_info=True)
            return False
            
    def check_entry_conditions(self):
        """
        Checks for bullish and bearish divergence entry conditions and places orders.
        This now only updates the position state *after* an order is confirmed as filled.
        """
        if current_position["active"] or self.order_id:
            return

        last_n_candles = self.historical_data.iloc[-6:]
        current_candle = last_n_candles.iloc[-1].to_dict()
        current_rsi = self.rsi_values.iloc[-1]
        
        # Check for Bullish Divergence and Engulfing
        for i in range(1, 6):
            prev_candle = last_n_candles.iloc[-(i + 1)].to_dict()
            prev_rsi = self.rsi_values.iloc[-(i + 1)]
            
            if (current_candle['low'] < prev_candle['low'] and
                current_rsi > prev_rsi and
                is_bullish_engulfing(last_n_candles.iloc[-2].to_dict(), current_candle)):
                
                self.logger.info(f"Bullish Divergence detected at {current_candle['date']}. Placing BUY order.")
                if LIVE_MODE:
                    self.order_id = self.client.place_order(self.instrument_token, 'BUY', TRADE_QUANTITY)
                else:
                    self.logger.info("LIVE_MODE is False. Simulating BUY order.")
                    self.order_id = "paper_trade_id_buy" # Placeholder for paper trading
                break
        
        # Check for Bearish Divergence and Engulfing
        if not self.order_id:
            for i in range(1, 6):
                prev_candle = last_n_candles.iloc[-(i + 1)].to_dict()
                prev_rsi = self.rsi_values.iloc[-(i + 1)]
                
                if (current_candle['high'] > prev_candle['high'] and
                    current_rsi < prev_rsi and
                    is_bearish_engulfing(last_n_candles.iloc[-2].to_dict(), current_candle)):
                    
                    self.logger.info(f"Bearish Divergence detected at {current_candle['date']}. Placing SELL order.")
                    if LIVE_MODE:
                        self.order_id = self.client.place_order(self.instrument_token, 'SELL', TRADE_QUANTITY)
                    else:
                        self.logger.info("LIVE_MODE is False. Simulating SELL order.")
                        self.order_id = "paper_trade_id_sell"
                    break

    def check_exit_conditions(self):
        """
        Checks for the trailing stop-loss exit conditions.
        """
        if not current_position["active"] or self.order_id:
            return
            
        current_candle = self.historical_data.iloc[-1].to_dict()

        if current_position["side"] == 'LONG':
            current_sl = current_position["effective_sl"]
            new_sl = current_candle['low'] - (self.atr_values.iloc[-1] * TRAILING_STOP_MULTIPLIER)
            current_position["effective_sl"] = max(current_sl, new_sl)
            
            if current_candle['low'] <= current_position["effective_sl"]:
                self.logger.info("Trailing Stop-Loss triggered for LONG position. Placing SELL order.")
                if LIVE_MODE:
                    self.order_id = self.client.place_order(self.instrument_token, 'SELL', current_position["quantity"])
                else:
                    self.logger.info("LIVE_MODE is False. Simulating SELL order.")
                    self.order_id = "paper_trade_id_sell_exit"

        elif current_position["side"] == 'SHORT':
            current_sl = current_position["effective_sl"]
            new_sl = current_candle['high'] + (self.atr_values.iloc[-1] * TRAILING_STOP_MULTIPLIER)
            current_position["effective_sl"] = min(current_sl, new_sl)
            
            if current_candle['high'] >= current_position["effective_sl"]:
                self.logger.info("Trailing Stop-Loss triggered for SHORT position. Placing BUY order.")
                if LIVE_MODE:
                    self.order_id = self.client.place_order(self.instrument_token, 'BUY', current_position["quantity"])
                else:
                    self.logger.info("LIVE_MODE is False. Simulating BUY order.")
                    self.order_id = "paper_trade_id_buy_exit"
                
    def _is_market_open(self):
        """
        Checks if the current time is within Indian market hours (9:15 AM - 3:30 PM IST) and on a weekday.
        This function has been updated to be more resilient to server time zones.
        """
        ist = pytz.timezone('Asia/Kolkata')
        
        # Get the current time in UTC and convert it to IST
        now_utc = datetime.datetime.now(pytz.utc)
        now_ist = now_utc.astimezone(ist)
        
        market_open = now_ist.replace(hour=9, minute=15, second=0, microsecond=0)
        market_close = now_ist.replace(hour=15, minute=30, second=0, microsecond=0)
        
        is_weekday = 0 <= now_ist.weekday() <= 4
        
        is_open = is_weekday and market_open <= now_ist <= market_close
        
        # Log the calculated time for debugging
        self.logger.info(f"Current time in IST is {now_ist.strftime('%H:%M:%S')}. Market open check is: {is_open}.")
        
        return is_open
    
    def run(self):
        """
        The main loop for the trading bot, now with market hour management and order status checking.
        """
        self.logger.info("Starting live trading bot...")
        if not self.initialize():
            self.logger.error("Initialization failed. Cannot run the bot.")
            return

        self.check_initial_position()

        while not shutdown_requested.is_set():
            if self._is_market_open():
                if self.order_id:
                    # An order is pending, check its status
                    if self._check_and_update_order_status():
                        # If the order is filled, update the position
                        current_position.update({
                            "entry_price": self.last_order_price,
                            "active": True,
                            "initial_sl": 0 # This will be set on the next candle
                        })
                        if current_position["side"] == "LONG":
                             current_position["initial_sl"] = self.last_order_price - (self.atr_values.iloc[-1] * ATR_MULTIPLIER)
                        else:
                             current_position["initial_sl"] = self.last_order_price + (self.atr_values.iloc[-1] * ATR_MULTIPLIER)
                        current_position["effective_sl"] = current_position["initial_sl"]
                    else:
                        # If not filled, sleep and check again
                        self.logger.info("Waiting for order to fill...")
                        time.sleep(10) # Check more frequently for order status
                        continue # Skip the rest of the loop for this iteration
                
                # After checking order status, proceed with candle logic
                latest_candle = None
                retries = 0
                while not latest_candle and retries < 5:
                    latest_candle = self.client.get_live_data(self.instrument_token, TIME_INTERVAL)
                    if not latest_candle:
                        self.logger.info(f"No new candles found. Retrying in 10 seconds. Retry attempt {retries + 1}...")
                        time.sleep(10)
                        retries += 1

                if latest_candle and latest_candle['date'] not in self.historical_data.index:
                    new_candle_df = pd.DataFrame([latest_candle]).set_index('date')
                    self.historical_data = pd.concat([self.historical_data, new_candle_df])
                    
                    self.rsi_values = calculate_rsi(self.historical_data['close'], RSI_PERIOD)
                    self.atr_values = calculate_atr(self.historical_data, ATR_PERIOD)
                    
                    self.check_exit_conditions()
                    self.check_entry_conditions()
                elif latest_candle:
                    self.logger.info("Latest candle already in historical data. Waiting for the next candle...")
                
                self.logger.info("Waiting for the next candle...")
                time.sleep(300)
            else:
                self.logger.info("Market is closed. Sleeping until market open...")
                time.sleep(60)
    
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Create and run the bot
    bot = LiveTradingBot()
    bot.run()
