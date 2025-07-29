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

    for symbol in all_sbin:
        if f"SBIN{str(expiry.year)[-2:]}{expiry.strftime('%b').upper()}FUT" in symbol:
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
                if len(candles) >= 26:
                    return symbol
            except:
                continue

    raise Exception("❌ No valid SBIN FUTURE symbol found with sufficient candle data.")
