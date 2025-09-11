# cleanup_project.py - Clean up old debug scripts
import os
import shutil
from datetime import datetime

# Scripts to archive (old ChatGPT debug tools)
TO_ARCHIVE = [
    "analyze_accuracy.py",
    "audit_openers.py", 
    "audit_sample_rows.py",
    "audit_sample_rows_fixed.py",
    "audit_watchboard_consistency.py",
    "backfill_results_force.py",
    "check_db.py",
    "check_finished_candidates.py", 
    "clean_suspect_results.py",
    "count_mismatches.py",
    "diag_probe_event.py",
    "diag_recent.py",
    "fix_opened_at.py",
    "fix_stray_finals.py",
    "peek_db.py",
    "peek_openers_now.py",
    "peek_openers_per_game.py",
    "probe_api.py",
    "probe_event_view.py", 
    "probe_h2h.py",
    "probe_inplay.py",
    "probe_leagues.py",
    "probe_prematch.py",
    "probe_results_api.py",
    "probe_status.py",
    "probe_upcoming.py",
    "purge_bad_totals.py",
    "recent_null_openers.py",
    "repair_finals_strict.py",
    "repair_recent_finals.py",
    "verify_deltas.py",
    "watchboard.py",  # replaced by enhanced_dashboard.py
    "db_summary.py",  # functionality moved to data_quality.py
]

# Scripts to keep (core functionality)
TO_KEEP = [
    "src/",
    "enhanced_dashboard.py",
    "data_quality.py", 
    "performance_optimizer.py",
    "verify_fix.py",
    "live_monitor.py",
    "run_tracker.py",
    "backfill_openers.py",
    "backfill_results.py",
    "schema.sql",
    "requirements.txt",
    ".env.example",
    ".gitignore",
    "README.md"
]

def cleanup_project():
    print("🧹 PROJECT CLEANUP")
    print("="*50)
    
    # Create archive directory
    archive_dir = f"archived_scripts_{datetime.now().strftime('%Y%m%d')}"
    if not os.path.exists(archive_dir):
        os.makedirs(archive_dir)
        print(f"📂 Created archive directory: {archive_dir}")
    
    moved_count = 0
    not_found = 0
    
    # Move old scripts to archive
    for script in TO_ARCHIVE:
        if os.path.exists(script):
            try:
                shutil.move(script, os.path.join(archive_dir, script))
                print(f"  ✅ Archived: {script}")
                moved_count += 1
            except Exception as e:
                print(f"  ❌ Failed to archive {script}: {e}")
        else:
            not_found += 1
    
    print(f"\n📊 SUMMARY:")
    print(f"  ✅ Archived: {moved_count} files")
    print(f"  ❓ Not found: {not_found} files")
    
    # Show current project structure
    print(f"\n📁 CURRENT PROJECT STRUCTURE:")
    for item in sorted(os.listdir(".")):
        if os.path.isfile(item) and item.endswith('.py'):
            status = "🟢 KEEP" if any(item in keep for keep in TO_KEEP) else "🟡 REVIEW"
            print(f"  {status} {item}")
        elif os.path.isdir(item) and not item.startswith('.') and item != archive_dir:
            print(f"  📁 {item}/")
    
    print(f"\n🎯 RECOMMENDATIONS:")
    print(f"  1. Review archived scripts in '{archive_dir}/' before deleting")
    print(f"  2. Update your .gitignore to exclude archived_scripts_*")
    print(f"  3. Consider creating a docs/ folder for documentation")
    print(f"  4. Your core system is now much cleaner! 🎉")

def create_clean_readme():
    """Create a clean README for the organized project"""
    readme_content = """# EBasketball Lines Tracker

A system for tracking opening lines vs closing results for eBasketball games using BetsAPI.

## Quick Start

1. Setup environment:
   ```bash
   python -m venv .venv
   .venv\\Scripts\\activate
   pip install -r requirements.txt
   ```

2. Configure:
   ```bash
   cp .env.example .env
   # Edit .env with your BETSAPI_KEY and LEAGUE_IDS
   ```

3. Run:
   ```bash
   python run_tracker.py
   ```

## Core Files

- `src/etl.py` - Main ETL process
- `src/betsapi.py` - BetsAPI client
- `run_tracker.py` - Main runner script
- `backfill_*.py` - Data backfill scripts

## Monitoring Tools

- `enhanced_dashboard.py` - Real-time dashboard
- `data_quality.py` - Data quality analysis  
- `verify_fix.py` - System health checks
- `live_monitor.py` - Live monitoring

## Analysis

The system tracks how opening spreads/totals compare to final game margins/totals, looking for games that finish within 2-5 points of the opening lines.

## Database Schema

See `schema.sql` for complete database structure.
"""
    
    with open("README.md", "w") as f:
        f.write(readme_content)
    
    print("📝 Created clean README.md")

if __name__ == "__main__":
    cleanup_project()
    
    create_clean = input("\n📝 Create clean README.md? [y/N]: ")
    if create_clean.lower() == 'y':
        create_clean_readme()
        
    print(f"\n🎉 Project cleanup complete!")
    print(f"Your project is now much more organized and maintainable.")