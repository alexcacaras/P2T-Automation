from __future__ import annotations
#post_refresh_automation_helpers.py
#
# Helper utilities for Oracle Fusion UI automation with built-in resilience.
# Provides a safety wrapper system that allows automation to continue running
# even when individual tasks fail.
import os
import datetime
import pathlib # For cross-platform file path handling
import shutil # For recursive folder deletion
import time  # For timestamp calculations
import traceback  # For printing full error stack traces
from contextlib import suppress # Clean way to ignore exceptions without try/except


# =====================================================
# v1.0.2 CHANGE NOTES
# =====================================================
# Screenshot routing improvement:
#   Problem:
#       Sometimes screenshots from one task appeared in another task's folder.
#       Example: Task 16 screenshots showing up inside Task 17 folder.
#
#   Root Cause:
#       screenshot() previously only relied on the global CURRENT_TASK_DIR.
#       If the global state moved to the next task, later screenshots could land
#       in the wrong folder.
#
#   Fix:
#       1) Added CURRENT_TASK_NAME global tracker
#       2) Added optional task_name override to screenshot()
#       3) Wrapper screenshots now force correct task folder using task_name=task_name
#       4) Added more meaningful automatic labels:
#            - BEFORE_SUCCESS
#            - SUCCESS
#            - STUCK
#            - FAILED
#
# IMPORTANT:
#   Soft-fail behavior is preserved.
#   If a task fails, automation still recovers to home and continues.


# 1. Global tracker for the 1:1 Task Folder
# We need screenshot() to know which task is currently running without passing
# task_name through every function call. This global is updated by 
# set_current_task() before each task runs.
#
# Alternative considered: Pass task_name to every screenshot() call → too repetitive. Can still put after each step screenshot(page) to add custom screenshots
#
# v1.0.2:
# Also track CURRENT_TASK_NAME so wrapper-level screenshots can explicitly route
# to the correct folder even if global state becomes stale later.
CURRENT_TASK_NAME = "General"
CURRENT_TASK_DIR = pathlib.Path("screenshots/General")

def clean_old_screenshots(days=7):
    """Deletes screenshot folders older than 'days'.
    Automation runs generate hundreds of screenshots. Without cleanup,
    the screenshots/ directory would grow unbounded and fill the disk. No storage/ less storage = poor performance

    Deletes entire folders (by task name) rather than individual files.
        Rationale:
        - Simpler than tracking individual file ages
        - Keeps related screenshots together until all are deleted as a unit
        - Faster (one stat() call per folder vs per file)
    DESIGN DECISION - Silent Failure:
        Uses try/except to ignore deletion errors (file locked, permission denied).
        Don't want cleanup to break the automation if a file is
        temporarily locked by antivirus or backup software.
    """
    base_dir = pathlib.Path("screenshots")
    # Early return if screenshots directory doesn't exist yet (first run)
    if not base_dir.exists():
        return

    now = time.time()# Current time as Unix timestamp
    threshold = now - (days * 86400) # 86400 seconds in a day
    # Iterate through all folders in screenshots
    for folder in base_dir.iterdir():
        # Check folder's last modification time
        if folder.is_dir():
            if folder.stat().st_mtime < threshold:
                try:
                    shutil.rmtree(folder) # Delete entire folder recursively = delete everything inside including subfolder and contents
                    print(f" [Cleaner] Deleted old folder: {folder.name}")
                except Exception:
                    # Silently ignore errors - don't break automation over cleanup
                    pass

def set_current_task(task_name):
    """Updates the folder path for the current task being run.
    Each task gets its own folder (e.g., screenshots/Task_12_Remove_Emails/)
        so when debugging failures, you can quickly find all screenshots for
        that specific task without sifting through hundreds of files.
    Call clean_old_screenshots() here rather than once at startup.
        This ensures cleanup happens even if the script runs multiple times
        per day, and spreads the cleanup cost across the run.
    Task names like "Task 12 — Remove Emails" contain characters that are
        invalid in folder names (em dash, special chars, spaces cause issues).
        We strip to alphanumeric + safe chars and replace spaces with underscores.
        
    v1.0.2:
        Also updates CURRENT_TASK_NAME for explicit screenshot routing.
    """
    global CURRENT_TASK_NAME, CURRENT_TASK_DIR # Allows us to modify the global variables
    clean_old_screenshots(days=7) # Clean up old screenshots before starting new task, choose the days, picked 7 for 1 week can be changed

    # Store raw task name too (v1.0.2)
    CURRENT_TASK_NAME = task_name

    # Sanitize task name for use as folder name
    # Keep: letters, numbers, dots, underscores, hyphens, spaces
    # Remove: em dash (—), quotes, slashes, etc.
    clean_name = "".join(x for x in task_name if x.isalnum() or x in "._- ").replace(" ", "_")
    # Build the folder path: screenshots/Task_Name
    CURRENT_TASK_DIR = pathlib.Path("screenshots") / clean_name
     # Create the folder if it doesn't exist
    # parents=True: also create 'screenshots/' if it doesn't exist
    # exist_ok=True: don't error if folder already exists (idempotent)
    CURRENT_TASK_DIR.mkdir(parents=True, exist_ok=True)

def screenshot(page, label="step", task_name: str | None = None):
    """
    Saves a screenshot in the current task's specific folder.
    Using datetime instead of sequential numbers (img1.png, img2.png) ensures:
        1. Files sort chronologically in file explorer
        2. No collision risk if script runs multiple times
        3. Easy to correlate with log timestamps
    
    Filename Format:
        Format: YYYY-MM-DD_HH-MM-SS_label.png
        Example: 2026-02-11_14-30-45_SUCCESS.png
    Uses hyphens instead of colons (Windows doesn't allow : in filenames)
        Includes label for quick identification (SUCCESS, FAILED, step, etc.)

    v1.0.2:
        Added optional task_name override.
        This allows wrapper-level screenshots to force correct task folder,
        even if CURRENT_TASK_DIR later changes.

    USAGE:
        screenshot(page)                                # Generic step capture can call this function after any step you'd like for more screenshots in Ui_Automation.py
        screenshot(page, "SUCCESS")                     # Called automatically on task success
        screenshot(page, "FAILED")                      # Called automatically on task failure
        screenshot(page, "before_save")                 # Manual debugging point
        screenshot(page, "STUCK", task_name=task_name)  # Explicit task routing
    """
    target_dir = CURRENT_TASK_DIR

    # v1.0.2 explicit override for correct folder routing
    if task_name:
        clean_name = "".join(x for x in task_name if x.isalnum() or x in "._- ").replace(" ", "_")
        target_dir = pathlib.Path("screenshots") / clean_name
        target_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S") #timestamp format
    filename = target_dir / f"{ts}_{label}.png" #build filename 
    page.screenshot(path=str(filename)) #capture screenshot (playwright helps handle the capture)
    # Log where it was saved (indentation groups it with task output)
    print(f"   [Shot] Saved to {filename}")

def recover_to_home(page, HOME_URL, PAUSE=3500, reason=""):
    """
    Hard reset to HOME_URL. Never raises.
    The reason I made this function to use in the Automation process was because when running many times and testing:
        1)the code would go through each task one after another if it failed somewhere then the code would get stuck and crash 
        this made it harder to run the code as to get through the whole thing I would have to comment each section out that failed and rerun, now if it fails
        it will move to nexxt step by automatically going to home page.
        2)sometimes the code would fail due to external factors, e.g wifi drop, so now if something happens the code won't get stuck and crash but move to next step.
        This is the case also if say the code somehow missed clicked even when typically in that task it doesn't
        3) ensure we at least can run all the tasks that would work on first run, so if something were to happen to cause task to fail the code wll at least finish the rest
        The tasks if skipped are logged and printed.
    ----------------DESIGN DECISION (extra)------------------------
     Never Raises:
        Uses contextlib.suppress to swallow ALL exceptions.
        This is the "last resort" recovery mechanism. If even THIS fails
        (network down, browser crashed), we don't want to raise an exception
        because there's nothing left to catch it. Better to log and continue.
    
    Domcontentloaded vs networkidle:
        Uses wait_until="domcontentloaded" instead of "networkidle" because
        Oracle Fusion NEVER reaches true networkidle (constant AJAX polling,
        analytics, session keepalives). domcontentloaded is "good enough" -
        the main HTML is loaded and we can interact with the page.
    
    3500ms PAUSE After Navigation:
        Even after domcontentloaded fires, Oracle Fusion needs extra time for:
        - JavaScript initialization (React/Angular bootstrapping)
        - AJAX requests to populate menus
        - Session validation
        
        3500ms (3.5 seconds) is empirically determined to be enough.
    """
    print(f"[RECOVER] {reason}")
    # suppress(Exception) = try/except that swallows ALL exceptions
    # Ensures recovery NEVER crashes, even if navigation fails
    with suppress(Exception):
        # Navigate to home URL
        # wait_until="domcontentloaded": Wait for HTML (not full networkidle)
        # timeout=60000: Give up after 60 seconds (milliseconds) can change the timeout and pause amounts if wanted anywhere in code
        page.goto(HOME_URL, wait_until="domcontentloaded", timeout=60000)
        # Additional pause for JavaScript initialization and AJAX
        #AJAX = Loading data in the background without refreshing the page
        page.wait_for_timeout(PAUSE)

def run_task_safe(task_name, task_fn, page, HOME_URL, PAUSE=3500, max_retries=1, **kwargs):
    """
    Crash-proof wrapper with optional retry + AI healer integration.
    
    max_retries: How many times to attempt the task total.
        1 = no retry (current default, backward compatible)
        2 = try once, retry once on failure
        3 = try once, retry twice on failure
    
    AI HEALER INTEGRATION:
        When AI_HEALER_ENABLED=true in .env:
        - On failure, AI analyzes the screenshot + DOM before retry
        - AI attempts a fix (click the right element, dismiss dialog, etc.)
        - If AI fix works, task continues without needing a full retry
        - If AI fix fails, normal retry system kicks in
        - AI gets another chance on each retry attempt
    
    On retry, passes is_retry=True to task functions that accept it.
    This lets destructive tasks (Task 3 row deletion, Task 16 row deletion)
    skip already-completed delete steps on retry.
    
    Tasks that don't accept is_retry are unaffected — the parameter is
    automatically stripped before calling them.
    """
    import inspect

    # Import AI healer (lazy — only when needed)
    healer = None
    try:
        from ai_healer import get_healer
        healer = get_healer()
    except ImportError:
        pass  # ai_healer.py not present — no AI features
    except Exception:
        pass  # ollama not installed or other issue — continue without AI
    
    print(f"\n===== {task_name} START =====")
    if healer and healer.enabled:
        print(f"  [AI Healer] Active — will analyze failures with {healer.model}")
    set_current_task(task_name)
    
    for attempt in range(1, max_retries + 1):
        try:
            task_kwargs = dict(kwargs)
            
            if attempt > 1:
                print(f"  [RETRY {attempt}/{max_retries}] {task_name}")
                task_kwargs["is_retry"] = True
                recover_to_home(page, HOME_URL, PAUSE=PAUSE, reason=f"{task_name} retry attempt {attempt}")
            
            # Only pass is_retry if the task function accepts it
            if "is_retry" in task_kwargs:
                sig = inspect.signature(task_fn)
                if "is_retry" not in sig.parameters and "kwargs" not in str(sig):
                    task_kwargs.pop("is_retry")
            
            task_fn(page, **task_kwargs)
            
            screenshot(page, "BEFORE_SUCCESS", task_name=task_name)
            screenshot(page, "SUCCESS", task_name=task_name)
            print(f"===== {task_name} DONE =====")
            return  # success, exit
            
        except Exception as e:
            screenshot(page, "STUCK", task_name=task_name)
            screenshot(page, "FAILED", task_name=task_name)
            print(f"!!!!! {task_name} FAILED (attempt {attempt}/{max_retries}): {e}")
            traceback.print_exc()
            
            # ── AI Healer: try to fix before retry ──
            if healer and healer.enabled:
                print(f"\n[AI Healer] Analyzing failure for {task_name}...")
                for ai_attempt in range(1, healer.max_retries + 1):
                    fixed = healer.attempt_fix(
                        page=page,
                        task_name=task_name,
                        failed_action=f"{task_name} (attempt {attempt}/{max_retries})",
                        error_message=str(e)[:300]
                    )
                    if fixed:
                        print(f"[AI Healer] Fix worked on AI attempt {ai_attempt}! Continuing task...")
                        # AI fixed the immediate issue — try to continue the task
                        # by letting the retry loop handle it with a fresh attempt
                        break
                    elif ai_attempt < healer.max_retries:
                        print(f"[AI Healer] Fix attempt {ai_attempt} failed, trying again...")
            
            if attempt < max_retries:
                print(f"  [RETRY] Will retry {task_name}...")
                recover_to_home(page, HOME_URL, PAUSE=PAUSE, reason=f"{task_name} failed -> retry")
                continue
            
            # Final attempt failed — recover and move on
            recover_to_home(page, HOME_URL, PAUSE=PAUSE, reason=f"{task_name} failed -> reset to Home")
            print(f"===== {task_name} SKIPPED (continued) =====")

 
def robust_click(page, locator, *, label="", attempts=4, timeout=15000, settle_ms=2000):
    """Click an element Oracle may render slowly.

    Waits for visibility, then clicks, retrying a few times with an escalating
    settle between attempts. Re-raises the last error if every attempt fails so
    the caller still sees a real failure instead of a silent skip.
    """
    last_err = None
    for i in range(1, attempts + 1):
        try:
            locator.wait_for(state="visible", timeout=timeout)
            locator.click(timeout=timeout)
            return True
        except Exception as e:
            last_err = e
            print(f"[robust_click] {label or 'element'} not ready "
                  f"(attempt {i}/{attempts}): {type(e).__name__}")
            page.wait_for_timeout(settle_ms * i)  # 2s, 4s, 6s, 8s
    raise last_err