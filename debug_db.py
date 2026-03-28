import duckdb
import os

base_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(base_dir, "backend", "data", "trader.db")

print(f"Checking DB at: {db_path}")

try:
    con = duckdb.connect(db_path)
    res = con.execute("SELECT count(*) FROM decisions").fetchall()
    print(f"Total decisions count: {res}")
    
    res2 = con.execute("SELECT * FROM decisions LIMIT 5").df()
    print(res2)
except Exception as e:
    print(e)
