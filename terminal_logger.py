from __future__ import annotations
# terminal_logger.py
"""
SQLite-based terminal logger - absolutely crash-proof.
Writes every line to a database that auto-commits instantly.

The goal was to create a logger that would log whatever was printed to the terminal.
One problem I ran into was: OneDrive Interference
    -I got new laptop so the folder was stored in a onedriv folder when developing. 
    -Onedrive was really aggressive with deleting the log files if a crash (I was forcing crash for test purpose) happened.
    -Easy fix could have been just move folder off one drive but thought better should make workaround for it
    -Buffer issue where there is a wait to write to disk the logs so on crash it wouldn't save

The idea was to make the logger SQLite database version:
    - SQLite with autocommit (isolation_level=None) writes INSTANTLY to disk
    - Every single line is committed immediately (no buffering)
    - Database files are more resistant to OneDrive's cleanup
    - 100% crash-proof - even Ctrl+C or force-close preserves all logs

As a workaround to the onedrive issue I have write to desktop instead of project folder:
    - Desktop folder (outside OneDrive sync) doesn't have aggressive cleanup
    - Files survive even on crashes
    - Can be moved back to project folder after moving out of OneDrive
    -Could have just moved project off onedrive butdidn't feel like waiting for long time for files to move

WHAT THIS FILE DOES:
    1. Hijacks sys.stdout and sys.stderr (every satandard outpur and error)
    2. Writes every print() statement to both:
       - Terminal (so you see output in real-time)
       - SQLite database (crash-proof storage)
    3. Provides CLI tools to view/export logs later

I Import the file into the Ui_Automation.py then
Everything prints to terminal AND logs automatically!.
    print("This goes to both console and database")
    
    Later, view the log ex:
    python terminal_logger.py C:\\Users\\...\\Desktop\\ui_automation_logs\\ui_automation_2026-02-11_17-24-46.db
    
    Or export to text file ex:
    python terminal_logger.py C:\\Users\\...\\Desktop\\ui_automation_logs\\ui_automation_2026-02-11_17-24-46.db export
This one better documented becuase I did recently to the date Feb 11th 2026.
Another reason for SQLite database is because for an at home project I do where I have created an "AI" or at least made my code 
program self-learning, I used SQLite database for a part of logging system.


"""
import sqlite3 # For crash-proof database logging
import sys  # For hijacking stdout/stderr
import os # For file size checks
from pathlib import Path # For cross-platform file paths
from datetime import datetime # For timestamps
from typing import TextIO # Type hint for file-like objects
import atexit
_db_conn = None # SQLite connection - stays open entire run
_log_name = None # Base name for log file (e.g., "ui_automation")
_original_stdout = None # Original sys.stdout (before code hijack it)
_original_stderr = None # Original sys.stderr (before code hijack it)


class SQLiteTeeLogger:
    """Captures stdout/stderr and writes to both console and SQLite.
    TEE becausethe Unix 'tee' command which splits output to multiple destinations.
    Code takes one input stream and splits it into two outputs.
    1. Terminal 
    2. SQLite database
    When Python calls write everytime something is printed we hijack call and send to both destinations
    """
    def __init__(self, terminal: TextIO, db_conn):
        """
        Initialize the Tee logger.
        
        Args:
            terminal: Original stdout or stderr (to keep console output)
            db_conn: SQLite database connection (for logging)
        """
        self.terminal = terminal # Keep reference to original stream
        self.db = db_conn # Keep reference to database
    
    def write(self, message: str):
        """Write to both terminal and SQLite.
        -Only logs non-empty messages to avoid clutter
        -IF database wtrite fails I still want terminal ouput to work and not crash entire system over logging.
        """
        # Always write to terminal (real-time output)
        self.terminal.write(message)
        if self.db and message.strip():  # Only log non-empty messages
            try:
                 # Insert message into database with timestamp
                # Uses ISO format timestamp for easy sorting and readability
                self.db.execute(
                    "INSERT INTO logs (timestamp, message) VALUES (?, ?)",
                    (datetime.now().isoformat(), message.rstrip('\n'))
                )
            except:
                # Silently ignore database errors - don't crash over logging
                pass
    
    def flush(self):
        """Flush terminal.
        Python's print() sometimes calls flush() to force output to appear immediately. Implement so logger looks like real file object
        since python is expecting sys.stdout to be real object file the logger has to pretend to be one.
        The code only flushes terminal, not database. Database uses autocommit, so it flushes automatically after ever insert.
        """
        self.terminal.flush()
    
    def isatty(self):
        """Check if connected to terminal.
        Some  Python libraries check isatty() to decide whether to use coloured output or progress bars.
        Delegate to original terminal to preserve behaviour.

        Returns:
            True if output is going to a real terminal, False if redirected to file
        """
        return self.terminal.isatty()


def setup_terminal_logging(log_name: str = "ui_automation") -> Path:
    """
    Set up SQLite-based logging that captures all stdout/stderr.
    100% crash-proof - every line commits to disk immediately.

    WHAT THIS DOES:
        1. Creates a SQLite database for logging
        2. Hijacks sys.stdout and sys.stderr
        3. Every print() now goes to BOTH terminal AND database
        4. Returns the path to the created log file
    WHY DESKTOP LOCATION?:
        Current: logs_dir = Path.home() / "Desktop" / "ui_automation_logs"

    Because got new laptop and folder was now on onedrive, onedrive aggressive file cleanup on crashes.
    Desktop safe way to save log files from forced crash.
    TO MOVE BACK TO PROJECT FOLDER:
        After moving project out of OneDrive, change logs_dir = Path.home() / "Desktop" / "ui_automation_logs" to:
            logs_dir = Path("logs")

    DESIGN DECISION
        isolation_level=None means "autocommit mode"
        - Every INSERT commits to disk IMMEDIATELY
        - No buffering, no waiting
        - Even if script crashes 1 millisecond later, the log is saved
        
        Without this: Database buffers writes in memory, lost on crash
        With this: Every line is permanent instantly

        Database table structure:
        - id: Auto-increment, ensures correct order if timestamps collide
        - timestamp: ISO format, human-readable and sortable
        - message: Stores the actual print() output
    
        sys.__stdout__ vs sys.stdout:
        - sys.__stdout__: Original terminal (never changes)
        - sys.stdout: What print() uses (I am replacing it)
        - Pass sys.__stdout__ to logger so it always has real terminal access
    """
    if os.environ.get("P2T_DASHBOARD_MODE") == "1":
        # Dashboard mode: save SQLite log but don't hijack stdout
        # (stdout flows to pipe for live dashboard streaming)
        global _db_conn, _log_name
        _log_name = log_name
        logs_dir = Path.home() / "Desktop" / "ui_automation_logs"
        logs_dir.mkdir(exist_ok=True, parents=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        db_path = logs_dir / f"{log_name}_{timestamp}.db"
        _db_conn = sqlite3.connect(str(db_path), isolation_level=None)
        _db_conn.execute("""
            CREATE TABLE logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                message TEXT
            )
        """)
        # Write to SQLite on every print without hijacking stdout
        
        _original_write = sys.stdout.write
        def _dashboard_tee(msg):
            try:
                _original_write(msg)
            except UnicodeEncodeError:
                _original_write(msg.encode('ascii', 'replace').decode('ascii'))
            if _db_conn and msg.strip():
                try:
                    _db_conn.execute(
                        "INSERT INTO logs (timestamp, message) VALUES (?, ?)",
                        (datetime.now().isoformat(), msg.rstrip('\n'))
                    )
                except:
                    pass
            return len(msg)
        sys.stdout.write = _dashboard_tee
        sys.stderr.write = _dashboard_tee
        return db_path
    global _original_stdout, _original_stderr
    _log_name = log_name
    
    # Create logs directory - CHANGE THIS LINE TO DESKTOP FOR TESTING
    logs_dir = Path.home() / "Desktop" / "ui_automation_logs"  # Changed from Path("logs")
    logs_dir.mkdir(exist_ok=True, parents=True)
    
    # Create timestamped database
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    db_path = logs_dir / f"{log_name}_{timestamp}.db"
    
    # SQLite with autocommit (isolation_level=None) - instant disk writes
    _db_conn = sqlite3.connect(str(db_path), isolation_level=None)
     # Create table structure for log storage
    _db_conn.execute("""
        CREATE TABLE logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            message TEXT
        )
    """)
    
    # Write header to log
    _db_conn.execute(
        "INSERT INTO logs (timestamp, message) VALUES (?, ?)",
        (datetime.now().isoformat(), "=" * 80)
    )
    _db_conn.execute(
        "INSERT INTO logs (timestamp, message) VALUES (?, ?)",
        (datetime.now().isoformat(), f"UI Automation Log - Started at {timestamp}")
    )
    _db_conn.execute(
        "INSERT INTO logs (timestamp, message) VALUES (?, ?)",
        (datetime.now().isoformat(), "=" * 80)
    )
    
    # Redirect stdout and stderr
    #save original
    _original_stdout = sys.stdout
    _original_stderr = sys.stderr
    #hijack
    sys.stdout = SQLiteTeeLogger(sys.__stdout__, _db_conn)
    sys.stderr = SQLiteTeeLogger(sys.__stderr__, _db_conn)
    #print instructions(through the logger now)
    print(f"[Logging] Output being logged to: {db_path}")
    print(f"[Logging] To view: python terminal_logger.py {db_path}")
    print(f"[Logging] To export: python terminal_logger.py {db_path} export")
    
    # DEBUG INFO (can be removed after confirming logging works) but didn't feel like removing after maybe useful in future
    print(f"[DEBUG] Full absolute path: {db_path.absolute()}")
    print(f"[DEBUG] File exists now? {db_path.exists()}")
    print(f"[DEBUG] File size: {os.path.getsize(db_path) if db_path.exists() else 'N/A'} bytes")
    
    return db_path


def cleanup_old_logs(days: int = 7, log_pattern: str = "ui_automation_*.db"):
    """Delete SQLite log files older than specified days.
    The purpose is because of storage space, I don't want to take up too much space, the log is meant to check after runs to see what went
    wrong if anything did. This auto-cleaner is meant to remove old logs at startup, can change the int=7 to any amount of days as preferred.
    I am using "ui_automation_*.db" because we are using SQLite databases
    If you want to move back toproject folder like previously then change logs_dir = Path.home() / "Desktop" / "ui_automation_logs" to:
     logs_dir = Path("logs")
    
    """
    import time
    
    # Update to match new location
    logs_dir = Path.home() / "Desktop" / "ui_automation_logs"  #CHANGE THIS TO Path("logs") AFTER MOVING OUT OF ONEDRIVE
    # Early return if log directory doesn't exist, don't waste time
    if not logs_dir.exists():
        return
    
    now = time.time()
    threshold = now - (days * 86400) # Calculate cutoff time
    
    deleted_count = 0
     # Find all .db files matching the pattern
    for log_file in logs_dir.glob(log_pattern):
        if log_file.is_file() and log_file.stat().st_mtime < threshold:
            try:
                log_file.unlink()
                # Delete the file
                deleted_count += 1
                print(f"[Cleanup] Deleted old log: {log_file.name}")
            except Exception as e:
                # Don't crash if we can't delete (file in use, permissions, etc.)
                print(f"[Cleanup] Could not delete {log_file.name}: {e}")
    
    if deleted_count > 0:
        print(f"[Cleanup] Removed {deleted_count} old log file(s)")


def export_to_text(db_path: Path) -> Path:
    """Export SQLite log to readable text file.
    WHY THIS EXISTS:
        SQLite databases can't be read directly in a text editor.
        This converts the database to a plain text file for easy reading.
    WHAT IT DOES:
        1. Opens the SQLite database
        2. Reads all messages in order
        3. Writes them to a .log text file
        4. Returns the path to the text file
    
    DESIGN DECISION - with_suffix('.log'):
        Takes the database filename and changes the extension:
        ui_automation_2026-02-11_17-24-46.db → ui_automation_2026-02-11_17-24-46.log
        
        This keeps the same name so it's easy to match database to text file.
    
    USAGE:
        # From command line in terminal:
        python terminal_logger.py path/to/log.db export
        
        # From Python code:
        from terminal_logger import export_to_text
        export_to_text(Path("ui_automation_2026-02-11_17-24-46.db"))
    """
    # Open the SQLite database
    conn = sqlite3.connect(str(db_path))
    
    # Create text file with same name
    txt_path = db_path.with_suffix('.log')
    # Write all log messages to text file
    with open(txt_path, "w", encoding="utf-8") as f:
        # SELECT message FROM logs ORDER BY id
        # - Gets all messages
        # - ORDER BY id ensures correct chronological order
        for row in conn.execute("SELECT message FROM logs ORDER BY id"):
            f.write(row[0] + "\n") # row[0] is the message text
    
    conn.close()
    print(f"[Export] Created: {txt_path}")
    return txt_path

#-----------------------------
# CLI tool to view/export logs
#-----------------------------
#Runs only when you execute file directly:
#python terminal_logger.py <arguments>= could be path/to/file.db or path/to/file.db export
#
# Does NOT run when you import the module:
# from terminal_logger import setup_terminal_logging
if __name__ == "__main__":
    """
    Commandline interface for viewing and exporting log databases.
    USAGE:
        View log in terminal:
            python terminal_logger.py path/to/ui_automation_2026-02-11_17-24-46.db
        
        Export log to text file:
            python terminal_logger.py path/to/ui_automation_2026-02-11_17-24-46.db export
    EXTRA INFO: I import sys as _sys here to avoid confusion with the 'sys' module
        already imported at the top of the file. This makes it clear the
        use is for command-line arguments (_sys.argv), not for stdout/stderr.
    """
    import sys as _sys
    # Check if user provided the database path argument
    if len(_sys.argv) < 2:
        # No arguments provided - show usage instructions
        print("Usage:")
        print("  python terminal_logger.py <log.db>          # View in console")
        print("  python terminal_logger.py <log.db> export   # Export to .log file")
        _sys.exit(1)
    # Get the database path from command line
    # _sys.argv[0] = "terminal_logger.py" (script name)
    # _sys.argv[1] = path to database file
    db_path = Path(_sys.argv[1])
    # Verify the file exists
    if not db_path.exists():
        print(f"Error: {db_path} not found")
        _sys.exit(1)
    # Check if user wants to export (second argument = "export")
    if len(_sys.argv) == 3 and _sys.argv[2] == "export":
        # Export mode: Convert database to text file
        export_to_text(db_path)
    else:
        # Print to console
        conn = sqlite3.connect(str(db_path))
        # SELECT timestamp, message FROM logs ORDER BY id
        for row in conn.execute("SELECT timestamp, message FROM logs ORDER BY id"):
            print(f"[{row[0]}] {row[1]}")
        conn.close()