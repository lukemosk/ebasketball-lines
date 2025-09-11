# Ebasketball Opening-Line Tracker

1) Create venv:
   python -m venv .venv
   . .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt

2) Copy .env.example -> .env and fill:
   BETSAPI_KEY=...
   LEAGUE_IDS=25067,XXXXX

3) Run once:
   python -m src.etl
