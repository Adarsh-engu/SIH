import sqlite3

conn = sqlite3.connect('backend/setu.db')
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE event_audit ADD COLUMN source VARCHAR DEFAULT 'live'")
    cursor.execute("UPDATE event_audit SET source = 'live' WHERE source IS NULL")
    conn.commit()
    print('Migration complete')
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("Column 'source' already exists.")
    else:
        print(f"Error: {e}")
finally:
    conn.close()
