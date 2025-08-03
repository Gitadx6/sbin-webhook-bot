def is_bullish_engulfing(d1: dict, d2: dict) -> bool:
    """Checks for a Bullish Engulfing pattern on two candles (represented as dictionaries)."""
    return (d1['close'] < d1['open'] and
            d2['close'] > d2['open'] and
            d2['close'] > d1['open'] and
            d2['open'] < d1['close'])

def is_bearish_engulfing(d1: dict, d2: dict) -> bool:
    """Checks for a Bearish Engulfing pattern on two candles (represented as dictionaries)."""
    return (d1['close'] > d1['open'] and
            d2['close'] < d2['open'] and
            d2['close'] < d1['open'] and
            d2['open'] > d1['close'])
