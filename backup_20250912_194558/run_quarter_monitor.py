# run_quarter_monitor.py - Standalone quarter monitor runner
from live_quarter_monitor import LiveQuarterMonitor
import sys

def main():
    print("Basketball Quarter Line Monitor")
    print("This will monitor live games and capture lines at quarter endings")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    
    cycles = None
    if len(sys.argv) > 1:
        try:
            cycles = int(sys.argv[1])
            print(f"Running for {cycles} cycles only")
        except:
            print("Invalid cycle count, running indefinitely")
    
    monitor = LiveQuarterMonitor()
    monitor.run(cycles=cycles)

if __name__ == "__main__":
    main()
