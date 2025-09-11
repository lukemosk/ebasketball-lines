import sqlite3

DB = "data/ebasketball.db"
con = sqlite3.connect(DB)

def count(sql):
    return con.execute(sql).fetchone()[0]

print("=== DB Summary ===")
print("Total tracked games:         ", count("SELECT COUNT(*) FROM event"))
print("Games with openers:         ", count("SELECT COUNT(DISTINCT event_id) FROM opener"))
print("Finished games:             ", count("SELECT COUNT(*) FROM event WHERE final_home IS NOT NULL AND final_away IS NOT NULL"))
print("Finished games w/ openers:  ", count("""
    SELECT COUNT(DISTINCT e.event_id)
    FROM event e
    JOIN opener o ON e.event_id=o.event_id
    WHERE e.final_home IS NOT NULL AND e.final_away IS NOT NULL
"""))
