import sqlite3
con = sqlite3.connect("data/ebasketball.db")
con.execute("UPDATE event SET final_home=NULL, final_away=NULL, status='not_started' WHERE event_id=181107468")
con.execute("DELETE FROM result WHERE event_id=181107468")
con.commit()
print("Cleared problematic game")