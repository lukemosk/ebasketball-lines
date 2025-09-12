# run_integrated_tracker.py - Full tracker with quarter monitoring
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import time
import subprocess
import threading
from live_quarter_monitor import LiveQuarterMonitor

class IntegratedTracker:
    def __init__(self):
        self.quarter_monitor = None
        self.monitor_thread = None
        self.running = True
    
    def start_quarter_monitor(self):
        """Start quarter monitoring in a separate thread"""
        def monitor_worker():
            self.quarter_monitor = LiveQuarterMonitor()
            # Run indefinitely until stopped
            while self.running:
                try:
                    self.quarter_monitor.monitor_cycle()
                    time.sleep(10)  # 10 second polling
                except Exception as e:
                    print(f"Quarter monitor error: {e}")
                    time.sleep(30)  # Wait longer on error
        
        self.monitor_thread = threading.Thread(target=monitor_worker, daemon=True)
        self.monitor_thread.start()
        print("Quarter monitoring started in background")
    
    def run_etl_cycle(self):
        """Run the standard ETL cycle"""
        print("\n=== ETL ===")
        subprocess.run([r".\.venv\Scripts\python.exe", "-m", "src.etl"])
        print("=== Openers ===")
        subprocess.run([r".\.venv\Scripts\python.exe", "backfill_openers.py"])
        print("=== Retry Missing Openers ===")
        subprocess.run([r".\.venv\Scripts\python.exe", "-m", "src.backfill_openers_retry_missing"])
        print("=== Results ===")
        subprocess.run([r".\.venv\Scripts\python.exe", "backfill_results.py"])
    
    def run(self):
        POLL_SECONDS = 60  # Main ETL cycle every 60 seconds
        
        print("INTEGRATED EBASKETBALL TRACKER")
        print("- Standard ETL every 60 seconds")
        print("- Live quarter monitoring every 10 seconds")
        print("- Press Ctrl+C to stop")
        print("=" * 60)
        
        # Start quarter monitoring
        self.start_quarter_monitor()
        
        try:
            while True:
                self.run_etl_cycle()
                print(f"Sleeping {POLL_SECONDS}s... (quarter monitor running in background)")
                time.sleep(POLL_SECONDS)
        except KeyboardInterrupt:
            print("\nStopping integrated tracker...")
            self.running = False
            if self.monitor_thread:
                self.monitor_thread.join(timeout=2)

def main():
    tracker = IntegratedTracker()
    tracker.run()

if __name__ == "__main__":
    main()
