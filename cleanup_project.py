# cleanup_project.py
import os
import shutil
from datetime import datetime

def cleanup_project():
    """Backup and remove unnecessary files from the ebasketball project"""
    
    # Create backup directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = f"backup_{timestamp}"
    os.makedirs(backup_dir, exist_ok=True)
    
    print(f"🗄️ Creating backup in: {backup_dir}/")
    
    # Files to delete (with reasons)
    files_to_delete = {
        # Archived scripts (already in archived folder)
        "archived_scripts_20250911/": "Already archived - duplicates",
        
        # Test/debug scripts that served their purpose
        "test_live_betting_lines.py": "Test script - no longer needed",
        "comprehensive_debug.py": "Debug script - served its purpose",
        "simple_quarter_tracker.py": "Replaced by integrated_quarter_tracker.py",
        "working_line_extractor.py": "Test script - logic integrated into main tracker",
        "live_quarter_tracker_inplay.py": "Old version - replaced by integrated tracker",
        
        # Setup scripts that have been run
        "setup_quarter_monitoring.py": "Setup complete - no longer needed",
        "setup_quarter_table.py": "Setup complete - no longer needed",
        
        # Duplicate/unused analysis scripts
        "middling_windows_test.py": "Test version of middling analysis",
        "variance_analysis.py": "One-off analysis - can regenerate if needed",
        
        # Old runners replaced by integrated tracker
        "run_quarter_monitor.py": "Replaced by run_integrated_tracker.py",
        "live_quarter_monitor.py": "Old version - logic in integrated tracker",
        
        # Database management scripts (run once)
        "create_fresh_database.py": "One-time use - database created",
        "verify_fresh_setup.py": "One-time verification - complete",
        "sync_game_status.py": "One-time fix - complete",
        
        # Debug/monitoring scripts (can regenerate)
        "debug_captures.py": "Debug script - can use live_db_monitor.py instead",
        "check_captures.py": "Replaced by live_db_monitor.py",
        
        # Old batch files
        "run_etl.bat": "Windows-specific - using Python scripts instead",
        
        # Temporary analysis scripts
        "analyze_all_captures.py": "Can regenerate from quarter_middling_analysis.py",
        "create_unified_view.py": "View creation - already done",
        
        # Probe/test scripts
        "probe_api.py": "API testing complete",
    }
    
    # Backup and delete files
    deleted_count = 0
    for file_path, reason in files_to_delete.items():
        if os.path.exists(file_path):
            print(f"\n📁 {file_path}")
            print(f"   Reason: {reason}")
            
            # Create backup
            backup_path = os.path.join(backup_dir, file_path)
            
            try:
                if os.path.isdir(file_path):
                    # Backup directory
                    shutil.copytree(file_path, backup_path)
                    shutil.rmtree(file_path)
                    print(f"   ✅ Directory backed up and removed")
                else:
                    # Backup file
                    os.makedirs(os.path.dirname(backup_path), exist_ok=True)
                    shutil.copy2(file_path, backup_path)
                    os.remove(file_path)
                    print(f"   ✅ File backed up and removed")
                
                deleted_count += 1
                
            except Exception as e:
                print(f"   ❌ Error: {e}")
    
    print(f"\n✨ CLEANUP COMPLETE")
    print(f"Backed up and removed {deleted_count} items")
    print(f"Backup location: {backup_dir}/")
    
    # Show remaining key files
    print("\n📂 KEY FILES REMAINING:")
    key_files = {
        "run_integrated_tracker.py": "Main tracker - runs everything",
        "integrated_quarter_tracker.py": "Core quarter tracking logic",
        "live_db_monitor.py": "Real-time database monitor",
        "backfill_openers.py": "Opening lines backfill",
        "backfill_results.py": "Results backfill",
        "middling_analysis.py": "Opening line middling analysis",
        "quarter_middling_analysis.py": "Quarter-based middling analysis",
        "src/": "Core source code directory",
        "data/": "Database directory",
        "schema.sql": "Database schema",
        ".env": "Configuration",
    }
    
    for file, purpose in key_files.items():
        if os.path.exists(file):
            print(f"  ✅ {file:<35} - {purpose}")
    
    # Create a restore script
    restore_script = f"""# restore_backup.py
# Generated restore script for backup_{timestamp}

import os
import shutil

def restore_backup():
    backup_dir = "{backup_dir}"
    
    if not os.path.exists(backup_dir):
        print("❌ Backup directory not found!")
        return
    
    print("🔄 Restoring from backup...")
    
    for root, dirs, files in os.walk(backup_dir):
        for file in files:
            src = os.path.join(root, file)
            dst = src.replace(backup_dir + os.sep, "")
            
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            print(f"  Restored: {{dst}}")
    
    print("✅ Restore complete!")

if __name__ == "__main__":
    confirm = input("Restore backup {backup_dir}? [y/N]: ")
    if confirm.lower() == 'y':
        restore_backup()
"""
    
    with open(f"{backup_dir}/restore_backup.py", "w") as f:
        f.write(restore_script)
    
    print(f"\n💡 TIP: To restore files later, run:")
    print(f"   python {backup_dir}/restore_backup.py")

if __name__ == "__main__":
    print("🧹 EBASKETBALL PROJECT CLEANUP")
    print("=" * 50)
    print("This will backup and remove unnecessary files.")
    print("A restore script will be created in the backup folder.")
    
    confirm = input("\nProceed with cleanup? [y/N]: ")
    if confirm.lower() == 'y':
        cleanup_project()
    else:
        print("Cleanup cancelled.")