import json
import os

TRACK_PATH = r"D:\Personal\Trade\TSL\price_track.json"

def load_price_track():
    if not os.path.exists(TRACK_PATH):
        return {"highest_price": None, "lowest_price": None}
    try:
        with open(TRACK_PATH, "r") as f:
            return json.load(f)
    except:
        return {"highest_price": None, "lowest_price": None}

def save_price_track(high=None, low=None):
    data = load_price_track()
    if high is not None:
        data["highest_price"] = high
    if low is not None:
        data["lowest_price"] = low
    with open(TRACK_PATH, "w") as f:
        json.dump(data, f)
