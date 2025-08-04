import pandas as pd
import datetime
import time
import logging
from config import (
    kite, Instrument, TRADE_QUANTITY, TIME_INTERVAL,
    RSI_PERIOD, ATR_PERIOD, ATR_MULTIPLIER, TRAILING_STOP_MULTIPLIER
)
from indicators import calculate_rsi, calculate_atr
from patterns import is_bullish_engulfing, is_bearish_engulfing
from kite_client import KiteClient
from symbol_resolver import resolve_current_month_symbol, resolve_token # Import the new functions

# --- Global State from config.py ---
from config import current_position, shutdown_requested

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
    
    def initialize(self):
        """
        Initializes the bot by fetching historical data to prime the indicators.
        Resolves the correct futures contract instrument token.
        """
        self.logger.info("Resolving futures contract instrument token...")
        
        # Use the functions from symbol_resolver.py to get the symbol and token
        self.futures_symbol = resolve_current_month_symbol()
        
        if not self.futures_symbol:
            self.logger.error(f"Could not resolve a tradable futures symbol for {Instrument}.")
            return False
        
        self.instrument_token = resolve_token(self.futures_symbol)
        
        if not self.instrument_token:
            self.logger.error(f"Could not resolve instrument token for {self.futures_symbol}.")
            return False
            
        self.logger.info(f"Resolved instrument token {self.instrument_token} for futures symbol: {self.futures_symbol}")
        
        # Fetch historical data using the resolved token
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
                        "symbol": pos['tradingsymbol'], # Use the actual tradingsymbol from the API
                        "token": pos['instrument_token'],
                        "side": "LONG" if pos['quantity'] > 0 else "SHORT",
                        "active": True,
                        "quantity": abs(pos['quantity']),
                        "entry_price": pos['average_price'],
                        "initial_sl": 0, # Initial stop-loss will be updated on the next candle
                        "effective_sl": 0 # Effective stop-loss will be updated on the next candle
                    })
                    return True
            self.logger.info("No active position found on Kite API. Starting fresh.")
            return False
        except Exception as e:
            self.logger.error(f"Error checking initial position from API: {e}", exc_info=True)
            return False
            
    def check_entry_conditions(self):
        """
        Checks for bullish and bearish divergence entry conditions.
        """
        if current_position["active"]:
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
                self.client.place_order(self.instrument_token, 'BUY', TRADE_QUANTITY)
                current_position.update({
                    "symbol": self.futures_symbol,
                    "token": self.instrument_token,
                    "side": "LONG",
                    "active": True,
                    "quantity": TRADE_QUANTITY,
                    "entry_price": current_candle['open'],
                    "initial_sl": current_candle['open'] - (self.atr_values.iloc[-1] * ATR_MULTIPLIER)
                })
                current_position["effective_sl"] = current_position["initial_sl"]
                break
        
        # Check for Bearish Divergence and Engulfing
        if not current_position["active"]:
            for i in range(1, 6):
                prev_candle = last_n_candles.iloc[-(i + 1)].to_dict()
                prev_rsi = self.rsi_values.iloc[-(i + 1)]
                
                if (current_candle['high'] > prev_candle['high'] and
                    current_rsi < prev_rsi and
                    is_bearish_engulfing(last_n_candles.iloc[-2].to_dict(), current_candle)):
                    
                    self.logger.info(f"Bearish Divergence detected at {current_candle['date']}. Placing SELL order.")
                    self.client.place_order(self.instrument_token, 'SELL', TRADE_QUANTITY)
                    current_position.update({
                        "symbol": self.futures_symbol,
                        "token": self.instrument_token,
                        "side": "SHORT",
                        "active": True,
                        "quantity": TRADE_QUANTITY,
                        "entry_price": current_candle['open'],
                        "initial_sl": current_candle['open'] + (self.atr_values.iloc[-1] * ATR_MULTIPLIER)
                    })
                    current_position["effective_sl"] = current_position["initial_sl"]
                    break

    def check_exit_conditions(self):
        """
        Checks for the trailing stop-loss exit conditions.
        """
        if not current_position["active"]:
            return
            
        current_candle = self.historical_data.iloc[-1].to_dict()

        if current_position["side"] == 'LONG':
            # Update Trailing Stop-Loss
            current_sl = current_position["effective_sl"]
            new_sl = current_candle['low'] - (self.atr_values.iloc[-1] * TRAILING_STOP_MULTIPLIER)
            current_position["effective_sl"] = max(current_sl, new_sl)
            
            # Check for trigger
            if current_candle['low'] <= current_position["effective_sl"]:
                self.logger.info("Trailing Stop-Loss triggered for LONG position. Placing SELL order.")
                self.client.place_order(self.instrument_token, 'SELL', current_position["quantity"])
                current_position["active"] = False

        elif current_position["side"] == 'SHORT':
            # Update Trailing Stop-Loss
            current_sl = current_position["effective_sl"]
            new_sl = current_candle['high'] + (self.atr_values.iloc[-1] * TRAILING_STOP_MULTIPLIER)
            current_position["effective_sl"] = min(current_sl, new_sl)
            
            # Check for trigger
            if current_candle['high'] >= current_position["effective_sl"]:
                self.logger.info("Trailing Stop-Loss triggered for SHORT position. Placing BUY order.")
                self.client.place_order(self.instrument_token, 'BUY', current_position["quantity"])
                current_position["active"] = False
    
    def run(self):
        """
        The main loop for the trading bot.
        """
        self.logger.info("Starting live trading bot...")
        if not self.initialize():
            self.logger.error("Initialization failed. Cannot run the bot.")
            return

        # NEW: Check for an existing position from the API before starting the loop
        self.check_initial_position()

        while not shutdown_requested.is_set():
            latest_candle = self.client.get_live_data(self.instrument_token, TIME_INTERVAL)
            
            if latest_candle and latest_candle['date'] not in self.historical_data.index:
                new_candle_df = pd.DataFrame([latest_candle]).set_index('date')
                self.historical_data = pd.concat([self.historical_data, new_candle_df])
                
                self.rsi_values = calculate_rsi(self.historical_data['close'], RSI_PERIOD)
                self.atr_values = calculate_atr(self.historical_data, ATR_PERIOD)
                
                self.check_exit_conditions()
                self.check_entry_conditions()
            
            self.logger.info("Waiting for the next candle...")
            time.sleep(300) # Sleep for 5 minutes

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Create and run the bot
    bot = LiveTradingBot()
    bot.run()
