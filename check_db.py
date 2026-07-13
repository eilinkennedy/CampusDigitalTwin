import os
import sqlite3

p = os.path.join(os.getcwd(), 'db.sqlite3')
print('cwd:', os.getcwd())
print('path:', p)
print('exists:', os.path.exists(p))
if os.path.exists(p):
    print('size:', os.path.getsize(p))
    try:
        conn = sqlite3.connect(p)
        cur = conn.execute('SELECT name FROM sqlite_master LIMIT 5')
        print('tables:', cur.fetchall())
        conn.close()
    except Exception as e:
        print('sqlite_error:', repr(e))
