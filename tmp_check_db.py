import sqlite3

conn = sqlite3.connect('portfolio.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
print('PROJECTS')
for row in cur.execute('SELECT id, title, screenshot_path FROM projects ORDER BY id LIMIT 10'):
    print(row['id'], row['title'], row['screenshot_path'])
print('SCREENSHOTS')
for row in cur.execute('SELECT id, project_id, image_path FROM project_screenshots ORDER BY id DESC LIMIT 10'):
    print(row['id'], row['project_id'], row['image_path'])
print('PROFILE')
for row in cur.execute("SELECT value FROM settings WHERE key='profile_photo_path'"):
    print(row['value'])
conn.close()
