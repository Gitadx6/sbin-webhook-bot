import datetime
import calendar
from config import kite, resolve_token


def get_monthly_expiry(date_obj):
    """Get the last Thursday of the given month."""
    year = date_obj.year
    month = date_obj.month
    last_day = calendar.monthrange(year, month)[1]

    for day in range(last_day, 0, -1):
        d = datetime.date(year, month, day)
        if d.weekday() == 3:  # Thursday
            return d


def get_sbin_symbols():
    instruments = kite.instruments("NFO")
    return sorted(
        [i["tradingsymbol"] for i in instruments if i["tradingsymbol"].startswith("SBIN") and i["instrument_type"] == "FUT"],
        reverse=True
    )


def resolve_sbin_future():
    today = datetime.date.today()
    expiry = get_monthly_expiry(today)

    # 🔄 Switch to next month 2 days before expiry
    if (expiry - today).days <= 2:
        next_month = today.replace(day=28) + datetime.timedelta(days=4)
        next_month = next_month.replace(day=1)
        expiry = get_monthly_expiry(next_month)

    all_sbin = get_sbin_symbols()

    # Construct target symbol
    target_symbol = f"SBIN{str(expiry.year)[-2:]}{expiry.strftime('%b').upper()}FUT"
    print(f"\n🔍 Trying to resolve SBIN future symbol for expiry: {expiry}")
    print(f"🔧 Target Symbol: {target_symbol}")
    print(f"📦 All available SBIN FUT symbols: {all_sbin[:5]} ...\n")  # Show top 5 for brevity

    for symbol in all_sbin:
        if target_symbol in symbol:
            print(f"➡️ Attempting: {symbol}")
            try:
                token = resolve_token(symbol)
                now = datetime.datetime.now()
                past = now - datetime.timedelta(days=2)
                candles = kite.historical_data(
                    instrument_token=token,
                    from_date=past,
                    to_date=now,
                    interval="30minute"
                )
                print(f"📈 {symbol} - Candle count: {len(candles)}")
                if len(candles) >= 26:
                    print(f"✅ Selected SBIN future: {symbol}")
                    return symbol
                else:
                    print(f"⚠️ Insufficient data for {symbol}: only {len(candles)} candles")
            except Exception as e:
                print(f"❌ Error fetching candles for {symbol}: {e}")
                continue

    raise Exception("❌ No valid SBIN FUTURE symbol found with sufficient candle data.")
