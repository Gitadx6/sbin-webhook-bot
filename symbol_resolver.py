import datetime
import calendar

def resolve_sbin_future():
    today = datetime.date.today()
    expiry = get_monthly_expiry(today)

    # 🔄 Switch to next month 2 days before expiry
    if (expiry - today).days <= 2:
        # Move to next month
        next_month = today.replace(day=28) + datetime.timedelta(days=4)
        next_month = next_month.replace(day=1)
        expiry = get_monthly_expiry(next_month)

    # 🧩 Format: SBIN25JULFUT
    symbol = f"SBIN{str(expiry.year)[-2:]}{expiry.strftime('%b').upper()}FUT"
    return symbol

def get_monthly_expiry(date_obj):
    """Get the last Thursday of the given month."""
    year = date_obj.year
    month = date_obj.month
    last_day = calendar.monthrange(year, month)[1]

    for day in range(last_day, 0, -1):
        d = datetime.date(year, month, day)
        if d.weekday() == 3:  # Thursday
            return d
