import sqlite3
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "ollama-assist"
DB_FILE = CONFIG_DIR / "history.db"

def init_db():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Check if session column exists (for migrating old DB)
    c.execute("PRAGMA table_info(history)")
    columns = [col[1] for col in c.fetchall()]
    if "session" not in columns:
        c.execute('DROP TABLE history') # simple migration by dropping
    
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (id INTEGER PRIMARY KEY, session TEXT, role TEXT, content TEXT)''')
    conn.commit()
    return conn

def load_history(session="default"):
    conn = init_db()
    c = conn.cursor()
    c.execute('SELECT role, content FROM history WHERE session=? ORDER BY id ASC', (session,))
    rows = c.fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in rows]

def save_message(role, content, session="default"):
    conn = init_db()
    c = conn.cursor()
    c.execute('INSERT INTO history (session, role, content) VALUES (?, ?, ?)', (session, role, content))
    conn.commit()
    conn.close()

def clear_history(session="default"):
    conn = init_db()
    c = conn.cursor()
    c.execute('DELETE FROM history WHERE session=?', (session,))
    conn.commit()
    conn.close()

def get_sessions():
    conn = init_db()
    c = conn.cursor()
    c.execute('SELECT DISTINCT session FROM history')
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]
