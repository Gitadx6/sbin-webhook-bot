import datetime

def resolve_sbin_future():
    today = datetime.date.today()
    expiry = today + datetime.timedelta((3 - today.weekday()) % 7)  # Thursday
    return f"SBIN{expiry.strftime('%d%b').upper()}FUT"
