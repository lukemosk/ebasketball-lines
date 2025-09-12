# run_tracker.py
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())
import time, subprocess

POLL_SECONDS = 60  # every 1 minute(s)

while True:
    print("\n=== ETL ===")
    subprocess.run([r".\.venv\Scripts\python.exe", "-m", "src.etl"])
    #print("=== Openers ===")
    #subprocess.run([r".\.venv\Scripts\python.exe", "backfill_openers.py"])
    #print("=== Retry Missing Openers ===")
    #subprocess.run([r".\.venv\Scripts\python.exe", "-m", "src.backfill_openers_retry_missing"])  # <-- changed
    print("=== Results ===")
    subprocess.run([r".\.venv\Scripts\python.exe", "backfill_results.py"])
    print(f"Sleeping {POLL_SECONDS}s...")
    time.sleep(POLL_SECONDS)
