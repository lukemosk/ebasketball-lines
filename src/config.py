import os
from dotenv import load_dotenv
load_dotenv()
CONF = {
    "token": os.getenv("BETSAPI_KEY", ""),
    "book": os.getenv("BOOKMAKER_ID", "bet365"),
    "league_ids": [int(x) for x in os.getenv("LEAGUE_IDS","").split(",") if x],
    "poll_seconds": int(os.getenv("POLL_SECONDS","180")),
    "db_url": os.getenv("DB_URL","sqlite:///data/ebasketball.db"),
}
