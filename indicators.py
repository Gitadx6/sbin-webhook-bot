import pandas as pd
import numpy as np
import logging

# --- Logging Setup for this module ---
indicators_logger = logging.getLogger(__name__)

class IndicatorCalculator:
    """
    A utility class to calculate common technical indicators.

    This class is designed to work with pandas DataFrames containing OHLC data.
    """
    def __init__(self):
        """
        Initializes the IndicatorCalculator.
        """
        indicators_logger.info("IndicatorCalculator initialized.")

    def calculate_ema(self, df: pd.DataFrame, column: str = "close", periods: list = [9, 21]) -> pd.DataFrame:
        """
        Calculates the Exponential Moving Average (EMA) for specified periods.

        Args:
            df (pd.DataFrame): The input DataFrame with at least a 'close' column.
            column (str): The column name on which to calculate the EMA.
            periods (list): A list of integer periods for the EMA calculation.

        Returns:
            pd.DataFrame: The DataFrame with new columns for each EMA (e.g., 'ema_9', 'ema_21').
        """
        if column not in df.columns:
            indicators_logger.error(f"Column '{column}' not found in the DataFrame.")
            return df

        for period in periods:
            ema_column_name = f"ema_{period}"
            # Pandas' ewm method provides a simple way to calculate EMA.
            df[ema_column_name] = df[column].ewm(span=period, adjust=False).mean()
            indicators_logger.info(f"Calculated EMA for period {period}.")
        return df

    def calculate_adx(self, df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """
        Calculates the Average Directional Index (ADX) and its components (+DI, -DI).

        ADX is a non-trivial calculation that involves several steps.
        This implementation follows the standard Wilder's smoothing method.

        Args:
            df (pd.DataFrame): The input DataFrame with 'high', 'low', and 'close' columns.
            period (int): The look-back period for the ADX calculation (e.g., 14).

        Returns:
            pd.DataFrame: The DataFrame with new columns for ADX, +DI, and -DI.
        """
        required_columns = ["high", "low", "close"]
        if not all(col in df.columns for col in required_columns):
            indicators_logger.error("DataFrame is missing required columns: 'high', 'low', or 'close'.")
            return df

        # --- Step 1: Calculate Directional Movement (+DM and -DM) ---
        df['up_move'] = df['high'].diff()
        df['down_move'] = df['low'].diff() * -1 # Make it positive
        
        df['+dm'] = np.where(
            (df['up_move'] > df['down_move']) & (df['up_move'] > 0),
            df['up_move'], 0
        )
        df['-dm'] = np.where(
            (df['down_move'] > df['up_move']) & (df['down_move'] > 0),
            df['down_move'], 0
        )
        
        # --- Step 2: Calculate True Range (TR) ---
        df['tr'] = np.where(
            (df['high'] - df['low']) > (df['high'] - df['close'].shift(1)).abs(),
            np.where(
                (df['high'] - df['low']) > (df['low'] - df['close'].shift(1)).abs(),
                df['high'] - df['low'],
                (df['low'] - df['close'].shift(1)).abs()
            ),
            np.where(
                (df['high'] - df['close'].shift(1)).abs() > (df['low'] - df['close'].shift(1)).abs(),
                (df['high'] - df['close'].shift(1)).abs(),
                (df['low'] - df['close'].shift(1)).abs()
            )
        )
        
        # --- Step 3: Calculate Smoothed Directional Indicators (+DI and -DI) ---
        # The Wilder's smoothing method uses a specific formula for the first value
        # and then a rolling average for the rest.
        df[f'smoothed_+dm'] = df['+dm'].ewm(alpha=1/period, adjust=False).mean()
        df[f'smoothed_-dm'] = df['-dm'].ewm(alpha=1/period, adjust=False).mean()
        df[f'smoothed_tr'] = df['tr'].ewm(alpha=1/period, adjust=False).mean()

        # Calculate +DI and -DI
        df[f'+di_{period}'] = (df[f'smoothed_+dm'] / df[f'smoothed_tr']) * 100
        df[f'-di_{period}'] = (df[f'smoothed_-dm'] / df[f'smoothed_tr']) * 100

        # --- Step 4: Calculate DX (Directional Index) ---
        df['dx'] = (abs(df[f'+di_{period}'] - df[f'-di_{period}']) / (df[f'+di_{period}'] + df[f'-di_{period}'])) * 100

        # --- Step 5: Calculate ADX (Smoothed DX) ---
        df[f'adx_{period}'] = df['dx'].ewm(alpha=1/period, adjust=False).mean()

        # Drop intermediate columns for a cleaner final DataFrame
        df.drop(
            columns=['up_move', 'down_move', '+dm', '-dm', 'tr', 'smoothed_+dm', 'smoothed_-dm', 'smoothed_tr', 'dx'],
            inplace=True
        )

        indicators_logger.info(f"Calculated ADX, +DI, and -DI for period {period}.")
        return df

