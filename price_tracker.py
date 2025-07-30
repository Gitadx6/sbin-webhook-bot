# price_tracker.py
import sqlite3

DB_PATH = "price_track.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tracking (
                    id INTEGER PRIMARY KEY,
                    highest_price REAL,
                    lowest_price REAL
                )''')
    c.execute("INSERT OR IGNORE INTO tracking (id, highest_price, lowest_price) VALUES (1, NULL, NULL)")
    conn.commit()
    conn.close()

def save_price_track(high=None, low=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if high is not None:
        c.execute("UPDATE tracking SET highest_price = ? WHERE id = 1", (high,))
    if low is not None:
        c.execute("UPDATE tracking SET lowest_price = ? WHERE id = 1", (low,))
    conn.commit()
    conn.close()

def load_price_track():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT highest_price, lowest_price FROM tracking WHERE id = 1")
    row = c.fetchone()
    conn.close()
    return {
        "highest_price": row[0],
        "lowest_price": row[1]
    }
