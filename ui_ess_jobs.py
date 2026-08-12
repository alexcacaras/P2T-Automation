# ui_ess_jobs.py
#
# UI-based ESS job runner driven by Excel (UI_ESS_jobs.xlsx).
# This module expects an already-logged-in Playwright Page.
#
# You will call: run_ui_ess_jobs(page) from convert_to_defined.run()
#
# Excel columns (confirmed / expected):
#   Display Name
#   Index Name to Reingest
#   Chart of Accounts
#   Accounting Calendar
#   Starting Period
#   icalstring
#
# DRY RUN:
#   Set DRY_UI=true in env to prevent submitting jobs.
#   Navigation + field changes still run, but Submit/OK are skipped.
# ============================================================================
# UPDATE 1.0.1 - SMART RETRY INTEGRATION (March 2026)
# ============================================================================

#CHANGES IN VERSION 1.0.1:
 #   - Integrated with REST API status tracker (job_status_tracker.json)
 #   - Smart retry: Only retries jobs that failed in REST API
  #  - Display name matching for accurate job identification
 #   - ACL job status checking with hardcoded UI fallback
# - ADDED ONE ESSJOB FOR INGEST TO OSCS now 1-37 instead of 1-36 index and 39-44 and 40-44
    
#HOW IT WORKS:
#    1. Reads job_status_tracker.json to get failed job names
#    2. Loads Excel file and matches failed jobs by Display Name
#    3. Skips jobs that succeeded in REST API
#    4. Retries only failed/timed-out jobs via UI automation
 #   5. Checks ACL job status and runs hardcoded UI if needed
    
#DEPENDENCIES:
  #  - Requires job_status_tracker.json from REST API (RESTAPI_ESS/main.py)
 #   - Expects Excel with Display Name column matching REST API job names

# ============================================================================
# END UPDATE 1.0.1
# ============================================================================
# ============================================================================
# UPDATE 1.0.3 - UI RETRY FIXES + GLASS PANE HANDLING (March 2026)
# ============================================================================
 
# CHANGES IN VERSION 1.0.3:
#
#   RETRY MATCHING:
#   - run_ui_ess_jobs() now matches failed jobs by excel_row number from JSON
#     instead of by Display Name. This is more reliable — no name matching
#     ambiguity, works regardless of jobDefinitionName vs Display Name in JSON.
#     I did this because it just makes more sense and code won't run wrong process
#
#   ACL JOB HANDLING:
#   - ACL jobs (Compute Users ACL, Compute Users ACL by Event, Compute Users
#     with Large ACL) are now explicitly skipped in the retry loop with a
#     printed message. These always fail via UI automation due to Oracle's
#     LOV dialog glass pane issue. I didn't try to fix them if it fails API then run manually.
#   - Added manual action warning at end of summary: if acl_jobs_status
#     shows completed=False, prints clear instruction to run ACL jobs manually
#     in Oracle Fusion.
#
#   GLASS PANE FIX:
#   - Added wait_for_glass_pane_gone() helper — waits for AFModalGlassPane
#     overlay to disappear before clicking. Oracle ADF shows this overlay
#     during processing; clicking while visible causes silent failures.
#   - open_schedule_new_process() calls wait_for_glass_pane_gone() first so
#     the button is clickable after the previous job finishes.
#   - submit_job_simple() calls wait_for_glass_pane_gone() before Submit,
#     and all three clicks (Submit, OK, OK) use timeout=90000 (90s) since
#     Oracle can take ~60s to process a submission.
#
#   RECOVERY ON FAILURE:
#   - When a row fails, recovery now presses Escape twice to dismiss any
#     open LOV/search dialogs (keyboard events bypass the glass pane),
#     then waits for glass pane + 5s before attempting the next row.
#     Fixes cascade failures where rows 39-42 would all fail after row 38
#     left a dialog open.
 
# ============================================================================
# END UPDATE 1.0.3
# ============================================================================
from __future__ import annotations # Enable postponed evaluation of type annotations

import datetime as dt
import os
import re
from typing import Dict, Tuple

import math
import pandas as pd
from playwright.sync_api import Page, TimeoutError as PWTimeout
from pathlib import Path
from post_refresh_automation_helpers import robust_click
#Core dependencies:
# - pandas: Read Excel-driven job configurations
# - playwright: Browser automation for Oracle Fusion UI interactions
# - pathlib: Cross-platform file path handling
# - datetime/re: Schedule parsing and string matching

#-------------------------------------------------------
#Path Configuration
#-------------------------------------------------------
#--------------NEW UPDATE 1.0.1 SECTION------------------------------
# JSON status tracker from REST API
STATUS_FILE = Path(__file__).resolve().parent / "RESTAPI_ESS" / "job_status_tracker.json"

def load_failed_jobs():
    """
    Load list of jobs that failed in REST API.
    
    WHAT IT DOES:
        Reads job_status_tracker.json created by RESTAPI_ESS/main.py
        Returns status data including list of failed jobs to retry
    
    RETURNS:
        Dictionary with status data, or None if file doesn't exist
        
    STRUCTURE:
        {
            "total_jobs": 42,
            "successful": 38,
            "failed": 2,
            "timed_out": 2,
            "failed_jobs": [
                {"job_name": "Import Payables", "reason": "TIMEOUT_WAIT", ...},
                ...
            ],
            "acl_jobs_status": {
                "completed": False,
                "failed_acl_jobs": ["Compute Users ACL"]
            }
        }
    """
    if not STATUS_FILE.exists():
        print("  No status file found. Running all jobs from Excel.")
        return None
    
    try:
        import json
        with open(STATUS_FILE, 'r', encoding='utf-8') as f:
            status_data = json.load(f)
        
        print(f"\n{'='*60}")
        print(f" REST API STATUS LOADED")
        print(f"{'='*60}")
        print(f"Total jobs attempted: {status_data.get('total_jobs', 0)}")
        print(f"Successful: {status_data.get('successful', 0)}")
        print(f"Failed/Timed out: {len(status_data.get('failed_jobs', []))}")
        
        # ACL warning if critical jobs failed
        if not status_data.get("acl_jobs_status", {}).get("completed", True):
            print(f"\n{''*30}")
            print(f" CRITICAL: ACL JOBS FAILED IN REST API!")
            acl_failed = status_data.get("acl_jobs_status", {}).get("failed_acl_jobs", [])
            print(f"Failed ACL jobs: {acl_failed}")
            print(f"{''*30}\n")
        
        print(f"{'='*60}\n")
        
        return status_data
        
    except Exception as e:
        print(f" Error loading status file: {e}")
        import traceback
        traceback.print_exc()
        return None

# ui_ess_jobs.py is in post_refresh_automation/
# Excel is in the project root (one level up)
# Get the directory where ui_ess_jobs.py is located
PROJECT_ROOT = Path(__file__).resolve().parent  # ← Just .parent (not parents[1]!)

# Environment variable override (optional)
env_path = os.getenv("UI_ESS_EXCEL")
if env_path:
    EXCEL_PATH = Path(env_path)
else:
    # Path to Excel file - NO "P2T" folder in the middle!
    EXCEL_PATH = PROJECT_ROOT / "RESTAPI_ESS" / "scenarios" / "(client)P2T.xlsx" #"(client)P2T.xlsx" #change this for different excel

DRY_UI = os.getenv("DRY_UI", "false").lower() == "true"

# Debug output (temporary - remove after it works)
print(f"[DEBUG] PROJECT_ROOT = {PROJECT_ROOT}")
print(f"[DEBUG] EXCEL_PATH = {EXCEL_PATH}")
print(f"[DEBUG] File exists? {EXCEL_PATH.exists()}")

# ========== END NEW SECTION ==========


# ---------------------------------------------------------------------------
# Timing helper - Fusion is slow, so pause after each important step
# ---------------------------------------------------------------------------

DEFAULT_PAUSE_MS = 4000  # 4 seconds

def slow(page: Page, ms: int = DEFAULT_PAUSE_MS) -> None:
    """Global wait helper for UI steps.

Uses fixed timeouts instead of page load waits because Oracle Fusion:
- Triggers background AJAX that doesn't affect load/networkidle events
- Never reaches true 'networkidle' due to polling/analytics
- Renders dynamic elements after the page reports as "loaded"

Fixed waits ensure elements are fully interactive before the next action,
preventing "element not found" or "not clickable" errors.
"""
    page.wait_for_timeout(ms)
#defining the page wait function so we don't overrush the UI, have this instead of page load wait because


def wait_for_glass_pane_gone(page: Page, timeout_ms: int = 60000) -> None:
    """
    Wait for Oracle ADF's modal glass pane to disappear before interacting.

    WHY THIS EXISTS:
        Oracle ADF renders a <div class="AFModalGlassPane"> overlay while it is
        processing (saving params, loading a dialog, submitting a job, etc.).
        While visible it intercepts ALL pointer events, so clicks on Submit,
        Schedule New Process, Navigator etc. silently fail with:
            "AFModalGlassPane subtree intercepts pointer events"

    WHEN TO CALL:
        - Before clicking "Schedule New Process" (glass from previous job)
        - Before clicking "Submit" (glass from param loading / dialog open)
        - Before Navigator clicks that follow a job submission
    """
    try:
        page.wait_for_selector(
            "div.AFModalGlassPane",
            state="hidden",
            timeout=timeout_ms,
        )
    except PWTimeout:
        print(f"* wait_for_glass_pane_gone: glass pane still visible after {timeout_ms}ms — continuing anyway.")



# ---------------------------------------------------------------------------
# Safe Excel cell helper- helps to read the Excel file for the ESS jobs
# ---------------------------------------------------------------------------

def cell(row: Dict[str, object], key: str) -> str:
    """
    Safely get a string value from a row:
    - Treats NaN / None as ""
    - Strips whitespace
    - Converts numbers to string
    """
    val = row.get(key)

    # None → ""
    if val is None:
        return ""

    # Handle NaN (pandas uses float NaN for empty cells)
    if isinstance(val, float):
        if math.isnan(val):
            return ""
        # Non-NaN float → convert to string (e.g., 2025.0 -> "2025")
        if val.is_integer():
            return str(int(val))
        return str(val).strip()

    # Normal case: string or other types
    return str(val).strip()


# ---------------------------------------------------------------------------
# Helpers: icalstring parsing and date formatting
# ---------------------------------------------------------------------------

def parse_ical(ical: str) -> Tuple[str | None, int | None]:
    """Parse a simple iCal-like string from the Excel 'icalstring' column.
     Expected format: "FREQ=HOURLY;INTERVAL=15" or "FREQ=DAILY;INTERVAL=1"
     Uses manual parsing instead of a full iCal library because:
        We only need FREQ and INTERVAL, keep it simple.
    Returns:
        Tuple of (frequency, interval) where frequency is a string like
        "HOURLY", "DAILY", etc. and interval is an integer.
     """
    if not ical:
        return None, None

    freq = None
    interval = None
    parts = ical.split(";")
    kv = {}
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            kv[k.strip().upper()] = v.strip()

    freq = kv.get("FREQ")
    interval_str = kv.get("INTERVAL")
    if interval_str is not None:
        try:
            interval = int(interval_str)
        except ValueError:
            interval = None

    return freq, interval


def schedule_option_label(freq: str | None) -> str:
    """
    Map FREQ to the option text in the "Using a schedule" dropdown.

    Fusion combines HOURLY and MINUTELY into a single "Hourly/Minute" option,
    so both frequencies map to the same UI choice. The interval is then set
    separately in hours/minutes fields.
    
    Returns "Once" for None/empty or unrecognized frequencies (default behavior)
    """
    if not freq:
        return "Once"

    freq = freq.upper()
    if freq in ("HOURLY", "MINUTELY"):
        return "Hourly/Minute"
    if freq == "DAILY":
        return "Daily"
    if freq == "WEEKLY":
        return "Weekly"
    if freq == "MONTHLY":
        return "Monthly"
    if freq == "YEARLY":
        return "Yearly"

    return "Once"


def now_and_plus_one_year_strings() -> Tuple[str, str]:
    """
    Returns Start/End date strings formatted for Fusion:
      "MM/DD/YYYY hh:mm AM/PM" (e.g., "02/11/2026 03:45 PM")

      Uses current time + 1 year window to:
         Start jobs immediately upon creation
         If not set, it runs at current time and by the time click happens it pasts current time so job won't run. Must have end date later.
         Did plus 1 year because typically longer period for refreshes.
         Returns:
        Tuple of (start_date_string, end_date_string)
    """
    now = dt.datetime.now()
    one_year = now + dt.timedelta(days=365)
    fmt = "%m/%d/%Y %I:%M %p"
    return now.strftime(fmt), one_year.strftime(fmt)


# ---------------------------------------------------------------------------
# Generic UI helpers
# ---------------------------------------------------------------------------

def open_scheduled_processes(page: Page) -> None:
    """Navigator → Tools → Scheduled Processes.

    Attempts networkidle wait but gracefully continues on timeout since some
    Fusion tenants never reach stable state due to background polling.
    """
    robust_click(page, page.get_by_role("link", name="Navigator"), label="Navigator")
    slow(page)
    robust_click(page, page.get_by_title("Tools", exact=True).locator("div").nth(1), label="Tools tile")
    robust_click(page, page.get_by_role("link", name="Scheduled Processes"), label="Scheduled Processes")
    slow(page)
    #page.get_by_role("link", name="Navigator").click()
    #slow(page)
   #This line won't work if ran all together so say we skip the rest api file and run only UI then this line beneath comment should be commmented out
    #page.get_by_title("Tools", exact=True).locator("div").nth(1).click() #this line
    #slow(page)
    #page.get_by_role("link", name="Scheduled Processes").click()
    #slow(page)
    # Some tenants never reach true "networkidle" here; don't die on timeout.
    try:
        page.wait_for_load_state("networkidle", timeout=30000)
    except PWTimeout:
        print("* open_scheduled_processes: networkidle timeout ignored; continuing.")


def open_schedule_new_process(page: Page) -> None:
    """Click 'Schedule New Process' button and wait for dialog to open.

    Waits for AFModalGlassPane to clear first — after a previous job submits,
    Oracle ADF keeps the overlay up while it transitions. Clicking while the
    pane is visible causes: 'AFModalGlassPane subtree intercepts pointer events'.
    """
    wait_for_glass_pane_gone(page)  # clear any overlay from previous job
    page.get_by_role("button", name="Schedule New Process").click()
    slow(page)
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except PWTimeout:
        print("* open_schedule_new_process: networkidle timeout ignored; continuing.")


def select_process(page: Page, display_name: str) -> None:
    """
    In the 'Schedule New Process' popup, search for the job by Display Name
    and confirm it.

    Special-case handling:
      - "Compute Users ACL" has a unique UI pattern with a search grid (LOV)
        that requires clicking a cell, then two separate OK buttons:
        1. Inner dialog OK (to confirm LOV selection)
        2. Outer dialog OK (to close the Schedule New Process popup)
        
        Uses first() without exact=True because multiple cells may match the text,
        and nth(1) for the second OK button because it appears in the DOM before
        the main OK.

        Sometimes there will be issue with ESS jobs 37 and 42 in clicking right spot, this special case is meant to help with issue but the
        case is imperfect so still get errors sometimes, prefer to have ACL user jobs manually done
    """
    print(f"> Selecting process: {display_name}")
    name_upper = (display_name or "").strip().upper()

    # ----- Special-case: Compute Users ACL (grey job) -----
    if name_upper == "COMPUTE USERS ACL":
        combo = page.get_by_role("combobox", name="Name")
        combo.click()
        slow(page)
        combo.press("ControlOrMeta+a")
        slow(page)
        combo.fill("Compute Users ACL")
        slow(page)
        combo.press("Enter")
        slow(page)

        # ORIGINAL WORKING CELL CLICK — use first(), no exact=True,  multiple cells may match
        cell_loc = page.get_by_role("cell", name="Compute Users ACL")
        cell_loc.first.click()
        slow(page)

        #  Two-step OK button sequence for nested dialogs
        ok_btns = page.get_by_role("button", name="OK")
        if ok_btns.count() >= 2:
            ok_btns.nth(1).click()   # inner dialog OK
            slow(page)
            ok_btns.first.click()    # outer OK
            slow(page)
        else:
            ok_btns.first.click()
            slow(page)

        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except PWTimeout:
            pass

        return

    # ----- Generic path for all other jobs -----
    combo = page.get_by_role("combobox", name="Name")
    combo.click()
    slow(page)
    combo.press("ControlOrMeta+a")
    slow(page)
    combo.fill(display_name)
    slow(page)
    combo.press("Enter")
    slow(page)

    # If a result grid appears, click the matching cell
    # Some jobs auto-select after Enter, others show a grid requiring manual selection
    try:
        cells = page.get_by_role(
            "cell",
            name=re.compile(rf"^{re.escape(display_name)}$", re.I),
        )
        if cells.count() > 0:
            cells.first.click()
            slow(page)
    except Exception:
        # grid might not exist; some jobs auto-select
        pass

    # Handle OK in a non-strict, multi-OK-safe way
    # Different jobs have different dialog structures (single vs nested)
    ok_buttons = page.get_by_role("button", name="OK")
    count = ok_buttons.count()
    if count == 0:
        raise RuntimeError("Could not find any 'OK' button in Schedule New Process popup.")
    elif count == 1:
        ok_buttons.first.click()
        slow(page)
    else:
        # Multiple OK buttons present (likely nested dialogs)
        # Click second OK first (inner dialog), then first OK (outer dialog)
        # This order works for most multi-OK scenarios in Fusion
        ok_buttons.nth(1).click()
        slow(page)
        try:
            ok_buttons.first.click()
            slow(page)
        except Exception:
            # First OK might not be clickable if dialog already closed
            pass

    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except PWTimeout:
        print("* select_process: networkidle timeout ignored; continuing.")


def submit_job_simple(page: Page) -> None:
    """
    Submit job with standard two-step confirmation flow: Submit → OK → OK.
    
    Fusion's submit flow uses nested dialogs:
    1. Submit button opens confirmation dialog
    2. First OK (in a <td> cell, nth(1)) confirms the action
    3. Second OK (button role) closes the confirmation message
    
    DRY_UI=true: Only logs the action without actually submitting (for testing).
    """
    if DRY_UI:
        print("[-] DRY RUN: Would click Submit → OK → OK (job NOT submitted).")
        return

    print("[@] Submitting job...")
    wait_for_glass_pane_gone(page)  # wait for any overlay before Submit is clickable
    submit_btn = page.get_by_role("button", name="Submit", exact=True)
    slow(page)  # give Fusion time to enable Submit
    submit_btn.click(timeout=90000)  # 90s — Oracle can take ~60s to process submission
    slow(page)

    # First OK in dialog - uses <td> cell locator because Fusion renders
    # this OK in a table cell rather than as a proper button
    ok_cells = page.locator("td").filter(has_text=re.compile(r"^OK$"))
    ok_cells.nth(1).click(timeout=90000)  # 90s — wait for confirmation dialog
    slow(page)

    # Second OK (confirmation) - this one is a proper button
    page.get_by_role("button", name="OK").click(timeout=90000)  # 90s — wait for final OK
    slow(page)

    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except PWTimeout:
        print("* submit_job_simple: networkidle timeout ignored; continuing.")


# ---------------------------------------------------------------------------
# Universal parameter setter
# ---------------------------------------------------------------------------

def set_param(page: Page, label: str, value: str) -> bool:
    """
    Universal parameter setter with cascading fallback strategy.
    
    Oracle Fusion uses inconsistent UI patterns across different job types:
    - Modern jobs: Accessible combobox with proper ARIA roles
    - Legacy jobs: LOV (List of Values) pattern with span/label + anchor
    - Simple jobs: Plain textbox inputs
    
    Strategy:
    1. Try role-based combobox first (most reliable, uses accessibility APIs)
    2. Fall back to LOV-style anchor dropdown (legacy Oracle ADF pattern)
    3. Finally try textbox (for simple text inputs)
    
    Case-insensitive matching allows flexibility with label variations
    across different Fusion versions.

    Returns:
      True  if some control was found and set,
      False if nothing matched (caller can try alternate labels).
    """
    if not value:
        return False

    print(f"   > Setting {label} = {value}")
    pattern_label = re.compile(re.escape(label), re.I)
    pattern_value = re.compile(re.escape(value), re.I)

    # 1) Try ROLE-based combobox
    try:
        cbo = page.get_by_role("combobox", name=pattern_label)
        if cbo.count() > 0:
            cbo = cbo.first
            cbo.click()
            slow(page)
            cbo.press("ControlOrMeta+a")
            slow(page)
            cbo.fill(value)
            slow(page)
            # pick matching option if shown
            opts = page.get_by_role("option", name=pattern_value)
            if opts.count() > 0:
                opts.first.click()
                slow(page)
            return True
    except Exception:
        pass

    # 2) Try LOV-style dropdown (label cell/span + anchor)
    # Pattern: <span|td|label>LabelText</...><a> (anchor triggers dropdown)
    try:
        for base in ("span", "td", "label"):
            lov = page.locator(base).filter(has_text=pattern_label).locator("a")
            if lov.count() > 0:
                lov.first.click()
                slow(page)
                opts = page.get_by_role("option", name=pattern_value)
                if opts.count() > 0:
                    opts.first.click()
                    slow(page)
                return True
    except Exception:
        pass

    # 3) Fallback: textbox with that label
    try:
        box = page.get_by_role("textbox", name=pattern_label)
        if box.count() > 0:
            box = box.first
            box.click()
            slow(page)
            box.press("ControlOrMeta+a")
            slow(page)
            box.fill(value)
            slow(page)
            return True
    except Exception:
        pass

    print(f"   * WARNING: Did not find UI control for label={label!r}")
    return False


# ---------------------------------------------------------------------------
# Job-type specific handlers
# ---------------------------------------------------------------------------

def handle_balance_cube_job(page: Page, row: Dict[str, object]) -> None:
    """
    Red jobs:
      - Create General Ledger Balances Cube
      - Create Budgetary Control Balances Cube

    Parameters from Excel:
      - Chart of Accounts
      - Accounting Calendar (or Budget Calendar / Control Budget)
      - Starting Period (dropdown search dialog)
    """
    coa = cell(row, "Chart of Accounts")
    cal = cell(row, "Accounting Calendar")
    start_period = cell(row, "Starting Period")

    if coa:
        set_param(page, "Chart of Accounts", coa)

    if cal:
        # Try main label first
        ok = set_param(page, "Accounting Calendar", cal)
        if not ok:
            # Budgetary Control job might use different label text
            for alt_label in ("Budget Calendar", "Control Budget", "Budget", "Calendar"):
                if set_param(page, alt_label, cal):
                    print(f"   > Used alternate label for calendar: {alt_label}")
                    ok = True
                    break
        if not ok:
            print("   * Could not set calendar using any known label.")

    if start_period:
        print(f"   > Setting Starting Period = {start_period}")
        try:
            # Be flexible about the title - match anything containing 'Starting Period'
            # or at least 'Period'
            sp_btn = page.locator("[title*='Starting Period'], [title*='Period']")
            if sp_btn.count() == 0:
                raise Exception("No element with title containing 'Starting Period' or 'Period' found.")
            sp_btn.first.click()
            slow(page)
            # Allow case-insensitive match on the cell
            cell_loc = page.get_by_role(
                "cell",
                name=re.compile(re.escape(start_period), re.I),
            )
            cell_loc.first.click()
            slow(page)
        except Exception as exc:
            print(f"   * Could not set Starting Period via search dialog: {exc}")

    submit_job_simple(page)


def handle_simple_ess_job(page: Page) -> None:
    """
    Brown / grey jobs that don't need parameters or schedule:
      - Import User and Role Application Security Data
      - Send Pending LDAP Requests (if simple)
      - Compute Users ACL (grey)
      - etc.
    """
    submit_job_simple(page)


def handle_send_personal_data_ldap(page: Page) -> None:
    """
    Handle "blue job": Send Personal Data for Multiple Users to LDAP
    
    Sets User Population = "All users" using Oracle's LOV (List of Values) pattern.
    
    LOV Pattern in Fusion:
      <span>User PopulationAll</span><a> ← anchor triggers dropdown
      
    Uses flexible matching because the label text may have spacing variations
    ("User Population All" vs "User PopulationAll") depending on Fusion version.
    Fallback checks broader element types (td, span, label) if initial span fails.
    """
    print("   > Setting User Population = All users")

    try:# Primary: Look for span with "User Population" text + anchor
        lov = page.locator("span").filter(
            has_text=re.compile(r"User Population\s*All", re.I)
        ).locator("a")
        if lov.count() == 0:
            # Fallback: any label containing "User Population"
            lov = page.locator("td, span, label").filter(
                has_text=re.compile(r"User Population", re.I)
            ).locator("a")

        if lov.count() == 0:
            raise Exception("Could not find LOV anchor for User Population")

        lov.first.click()
        slow(page)

        opt = page.get_by_role("option", name=re.compile(r"All users", re.I))
        opt.first.click()
        slow(page)
    except Exception as exc:
        print(f"    Could not set User Population = All users → {exc}")

    submit_job_simple(page)


def handle_index_reingest_job(page: Page, row: Dict[str, object]) -> None:
    """
    Green job:
      - ESS job to create index definition and perform initial ingest to OSCS

    Uses: Index Name to Reingest
    
    Special handling required:
      This job's UI has poor accessibility - the textbox often lacks a proper
      ARIA name attribute. We try:
      1. Textbox with name containing "Index" (best case)
      2. First text input on page (fallback when accessibility is missing)
      
      The fallback is necessary because Oracle sometimes renders this field
      without any accessible label, making it impossible to target by name.
    """
    index_name = cell(row, "Index Name to Reingest")
    if not index_name:
        raise ValueError("Index Name to Reingest is required for this job type.")

    print(f"   > Setting Index Name to Reingest = {index_name}")

    # Try textbox with accessible name containing "Index"
    box = page.get_by_role("textbox", name=re.compile(r"Index", re.I))

    if box.count() == 0:
        # Fallback: first plain text input on the page
        # Risky but necessary - assumes the index name field is the only/first input
        print("   * No textbox with name containing 'Index' found; "
              "falling back to first text input on page.")
        box = page.locator("input[type='text']").first

    try:
        box.click()
        slow(page)
        box.press("ControlOrMeta+a")
        slow(page)
        box.fill(index_name)
        slow(page)
    except Exception as exc:
        print(f"    Failed to set index name field: {exc}")

    submit_job_simple(page)


def handle_load_and_index_job_requisitions(page: Page) -> None:
    """
    Pink job:
      - Load and Index Job Requisitions
      - Load and Index Candidates

    Changes Indexing Mode from default "Upgrade Current Index" to "Drop and Recreate Index".
    
    Why "Drop and Recreate":
      Ensures a clean index rebuild without potential corruption from incremental updates.
      Required for post-refresh environments where index state may be stale.
    
    Uses fallback strategy:
      1. Modern combobox with ARIA role (newer Fusion versions)
      2. Legacy LOV span/anchor pattern with flexible text matching
    """
    print("   > Setting Indexing Mode = Drop and Recreate Index")

    # 1) Try the clean ARIA combobox first (works if the dropdown has name "Indexing Mode")
    try:
        cbo = page.get_by_role("combobox", name=re.compile(r"Indexing Mode", re.I))
        if cbo.count() > 0:
            cbo.first.click()
            slow(page)
            opt = page.get_by_role("option", name=re.compile(r"Drop and Recreate Index", re.I))
            opt.first.click()
            slow(page)
            submit_job_simple(page)
            return
    except Exception:
        pass

    # 2) Fallback to old span/anchor pattern, but more flexible on text:
    #    handle "Indexing Mode Upgrade Current Index" OR "Upgrade Current" etc.
    try:
        span = page.locator("span").filter(
            has_text=re.compile(r"Indexing Mode\s*Upgrade Current", re.I)
        ).locator("a")
        if span.count() == 0:
            # very generic: any span containing "Indexing Mode"
            span = page.locator("span").filter(
                has_text=re.compile(r"Indexing Mode", re.I)
            ).locator("a")
        if span.count() > 0:
            span.first.click()
            slow(page)
            opt = page.get_by_role("option", name=re.compile(r"Drop and Recreate Index", re.I))
            opt.first.click()
            slow(page)
        else:
            print("    Could not find LOV anchor for Indexing Mode; leaving default.")
    except Exception as exc:
        print(f"    Failed to change Indexing Mode dropdown: {exc}")

    submit_job_simple(page)


def _click_using_a_schedule(page: Page) -> None:
    """
    Helper to robustly click the 'Using a schedule' radio.
    """
    clicked = False
    # Try by text
    try:
        lbl = page.get_by_text(re.compile(r"Using a schedule", re.I))
        if lbl.count() > 0:
            lbl.first.click()
            slow(page)
            clicked = True
    except Exception:
        pass

    # Try radio role if needed
    if not clicked:
        try:
            radio = page.get_by_role("radio", name=re.compile(r"Using a schedule", re.I))
            if radio.count() > 0:
                radio.first.click()
                slow(page)
                clicked = True
        except Exception:
            pass

    if not clicked:
        print("    Could not click 'Using a schedule' radio.")


def handle_scheduled_compute_users_acl_by_event(page: Page, row: Dict[str, object]) -> None:
    """
    Yellow job:
      Compute Users ACL by Event (scheduled version)

    Sets up recurring schedule based on Excel icalstring (e.g., "FREQ=HOURLY;INTERVAL=15").
    
    Schedule configuration:
      - Start Date: Current time (immediate start)
      - End Date: 1 year from now (standard refresh cycle)
      - Frequency: Parsed from icalstring (HOURLY, DAILY, etc.)
      - Interval: For HOURLY/MINUTELY only, sets specific recurrence (e.g., every 15 minutes)
    
    Requires Advanced section to be expanded before accessing schedule controls.

    *****Had issues with trhe scheduled jobs that is why I created a more hardcoded version*****
    """
    ical = cell(row, "icalstring")
    freq, interval = parse_ical(ical)
    sched_label = schedule_option_label(freq)
    start_str, end_str = now_and_plus_one_year_strings()

    print(f"   > Schedule: freq={freq}, interval={interval}, label={sched_label}")
    print(f"   > Start Date = {start_str}, End Date = {end_str}")

    # Make sure Advanced is open (contains schedule controls)
    adv_btn = page.get_by_role("button", name=re.compile(r"Advanced", re.I))
    if adv_btn.count() > 0:
        adv_btn.first.click()
        slow(page)
    else:
        print("    Could not find 'Advanced' button.")
        return

    # Click "Using a schedule"
    _click_using_a_schedule(page)

    # Open schedule dropdown, pick based on FREQ
    page.locator(
        "td"
    ).filter(
        has_text=re.compile(
            r"^OnceHourly/MinuteDailyWeeklyMonthlyYearlyUser-DefinedUse a Saved Schedule$"
        )
    ).locator("a").click()
    slow(page)
    page.get_by_role("option", name=sched_label).click()
    slow(page)

    # For HOURLY/MINUTELY frequencies, set specific interval
    # (e.g., "every 15 minutes" or "every 2 hours")
    if freq and freq.upper() in ("HOURLY", "MINUTELY"):
        hours = 0
        minutes = interval if interval is not None else 15 # Default to 15 min if not specified just safe backup option
        print(f"   > Hours={hours}, Minutes={minutes}")
        h_box = page.get_by_role("textbox", name="Hours")
        h_box.click()
        slow(page)
        h_box.press("ControlOrMeta+a")
        slow(page)
        h_box.fill(str(hours))
        slow(page)

        m_box = page.get_by_role("textbox", name="Minutes")
        m_box.click()
        slow(page)
        m_box.press("ControlOrMeta+a")
        slow(page)
        m_box.fill(str(minutes))
        slow(page)

    # Start/End dates
    start_box = page.get_by_role("textbox", name="Start Date")
    start_box.click()
    slow(page)
    start_box.press("ControlOrMeta+a")
    slow(page)
    start_box.fill(start_str)
    slow(page)

    end_box = page.get_by_role("textbox", name="End Date")
    end_box.click()
    slow(page)
    end_box.press("ControlOrMeta+a")
    slow(page)
    end_box.fill(end_str)
    slow(page)

    submit_job_simple(page)


def handle_scheduled_compute_users_with_large_acl(page: Page, row: Dict[str, object]) -> None:
    """
    Orange job:
      - Compute Users with Large ACL

    This job has a two-tab structure:
      1. Parameters tab: Set Report mode and user selection
      2. Schedule tab: Configure recurrence
    
    Configuration:
      - Report mode: "Compute" (generates the large ACL report)
      - User selection: "All users with large ACL"
      - Schedule: From icalstring (typically daily for performance reasons)
      
    Why this job exists:
      Large ACL calculations are expensive. This scheduled report identifies
      users with oversized ACLs for administrative review without impacting
      real-time performance.
    
    Note: Unlike the "by Event" job, this one doesn't support hourly/minute
    intervals - only uses the frequency label (Daily, Weekly, etc.).
    ****All ACL USER JOBS HARDCODED AS TH FLOW OF THE JOBS ONCE SCHEDULED CAME CREATED TOO MANY ISSUES****
    """
    ical = cell(row, "icalstring")
    freq, _ = parse_ical(ical) # Note: interval ignored for this job type
    sched_label = schedule_option_label(freq)
    start_str, end_str = now_and_plus_one_year_strings()

    print(f"   > Schedule: freq={freq}, label={sched_label}")
    print(f"   > Start Date = {start_str}, End Date = {end_str}")
    # Click initial field to ensure page is interactive
    page.locator("td").filter(has_text=re.compile(r"^ReportCompute$")).click()
    slow(page)

    # Make sure Advanced is open
    adv_btn = page.get_by_role("button", name=re.compile(r"Advanced", re.I))
    if adv_btn.count() > 0:
        adv_btn.first.click()
        slow(page)
    else:
        print("    Could not find 'Advanced' button.")
        return
    # Navigate to Schedule tab first (to ensure it's visible)
    page.locator("div").filter(has_text=re.compile(r"^Schedule$")).nth(1).click()
    slow(page)
    # Switch to Parameters tab to configure job settings
    page.get_by_role("link", name="Parameters").click()
    slow(page)

    # Use universal setter for Report + user selection
    set_param(page, "Report", "Compute")
    set_param(page, "All users with large ACL", "All users with large ACL")

    # Schedule tab
    page.locator("div").filter(has_text=re.compile(r"^Schedule$")).nth(1).click()
    slow(page)

    # Click "Using a schedule"
    _click_using_a_schedule(page)
    # Select frequency from dropdown
    page.locator(
        "td"
    ).filter(
        has_text=re.compile(
            r"^OnceHourly/MinuteDailyWeeklyMonthlyYearlyUser-DefinedUse a Saved Schedule$"
        )
    ).locator("a").click()
    slow(page)
    page.get_by_role("option", name=sched_label).click()
    slow(page)
    # Set date range
    start_box = page.get_by_role("textbox", name="Start Date")
    start_box.click()
    slow(page)
    start_box.press("ControlOrMeta+a")
    slow(page)
    start_box.fill(start_str)
    slow(page)

    end_box = page.get_by_role("textbox", name="End Date")
    end_box.click()
    slow(page)
    end_box.press("ControlOrMeta+a")
    slow(page)
    end_box.fill(end_str)
    slow(page)

    submit_job_simple(page)


# ---------------------------------------------------------------------------
# Row dispatcher - Routes each Excel row to the appropriate job handler
# ---------------------------------------------------------------------------

def handle_row(page: Page, row: Dict[str, object], idx: int | None = None) -> None:
    """
    Dispatch a single Excel row to the appropriate job handler based on Display Name.
    
    Job type detection uses keyword matching (case-insensitive) to route to
    specialized handlers. Each handler knows how to:
      1. Fill in job-specific parameters
      2. Configure scheduling (if needed)
      3. Submit the job
    
    Color coding in comments (Red, Blue, Green, etc.) references the original
    design doc for easy cross-reference.
    
    Special handling:
      - Rows 38-43: Pre-clicks Advanced button (workaround for UI timing issue)
      - Rows 39-43: Hard-coded ACL job routing (overrides keyword matching)
    
    Args:
        page: Playwright Page object (already logged in)
        row: Dict from Excel row (contains Display Name, parameters, icalstring, etc.)
        idx: Optional row index for special-case handling
    """
    display_name = cell(row, "Display Name")
    if not display_name:
        print(" Skipping row with empty Display Name")
        return

    print(f" Scheduling job: {display_name!r}")

    open_schedule_new_process(page)
    select_process(page, display_name)

    # Workaround: Force Advanced click for rows 38-43
    # These rows have a timing issue where the Advanced section doesn't
    # auto-expand reliably, causing subsequent handler failures
    if idx is not None and 42 <= idx <= 47:
        adv_btn = page.get_by_role("button", name=re.compile(r"Advanced", re.I))
        if adv_btn.count() > 0:
            print(f"   > (Row {idx}) Forcing click on 'Advanced' button before handler.")
            adv_btn.first.click()
            slow(page)
        else:
            print(f"   * (Row {idx}) Could not find 'Advanced' button to click before handler.")

    name_upper = display_name.upper()

    # Hard override: rows 39-43 are your scheduled ACL jobs
    if idx is not None and 43 <= idx <= 47:
        if "LARGE ACL" in name_upper:
            handle_scheduled_compute_users_with_large_acl(page, row)
        else:
            # default to "by event" if name doesn't explicitly say Large
            handle_scheduled_compute_users_acl_by_event(page, row)
        return

    # Red — balance cube jobs
    if "BALANCES CUBE" in name_upper:
        handle_balance_cube_job(page, row)
        return

    # Blue — Send Personal Data for Multiple Users to LDAP
    if "SEND PERSONAL DATA FOR MULTIPLE USERS TO LDAP" in name_upper:
        handle_send_personal_data_ldap(page)
        return

    # Green — index definition / ingest
    if "INDEX DEFINITION AND PERFORM INITIAL INGEST TO OSCS" in name_upper:
        handle_index_reingest_job(page, row)
        return

    # Pink — Load and Index Job Requisitions / Candidate
    if (
        "LOAD AND INDEX JOB REQUISITIONS" in name_upper
        or "LOAD AND INDEX CANDIDATE" in name_upper
    ):
        handle_load_and_index_job_requisitions(page)
        return

    # Yellow — Compute Users ACL by Event (scheduled)
    if "COMPUTE USERS ACL BY EVENT" in name_upper:
        handle_scheduled_compute_users_acl_by_event(page, row)
        return

    # Orange — Compute Users with Large ACL (scheduled)
    if "COMPUTE USERS WITH LARGE ACL" in name_upper:
        handle_scheduled_compute_users_with_large_acl(page, row)
        return

    # Brown / grey / default — simple ESS jobs with no params or schedule
    handle_simple_ess_job(page)


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------

def _flow(page: Page) -> None:
    """
    Main orchestration loop: reads Excel and processes each job row.
    
    Assumes page is already logged into Oracle Fusion.
    Processes rows sequentially with exception handling per row
    (failures don't stop the entire run).
    
    Row filtering (idx < 1 or idx > 37) allows selective testing
    without modifying the Excel file.
    """
    print(f" Reading Excel: {EXCEL_PATH}")
    df = pd.read_excel(EXCEL_PATH)
    rows = df.to_dict(orient="records")

    print(f" Opening Scheduled Processes... (DRY_UI={DRY_UI})")
    open_scheduled_processes(page)

    for idx, row in enumerate(rows, start=1):
        # ── 4A: Enabled column check ──
        enabled = str(row.get("Enabled", "Y")).strip().upper()
        if enabled in ("N", "NO", "FALSE", "0", ""):
            print(f"  ROW {idx}: SKIPPED (Enabled={row.get('Enabled', '')})")
            continue

        
        if idx < 1 or idx > 40:   #change to 1 and 37 for full doing it 1-37 because the other jobs need to be either hardcode or manual because it did not work properly
            #it failed because once flow got to that section the code struggled to click correct spots/find correct spotsadded 3 jobs so now 40
            continue

        print(f"\n===== ROW {idx} =====")
        try:
            handle_row(page, row, idx=idx)
        except Exception as exc:
            print(f" Row {idx} failed: {exc}")
    # Continue to next row even if this one fails allows continuation if the rows fail will log if skip in terminal

def run_ui_ess_jobs(page: Page) -> None:
    """
    Public entry point: Retry jobs that failed in REST API.
    
    WHAT IT DOES:
        1. Load job_status_tracker.json from REST API
        2. Check if any jobs failed/timed out
        3. If yes: Run only those specific jobs from Excel
        4. If no: Skip (all jobs succeeded)
        5. If no JSON: Run all jobs (fallback)
    
    MATCHING STRATEGY:
        Matches failed job names from JSON to Excel "Display Name" column
        Case-insensitive matching to handle variations
    
    Expects:
      - page: Logged-in Playwright Page object
      - Excel file at EXCEL_PATH with job definitions
      - JSON status file from REST API (optional)
    """
    # Load REST API status
    rest_status = load_failed_jobs()
    
    # Case 1: No status file - run all jobs (backward compatibility)
    if rest_status is None:
        print("  No REST API status available. Running all Excel jobs.")
        _flow(page)
        return
    
    # Case 2: All jobs succeeded - skip UI retry
    failed_jobs_data = rest_status.get("failed_jobs", [])
    if not failed_jobs_data:
        print(" All REST API jobs succeeded. Nothing to retry via UI.")
        return
    
    # Case 3: Some jobs failed - retry only those
    print(f"\n{'='*60}")
    print(f" RETRYING {len(failed_jobs_data)} FAILED JOBS VIA UI")
    print(f"{'='*60}\n")
    
    # Build set of failed excel row numbers from JSON.
    # Using excel_row is the most reliable matching strategy —
    # no name matching needed, works regardless of jobDefinitionName vs Display Name.
    failed_row_numbers = set()
    for job_data in failed_jobs_data:
        excel_row = job_data.get("excel_row")
        job_name = job_data.get("job_name", "")
        reason = job_data.get("reason", "")
        if excel_row:
            failed_row_numbers.add(int(excel_row))
            print(f"  - Row {excel_row}: {job_name} (Reason: {reason})")
    
    print(f"\n{'='*60}\n")
    
    # Read Excel
    print(f" Reading Excel: {EXCEL_PATH}")
    import pandas as pd
    df = pd.read_excel(EXCEL_PATH)
    rows = df.to_dict(orient="records")
    
    print(f" Opening Scheduled Processes... (DRY_UI={DRY_UI})")
    open_scheduled_processes(page)
    
    # Track results
    success_count = 0
    failed_count = 0
    skipped_count = 0
    
    # Process only rows that failed in REST API — matched by excel_row number
    for idx, row in enumerate(rows, start=1):
        # ── 4A: Enabled column check ──
        enabled = str(row.get("Enabled", "Y")).strip().upper()
        if enabled in ("N", "NO", "FALSE", "0", ""):
            print(f"  ROW {idx}: SKIPPED (Enabled={row.get('Enabled', '')})")
            continue
        display_name = cell(row, "Display Name")
        if not display_name:
            continue

        if idx not in failed_row_numbers:
            skipped_count += 1
            continue  # Skip jobs that succeeded in REST API
        
        print(f"\n===== ROW {idx} — RETRYING: {display_name} =====")

        # Skip ACL jobs — always fail via UI, must be done manually
        ACL_DISPLAY_NAMES = {
            "compute users acl",
            "compute users acl by event",
            "compute users with large acl",
            "computeusersaclprocessor",
            "datasecurityaclrefresh",
            "manageexcludedusersacl",
        }
        if display_name.strip().lower() in ACL_DISPLAY_NAMES:
            print(f" Skipping ACL in retry loop (compute users acl handled by hardcoded ACL runner)run manually: {display_name}")
            skipped_count += 1
            continue

        try:
            handle_row(page, row, idx=idx)
            success_count += 1
            print(f" UI retry successful: {display_name}")
        except Exception as exc:
            failed_count += 1
            print(f" UI retry failed: {display_name} - {exc}")
            import traceback
            traceback.print_exc()
            # Recovery: close any open dialogs, then wait for page to stabilize
            # so the next row starts from a clean state.
            # Press Escape to dismiss any open LOV/search dialog — works even
            # when the glass pane is blocking button clicks.
            try:
                page.keyboard.press("Escape")
                slow(page, ms=2000)
                page.keyboard.press("Escape")  # press twice in case nested dialogs
                slow(page, ms=2000)
                print("  Pressed Escape to dismiss any open dialogs.")
            except Exception:
                pass
            try:
                wait_for_glass_pane_gone(page, timeout_ms=90000)
                slow(page, ms=5000)
                print("  Page stabilized, continuing to next row.")
            except Exception:
                pass
    
    # Summary
    print(f"\n{'='*60}")
    print(f" UI ESS RETRY SUMMARY")
    print(f"{'='*60}")
    print(f" Successful retries: {success_count}")
    print(f" Failed retries:     {failed_count}")
    print(f" Skipped (already succeeded in REST API): {skipped_count}")
    print(f" Total Excel rows:   {len(rows)}")
    print(f"{'='*60}\n")

    # ACL jobs always fail via UI automation — print clear manual instruction
    if rest_status is not None:
        acl_status = rest_status.get('acl_jobs_status', {})
        if not acl_status.get('completed', True):
            failed_acl = acl_status.get('failed_acl_jobs', [])
            print('=' * 60)
            print(' NOTE: Compute Users ACL failed via REST API.')
            print(' It will be attempted via UI at the end of this run.')
            print(' Final ACL status will be reported after the hardcoded ACL runner.')
            for acl_job in failed_acl:
                print(f'   - {acl_job}')

def run_hardcoded_acl_jobs(page):
    """
     Hard-coded ACL + search-related scheduled jobs (alternative to Excel rows 37-43).
    
    WHY THIS EXISTS:
      These jobs use complex UI interactions that are difficult to drive purely
      from Excel data. Hard-coding ensures reliability for critical recurring jobs.
      
      This function can be used as:
      1. A replacement for Excel rows 37-43 (call instead of run_ui_ess_jobs)
      2. A reference implementation for manual execution
      3. A fallback when Excel-driven approach fails for these specific jobs
    
    Job Definitions:
      Row 38: Compute Users ACL (grey, one-time, no schedule)
      Row 39: Maintain Candidates and Job Requisitions for Search (every 15 min)
      Row 40: Index Candidates Attachments (every 15 min)
      Row 41: Compute Users ACL by Event (every 30 min)
      Row 42: Compute Users ACL (every 60 min)
      Row 43: Compute Users with Large ACL (daily)
    
    Note: The commented-out sections (rows 37, 40-42) are best done manually via UI because 
    when ran it runs into issues sometimes where it might miss one or two clicks and these jobs are important and must be ran at end.
    Oracle Fusion prevents duplicate scheduled job submissions even when
    using automation. The code is idempotent but will fail gracefully if jobs
    already exist.
    """
    # ========== UPDATE 1.0.1 NEW SECTION ==========
    # Load REST API status to check if ACL jobs need retry
    rest_status = load_failed_jobs()
    
    # Determine if we need to run ACL jobs
    run_acl_jobs = True  # Default: run them (safety)
    
    if rest_status is not None:
        acl_status = rest_status.get("acl_jobs_status", {})
        acl_completed = acl_status.get("completed", True)
        
        if acl_completed:
            print(" ACL jobs succeeded in REST API. Skipping UI ACL jobs.")
            return  # Skip entirely if REST API succeeded
        else:
            print(f"\n{''*30}")
            print(f" ACL JOBS FAILED IN REST API - RUNNING VIA UI")
            failed_acl = acl_status.get("failed_acl_jobs", [])
            print(f"Failed ACL jobs: {failed_acl}")
            print(f"{''*30}\n")
            run_acl_jobs = True
    else:
        print(" No REST API status. Running ACL jobs as safety measure.")
        run_acl_jobs = True
    
    # Only continue if we need to run ACL jobs
    if not run_acl_jobs:
        return
    # ========== END NEW SECTION ==========
    import re
    from datetime import datetime, timedelta

    # local slow to avoid conflict with global slow(page, ms)
    def _slow(ms=3000):
        page.wait_for_timeout(ms)

    # Start Date = 1 hour from now called tomorrow because I changed timedelta from days to now hours and didn't want to fix naming
    # End Date = 1 year from start
    def now_and_plus_one():
        tomorrow = datetime.now() + timedelta(hours=1)
        end = tomorrow + timedelta(days=365)
        fmt = "%m/%d/%Y %I:%M %p"
        return tomorrow.strftime(fmt), end.strftime(fmt)

    print("\n========== HARD-CODED ROWS 41-47 ==========")
    acl_result = {"compute_users_acl": None}

    #The following hardcoded jobs were not working in any flexible way,
    #I used playwright to extract the steps from the clicks but I formatted in way that is sacrificing flexibility. 
    #Without the sacrifice too many issues were happening.
    #Being said some jobs do not run correctly 100% of the time 37 then 40-42.
    #The jobs here that work are 38 and 39. I left bad code in too 37, 40-42 because it is possible to be corrected, although might be challenging.
    #The jobs follow very simple, not flexible flow, if ORACLE UI changes these jobs have highest potential for failure.
    #Each job follows the pattern:
      #  1. Open "Schedule New Process"
       # 2. Search for job by name
       # 3. Click OK to select
      #  4. Expand Advanced section
      #  5. Enable "Using a schedule"
      #  6. Set frequency (Hourly/Minute, Daily, etc.)
      #  7. Set Hours/Minutes (if applicable)
      #  8. Set Start/End dates
      #  9. Submit → OK → OK
    

        # --------------------------------------------------------
    # ROW 38 — Maintain Candidates and Job Requisitions for Search (15 min)
    # --------------------------------------------------------
    try:    
        print("\n=== ROW 42 — Maintain Candidates and Job Requisitions for Search (15 min) ===")

        start_date, end_date = now_and_plus_one()

        page.get_by_role("button", name="Schedule New Process").click(); _slow()
        page.get_by_role("combobox", name="Name").click()
        page.get_by_role("combobox", name="Name").press("ControlOrMeta+a")
        page.get_by_role("combobox", name="Name").fill("Maintain Candidates and Job Requisitions for Search")
        page.get_by_role("combobox", name="Name").press("Enter")
        _slow()

        page.get_by_role("button", name="OK").first.click(); _slow()

        page.get_by_role("button", name="Advanced").click(); _slow()
        page.get_by_text("Using a schedule").click(); _slow()

        page.locator("td").filter(
            has_text=re.compile(
                r"^OnceHourly/MinuteDailyWeeklyMonthlyYearlyUser-DefinedUse a Saved Schedule$"
            )
        ).locator("a").click()
        _slow()

        page.get_by_role("option", name="Hourly/Minute").click(); _slow()

        page.get_by_role("textbox", name="Hours").fill("0"); _slow()
        page.get_by_role("textbox", name="Minutes").fill("15"); _slow()

        page.get_by_role("textbox", name="Start Date").fill(start_date); _slow()
        page.get_by_role("textbox", name="End Date").fill(end_date); _slow()

        page.locator("div").filter(has_text=re.compile("^Submit$")).click(); _slow()
        page.locator("td").filter(has_text=re.compile("^OK$")).nth(1).click(); _slow()
        page.get_by_role("button", name="OK").first.click(); _slow()
    except Exception as exc:
        print(f"!!! Maintain Candidates failed (continuing to next job): {exc}")
        try:
            page.keyboard.press("Escape"); _slow()
            page.keyboard.press("Escape"); _slow()
        except Exception:
            pass

     # --------------------------------------------------------
    # ROW 39 — Index Candidates Attachments (15 min)
    # --------------------------------------------------------
    try:
        print("\n=== ROW 43 — Index Candidates Attachments (15 min) ===")

        start_date, end_date = now_and_plus_one()

        page.get_by_role("button", name="Schedule New Process").click(); _slow()
        page.get_by_role("combobox", name="Name").click()
        page.get_by_role("combobox", name="Name").press("ControlOrMeta+a")
        page.get_by_role("combobox", name="Name").fill("Index Candidate Attachments")
        _slow()
        page.get_by_role("combobox", name="Name").press("Enter")
        _slow()

        page.get_by_role("button", name="OK").first.click(); _slow()

        page.get_by_role("button", name="Advanced").click(); _slow()
        page.get_by_text("Using a schedule").click(); _slow()

        page.locator("td").filter(
            has_text=re.compile(
                r"^OnceHourly/MinuteDailyWeeklyMonthlyYearlyUser-DefinedUse a Saved Schedule$"
            )
        ).locator("a").click()
        _slow()

        page.get_by_role("option", name="Hourly/Minute").click(); _slow()

        page.get_by_role("textbox", name="Hours").fill("0"); _slow()
        page.get_by_role("textbox", name="Minutes").fill("15"); _slow()

        page.get_by_role("textbox", name="Start Date").fill(start_date); _slow()
        page.get_by_role("textbox", name="End Date").fill(end_date); _slow()

        page.locator("div").filter(has_text=re.compile("^Submit$")).click(); _slow()
        page.locator("td").filter(has_text=re.compile("^OK$")).nth(1).click(); _slow()
        page.get_by_role("button", name="OK").first.click(); _slow()
    except Exception as exc:
        print(f"!!! Index Candidate Attachments failed (continuing to next job): {exc}")
        try:
            page.keyboard.press("Escape"); _slow()
            page.keyboard.press("Escape"); _slow()
        except Exception:
            pass


    print("\n=== Compute Users ACL (UI, immediate submit) ===")
    try:
        page.get_by_role("button", name="Schedule New Process").click(); _slow()
            # Search + select the process
        name_box = page.get_by_role("combobox", name="Name")
        robust_click(page, name_box, label="Name combobox")
        name_box.fill("Compute Users ACL")
        name_box.press("Enter")
        _slow()
        
            # Select from results, then verify the process dialog actually opened
        cell_loc = page.get_by_role("cell", name="Compute Users ACL", exact=True)
        cell_loc.first.click()
        slow(page)
            # verify-landing: the OK/Submit dialog should now be present before we proceed
        page.get_by_role("button", name="OK").first.wait_for(state="visible", timeout=15000)
        _slow()
        
            # Confirm process-selection dialog (two OKs can stack — handle both defensively)
        robust_click(page, page.get_by_role("button", name="OK").nth(1), label="process-select OK")
        robust_click(page, page.get_by_role("button", name="OK").first, label="params OK")
        _slow()
        
            # Submit (params ALL_USERS / N are UI defaults — nothing to set)
        robust_click(page, page.get_by_role("button", name="Submit", exact=True), label="Submit")
        robust_click(page, page.get_by_role("button", name="OK").first, label="submit-confirm OK")
        _slow()
        print("=== Compute Users ACL submitted ===")
        acl_result["compute_users_acl"] = True
    except Exception as exc:
        if acl_result["compute_users_acl"] is not True:
            acl_result["compute_users_acl"] = False
        print(f"!!! Compute Users ACL FAILED via UI please run manually: {exc}")
        try:
            page.keyboard.press("Escape"); _slow()
            page.keyboard.press("Escape"); _slow()
        except Exception:
            pass
    print("\n" + "=" * 60)
    print(" ACL HARDCODED RUN — FINAL STATUS")
    print("=" * 60)
    if acl_result.get("compute_users_acl") is True:
        print(" [OK] Compute Users ACL: submitted via UI successfully.")
        print("      Verify it reaches SUCCEEDED in Scheduled Processes.")
    else:
        print(" [FAIL] Compute Users ACL could NOT be submitted via UI.")
        print(" ACTION REQUIRED — run it manually in Oracle Fusion:")
        print("   1. Tools -> Scheduled Processes -> Schedule New Process")
        print("   2. Search 'Compute Users ACL', submit with defaults (ALL_USERS / N)")
    print("=" * 60 + "\n")
    return acl_result
    '''
    THE PROBLEM:
    
    When you search for "Compute Users ACL" in Fusion, it shows multiple jobs 
    with the same or similar names in a grid. The automation can't tell them apart.
    
    Search results look like:
      - Compute Users ACL (one-time)
      - Compute Users ACL (scheduled)  
      - Compute Users ACL by Event
      - Compute Users with Large ACL
    
    WHERE IT FAILS:
    
    This line picks the first matching cell, which is often the wrong job:
    
        page.get_by_role("cell", name="Compute Users ACL", exact=True).first.click()
    
    The problem: All these cells have identical text. There's no reliable way to 
    pick the right one because job IDs aren't visible in the UI.

    It also might pick the correct job but fail to find the OK button for some reason.
    Despite this section matching 1-1 with what I would actualy click in the UI the code more times than none fails 
    to identify the correct click.

    WHAT I TRIED:
    
    - Double-clicking the cell → Still picks wrong job
    - Using hardcoded element IDs → Breaks in different environments
    - Using nth() position → Changes between page loads

    # --------------------------------------------------------
    # ROW 41 — Compute Users ACL by Event (30 min)
    # --------------------------------------------------------
    print("\n=== ROW 40 — Compute Users ACL by Event (30 min) ===")

    start_date, end_date = now_and_plus_one()

    page.get_by_role("button", name="Schedule New Process").click(); _slow()
    page.get_by_role("combobox", name="Name").click()
    page.get_by_role("combobox", name="Name").press("ControlOrMeta+a")
    page.get_by_role("combobox", name="Name").fill("Compute Users ACL by Event")
    page.get_by_role("combobox", name="Name").press("Enter")
    _slow()

    page.get_by_role("button", name="OK").first.click(); _slow()

    page.get_by_role("button", name="Advanced").click(); _slow()
    page.get_by_role("link", name="Schedule").click(); _slow()
    page.get_by_text("Using a schedule").click(); _slow()

    page.locator("td").filter(
        has_text=re.compile(
            r"^OnceHourly/MinuteDailyWeeklyMonthlyYearlyUser-DefinedUse a Saved Schedule$"
        )
    ).locator("a").click()
    _slow()

    page.get_by_role("option", name="Hourly/Minute").click(); _slow()

    page.get_by_role("textbox", name="Hours").fill("0"); _slow()
    page.get_by_role("textbox", name="Minutes").fill("30"); _slow()

    page.get_by_role("textbox", name="Start Date").fill(start_date); _slow()
    page.get_by_role("textbox", name="End Date").fill(end_date); _slow()

    page.locator("div").filter(has_text=re.compile("^Submit$")).click(); _slow()
    page.locator("td").filter(has_text=re.compile("^OK$")).nth(1).click(); _slow()
    page.get_by_role("button", name="OK").first.click(); _slow()
    
    # --------------------------------------------------------
    # ROW 42 — Compute Users ACL (60 min)
    # --------------------------------------------------------
    print("\n=== ROW 41 — Compute Users ACL (60 min) ===")

    start_date, end_date = now_and_plus_one()

    page.get_by_role("button", name="Schedule New Process").click(); _slow()
    page.get_by_role("combobox", name="Name").click()
    page.get_by_role("combobox", name="Name").press("ControlOrMeta+a")
    page.get_by_role("combobox", name="Name").fill("Compute Users ACL")
    page.get_by_role("combobox", name="Name").press("Enter")
    _slow()
    page.get_by_role("cell", name="Compute Users ACL", exact=True).first.click()
    _slow()
    page.get_by_role("cell", name="Compute Users ACL", exact=True).first.click()
    _slow()
    
    page.get_by_role("button", name="OK").first.click(); _slow()
    page.locator("[id=\"_FOpt1:_FOr1:0:_FONSr2:0:_FOTsr1:0:pt1:r1:0:r1:0:r1:basicReqBody:paramDynForm_Attribute1_ATTRIBUTE1::drop\"]").click()
    page.get_by_role("option", name="Logged in users").click()
    page.get_by_role("button", name="Advanced").click(); _slow()
    page.get_by_role("link", name="Schedule").click(); _slow()
    page.get_by_text("Using a schedule").click(); _slow()

    page.locator("td").filter(
        has_text=re.compile(
            r"^OnceHourly/MinuteDailyWeeklyMonthlyYearlyUser-DefinedUse a Saved Schedule$"
        )
    ).locator("a").click()
    _slow()

    page.get_by_role("option", name="Hourly/Minute").click(); _slow()

    page.get_by_role("textbox", name="Hours").fill("1"); _slow()
    page.get_by_role("textbox", name="Minutes").fill("0"); _slow()

    page.get_by_role("textbox", name="Start Date").fill(start_date); _slow()
    page.get_by_role("textbox", name="End Date").fill(end_date); _slow()

    page.locator("div").filter(has_text=re.compile("^Submit$")).click(); _slow()
    page.locator("td").filter(has_text=re.compile("^OK$")).nth(1).click(); _slow()
    page.get_by_role("button", name="OK").first.click(); _slow()
    
    # --------------------------------------------------------
    # ROW 43 — Daily job — Compute Users with Large ACL
    # --------------------------------------------------------
    print("\n=== ROW 42 — Compute Users with Large ACL (Daily) ===")

    start_date, end_date = now_and_plus_one()

    page.get_by_role("button", name="Schedule New Process").click(); _slow()
    page.get_by_role("combobox", name="Name").click()
    page.get_by_role("combobox", name="Name").press("ControlOrMeta+a")
    page.get_by_role("combobox", name="Name").fill("Compute Users with Large ACL")
    page.get_by_role("combobox", name="Name").press("Enter")
    _slow()

    page.get_by_role("button", name="OK").click(); _slow()

    page.locator("td").filter(has_text=re.compile("^ReportCompute$")).click(); _slow()
    page.get_by_role("button", name="Advanced").click(); _slow()
    page.get_by_role("link", name="Parameters").click(); _slow()
    page.locator("td").filter(has_text=re.compile("^ReportCompute$")).locator("a").click()
    page.get_by_role("option", name="Compute").click(); _slow()
    page.locator("td").filter(has_text=re.compile("^All users with large ACL")).locator("a").click()
    page.get_by_role("option", name="All users with large ACL").click(); _slow()

    page.get_by_role("link", name="Schedule").click(); _slow()
    page.get_by_text("Using a schedule").click(); _slow()

    page.locator("td").filter(
        has_text=re.compile(
            r"^OnceHourly/MinuteDailyWeeklyMonthlyYearlyUser-DefinedUse a Saved Schedule$"
        )
    ).locator("a").click()
    page.get_by_role("option", name="Daily").click(); _slow()

    page.get_by_role("textbox", name="Start Date").fill(start_date); _slow()
    page.get_by_role("textbox", name="End Date").fill(end_date); _slow()

    page.locator("div").filter(has_text=re.compile("^Submit$")).click(); _slow()
    page.locator("td").filter(has_text=re.compile("^OK$")).nth(1).click(); _slow()
    page.get_by_role("button", name="OK").click(); _slow()

# --------------------------------------------------------
    # ROW 38 — GREY JOB — Compute Users ACL (no schedule)
    # --------------------------------------------------------
    print("\n=== ROW 38 — Compute Users ACL (grey, one-time) ===")

    page.get_by_role("button", name="Schedule New Process").click(); _slow()
    page.get_by_role("combobox", name="Name").click()
    page.get_by_role("combobox", name="Name").press("ControlOrMeta+a")
    page.get_by_role("combobox", name="Name").fill("Compute Users ACL")
    page.get_by_role("combobox", name="Name").press("Enter")
    _slow()

    page.get_by_role("cell", name="Compute Users ACL", exact=True).first.click()
    _slow()
    page.get_by_role("cell", name="Compute Users ACL", exact=True).first.click()
    _slow()

    page.get_by_role("button", name="OK").nth(1).click(); _slow()
    page.get_by_role("button", name="OK").first.click(); _slow()

    # Submit
    page.locator("div").filter(has_text=re.compile(r"^Submit$")).click(); _slow()
    page.locator("td").filter(has_text=re.compile(r"^OK$")).nth(1).click(); _slow()
    page.get_by_role("button", name="OK").click(); _slow()
    print("\n========== HARD-CODED ROWS 38-44 COMPLETE ==========\n")
# '''
    
#The commented out ones is best done manual if you do through UI. The Ui version is indeed idempotent because I tested it and Oracle does not allow you to 
#repost the job even with thecode ui or through actual self.