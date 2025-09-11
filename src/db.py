# src/db.py
import os
from sqlalchemy import create_engine, text

DB_URL = os.getenv("DB_URL", "sqlite:///data/ebasketball.db")
engine = create_engine(DB_URL, future=True)

def init_db():
    sql = open("schema.sql", "r", encoding="utf-8").read()

    if engine.url.get_backend_name() == "sqlite":
        # Use sqlite raw connection so we can call executescript
        raw = engine.raw_connection()
        try:
            cur = raw.cursor()
            cur.executescript(sql)
            raw.commit()
        finally:
            raw.close()
    else:
        # For Postgres/MySQL: run statements individually
        stmts = [s.strip() for s in sql.split(";") if s.strip()]
        with engine.begin() as conn:
            for stmt in stmts:
                conn.execute(text(stmt))
