import sqlite3

conn = sqlite3.connect('portfolio.db')
cur = conn.cursor()
cur.execute("UPDATE settings SET value = ? WHERE key = 'contact_linkedin'", ('https://www.linkedin.com/in/monisolaoladeji',))
conn.commit()
conn.close()
print('Updated contact_linkedin to https://www.linkedin.com/in/monisolaoladeji')
