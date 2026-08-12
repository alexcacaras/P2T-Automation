from __future__ import annotations
"""
Export SQLite terminal logs to readable text files.

Usage in terminal commands:
    python export_logs.py <log_file.db>                    # Export single file
    python export_logs.py <log_file.db> <output.txt>       # Export with custom name
    python export_logs.py --all                            # Export all logs in directory
    python export_logs.py --recent                         # Export most recent log
    python export_logs.py --help

    I made this because wanted easier way to export logs. Yes it is easy to just type the command prompt I mentioend in terminal_logger but this is more easy to remember for user.
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime


def export_log_to_text(db_path: Path, output_path: Path = None):
    """Export SQLite log to readable text file"""
    
    if not db_path.exists():
        print(f" Error: File not found: {db_path}")
        return False
    
    # Default output name: same as input but .txt
    if output_path is None:
        output_path = db_path.with_suffix('.txt')
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Get log entries
        cursor.execute("SELECT timestamp, message FROM logs ORDER BY id")
        rows = cursor.fetchall()
        
        if not rows:
            print(f" Warning: No log entries found in {db_path.name}")
            conn.close()
            return False
        
        # Write to text file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write(f"LOG FILE: {db_path.name}\n")
            f.write(f"EXPORTED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"TOTAL LINES: {len(rows)}\n")
            f.write("=" * 80 + "\n\n")
            
            for timestamp, message in rows:
                f.write(f"[{timestamp}] {message}\n")
            
            f.write("\n" + "=" * 80 + "\n")
            f.write("END OF LOG\n")
            f.write("=" * 80 + "\n")
        
        conn.close()
        
        # Get file size
        size_kb = output_path.stat().st_size / 1024
        
        print(f" Exported: {db_path.name}")
        print(f"   → {output_path}")
        print(f"   Lines: {len(rows)} | Size: {size_kb:.2f} KB")
        
        return True
        
    except Exception as e:
        print(f" Error exporting {db_path.name}: {e}")
        return False


def find_logs_directory():
    """Find the logs directory (Desktop or project folder)"""
    
    # Check Desktop first
    desktop_logs = Path.home() / "Desktop" / "ui_automation_logs"
    if desktop_logs.exists():
        return desktop_logs
    
    # Check project logs folder
    project_logs = Path("logs")
    if project_logs.exists():
        return project_logs
    
    # Check current directory
    current_dir = Path(".")
    db_files = list(current_dir.glob("*.db"))
    if db_files:
        return current_dir
    
    return None


def export_all_logs(logs_dir: Path = None):
    """Export all log files in directory"""
    
    if logs_dir is None:
        logs_dir = find_logs_directory()
    
    if logs_dir is None:
        print(" Could not find logs directory")
        print("   Searched:")
        print(f"   - {Path.home() / 'Desktop' / 'ui_automation_logs'}")
        print(f"   - {Path('logs').absolute()}")
        return
    
    db_files = sorted(logs_dir.glob("ui_automation_*.db"), reverse=True)
    
    if not db_files:
        print(f" No log files found in {logs_dir}")
        return
    
    print(f"Found {len(db_files)} log file(s) in {logs_dir}")
    print("=" * 60)
    
    success_count = 0
    for db_file in db_files:
        if export_log_to_text(db_file):
            success_count += 1
        print()
    
    print("=" * 60)
    print(f" Successfully exported {success_count}/{len(db_files)} log files")


def export_recent_log():
    """Export the most recent log file"""
    
    logs_dir = find_logs_directory()
    
    if logs_dir is None:
        print(" Could not find logs directory")
        return
    
    db_files = sorted(logs_dir.glob("ui_automation_*.db"), reverse=True)
    
    if not db_files:
        print(f" No log files found in {logs_dir}")
        return
    
    recent = db_files[0]
    print(f"Most recent log: {recent.name}")
    print("=" * 60)
    export_log_to_text(recent)


def main():
    if len(sys.argv) == 1:
        print(__doc__)
        return
    
    command = sys.argv[1]
    
    if command == "--all":
        export_all_logs()
    
    elif command == "--recent":
        export_recent_log()
    
    elif command in ("-h", "--help"):
        print(__doc__)
    
    else:
        # Export specific file
        db_path = Path(command)
        
        if not db_path.exists():
            print(f" File not found: {db_path}")
            print("\nTry:")
            print("  python export_logs.py --all      # Export all logs")
            print("  python export_logs.py --recent   # Export most recent")
            return
        
        # Check for custom output name
        if len(sys.argv) > 2:
            output_path = Path(sys.argv[2])
        else:
            output_path = None
        
        export_log_to_text(db_path, output_path)


if __name__ == "__main__":
    main()

