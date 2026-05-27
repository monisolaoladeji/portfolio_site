import sqlite3

conn = sqlite3.connect('portfolio.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
print('SETTINGS')
for row in cur.execute("SELECT key, value FROM settings ORDER BY key"):
    print(row['key'], row['value'])
conn.close()
