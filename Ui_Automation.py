from __future__ import annotations
# Ui_Automation.py
"""
Oracle Fusion Post-Refresh Automation System - Main UI Task Runner

WHAT THIS FILE DOES:
    Automates 18+ Oracle Fusion UI configuration tasks that must be run after
    every environment refresh (e.g., DEV10 refreshed from PROD). These tasks
    include disabling notifications, updating banners, removing ADP deliveries,
    configuring security settings, and more.
    
    Automates Oracle Fusion browser tasks with built-in error recovery, screenshot
    capture, and crash-proof logging. Uses Playwright for the browser control part.

WHY EVERYTHING IS IN ONE FILE:
    No real reasomn. I just started to build and happened to slowly keep building in one file.
    I just stuck with it because I felt like it.
    It just happened naturally as the project grew.
    
    If I were to redo this, I'd probably:
    - Separate each task into its own file (task_1.py, task_2.py, etc.)
    - Have one main file that imports and calls them all
    - Add options to run specific tasks or skip certain ones
    - Create a "run all" mode vs selective execution (e.g., --only task_1,task_3)
    
    But for now, it works perfectly fine as-is. ¯\\_(ツ)_/¯

FILE STRUCTURE:
    - Part 1  Imports, global config, instance detection
    - Part 2  Login helpers, ensure_logged_in_and_home(), etc
    - Part 3  Pre-task: setup_procurement_access_for_user(), data access,etc
    - Part 4 Task functions (task1 through task23)
    - Part 5- end: Main runner with sync_playwright()

KEY FEATURES:
    - Persistent browser profile (stays logged in between runs)
    - Instance-aware (auto-detects DEV10, TEST, etc. from URL)
    - DRY_RUN mode (test without making changes)
    - Automatic screenshot capture (on success and failure)
    - Crash-proof SQLite logging (survives force-close)
    - Error recovery (failed tasks don't stop the suite)

GLOBAL VARIABLES (top of file):
    PAUSE:           Milliseconds between steps (default: 3500ms)
    DRY_RUN:         True = no saves/commits; False = real changes
    INSTANCE_URL:    Target Oracle Fusion URL (change this for different envs, (from .env or hardcoded fallback))
    HOME_URL:        Derived from INSTANCE_URL
    INSTANCE_LABEL:  Auto-detected (DEV10, TEST, etc.)
    PROFILE_DIR:     Playwright persistent context directory

CREDENTIALS (from .env file):
    FUSION_USERNAME: Oracle Fusion username (fallback: hardcoded default)
    FUSION_PASSWORD: Oracle Fusion password (fallback: hardcoded default)
    TENANT_BASE_URL: Oracle Fusion URL (fallback: hardcoded default)
USAGE:
     Run all tasks:
    python UI_Automation.py
    
     Set credentials and URL in .env file:
    FUSION_USERNAME=your.username
    FUSION_PASSWORD=YourPassword123
    FUSION_URL=https://(client)-saasfaprod1.fa.ocs.oraclecloud.com
    Or change instance URL in code:
    Edit INSTANCE_URL at top of file

     Dry run mode (no changes):
    Set DRY_RUN = True 
    
     View logs after crash:
    python terminal_logger.py C:\\Users\\...\\Desktop\\ui_automation_logs\\ui_automation_*.db
    
     Check screenshots:
    screenshots/<Task_Name>/YYYY-MM-DD_HH-MM-SS_SUCCESS.png


ROLE/DATA ACCESS LIST:(Pre-Task Setup):
    The setup_procurement_access_for_user() function grants the following to the specified user:
    ***If added prior then no need for this step, recommend add prior to refresh***
    ROLES ADDED:
        - Procurement Catalog Administrator
        - (client)-BPR IRC Recruiting Setup and Maintenance_JOB
        - (client)-BPR IRC Recruiting Setup and Maintenance View All
    
    DATA ACCESS CONFIGURED:
        Row 1:
            - Role: Procurement Catalog
            - Security Context: Business Unit
            - Security Context Value: (client) BU- 75% of time click works, 25% of time Oralce will not
            allow the auto code to save
        
        Row 2:
            - Role: (client)-BPR IRC Recruiting Setup
            - Security Context: Business Unit
            - Security Context Value: (client) BU- 10% of the time Oracle saves the click selection, most likely this step fails because Oracle
    
    PROCUREMENT AGENT ACCESS:
        - Procurement BU: (client) BU
    NOTE: Procurement Agent section currently commented out in code - 
          assumed to be pre-configured before script runs.


TASK LIST:
    Pre-Task:  Setup Procurement Access for User
    Task 1:    Disable Email Notifications
    Task 2:    Update Banner Message
    Task 2.2:  Upload Logo (DISABLED - low success rate)
    Task 3:    Disable ADP Extract Deliveries
    Task 4:    Add IPs to Location-Based Access
    Task 7:    Turn Off PO Communication
    Task 9:    Disable AP Payment Transmission
    Task 10:   Update Corp Card Program to Non-Prod SFTP
    Task 11:   Disable GetThere Configuration
    Task 12:   Remove Receivables Email "From" Values
    Task 14:   Create Sandbox for CIF/PLE (DISABLED - incomplete)
    Task 15:   Update/Remove HireRight Configuration
    Task 16:   Pre-Note: Update JPMC SFTP (sometimes misses second row to delete)
    Task 17:   Create ADMIN User Accounts ((client)s)
    Task 18:   Create Admin Tech User (environment-specific GUID)
    Task 20:   Update Preferred Gender/Absence Links (DISABLED - low success rate)
    Task 21:   Disable Separate Remittance Advice Emails
    Task 22:   Update Checklist URLs (Medical/Leave)
    Task 23:   Workforce Structure - Positions E-Flexfields
    Task 5,6, 19 -all ESS jobs ran at end via either REST API jobs and UI ESS jobs at the end
    
   
DEPENDENCIES:
    - playwright (browser control)
    - post_refresh_automation_helpers (error recovery wrappers)
    - terminal_logger (crash-proof SQLite logging)
    - RESTAPI_ESS/main (REST API job automation)
    - ui_ess_jobs (UI scheduled process automation)

KNOWN ISSUES / DISABLED TASKS:
    - Data Access Row 1 after security context value is selected sometimes Oracle will deselect after clicking OK
    -Data Access Row 2 after security context value is selected most of the time Oracle will deselect after clicking OK or not allow
    - Task 2.2 (Logo Upload): Disabled due to upload/download errors
    - Task 14 (Sandbox CIF/PLE): Incomplete, has some issues
    -Task 16- sometimes misses deleting second row
    - Task 20 (Preferred Gender Links): Low success rate, needs fixes

SESSIONS:
    The script runs in TWO browser sessions to avoid conflicts:
    
    Session 1: Data Access Setup
        - Logs in
        - Runs setup_procurement_access_for_user() -role and data access
        - Closes browser
    
    Session 2: Main Tasks
        - Logs in fresh
        - Runs all enabled tasks
        - Runs REST API jobs or Runs UI ESS jobs
        - Closes browser

DEVELOPMENT NOTES:
    Created: [Original date]
    Last Updated: February 12, 2026-adding documentation
    Developer: Alex Cacaras
    
    This was built incrementally over time with the use of playwright (similar to selenium)
    Creating code and refining codes for each task and testing task at a time as well.
    Each task function preserves the exact click sequence from the original steps for maximum reliability.
    Tried to make as dynamic/flexible as possible.




 ============================================================================
 UPDATE 1.0.1 - REST API + UI RETRY ORCHESTRATION (March 2026)
 ============================================================================
CHANGES IN VERSION 1.0.1:
    - Integrated REST API job submission before UI tasks
    - Smart retry system: UI only runs if REST API fails
    - Return code handling: 0 = success, 1 = failures detected
    - ACL job monitoring with hardcoded UI fallback
    
EXECUTION FLOW:
    1. Session 1: Setup procurement access (UI)
    2. Session 2: Run UI configuration tasks (Task 1-23)
    3. Launch REST API jobs (42+ jobs with timeout tracking)
    4. If REST API returns 1 (failures):
       a. Run ui_ess_jobs.py to retry failed jobs via UI
       b. Run hardcoded ACL jobs if needed, currently acl commented out, better to run manually if restapi fails on them 
    5. Close browser and exit
    
KEY INTEGRATION POINTS:
    - Line ~3836: REST API launch with scenario selection
    - Line ~3911: UI retry trigger based on return code
    - Line ~3913: ACL job hardcoded fallback check
 ============================================================================
 END UPDATE 1.0.1
 ============================================================================
"""

import subprocess
import os
import re
import datetime
from pathlib import Path
import sys
from contextlib import suppress  # Clean way to ignore exceptions without try/except
from urllib.parse import urlparse  # For parsing instance URLs
from pretask_data_access_api import run_fixed_procurement_data_access
# Browser automation library (tools to help with browser control for automation)
from playwright.sync_api import Playwright, sync_playwright, TimeoutError as PWTimeout

# The custom helper utilities file for task execution and visual debugging
from post_refresh_automation_helpers import run_task_safe, screenshot

#---------------------------------
# --- SUBFOLDER / MODULE SETUP ---
#---------------------------------
rest_api_path = Path(__file__).parent / "RESTAPI_ESS"# Define the path to the RESTAPI_ESS subfolder relative to this file
# Append the subfolder to sys.path so Python can find 'main.py' and other modules inside it
sys.path.append(str(rest_api_path))# This allows 'from RESTAPI_ESS import main' to work even if it's not a standard package
#Just did it this way because I had previous code from RESTAPI and just wanted it simple withot adding __init__ file
#not much reason, I think first __init__ failed and I just didn't want to bother trying again
from RESTAPI_ESS import main # Import the main runner from the REST API subfolder
from dotenv import load_dotenv
import os


load_dotenv()
#----------------------
# --- LOGGING SETUP ---
#----------------------
from terminal_logger import setup_terminal_logging, cleanup_old_logs # Imports the custom logger that mirrors terminal output to a SQLite database (crash-proof)
setup_terminal_logging("ui_automation") # Initialize logging for this specific UI session
cleanup_old_logs(days=7)#Remove log databases older than 7 days to save space

#-----------------------------
#---- Global Configuration----
#-----------------------------
PAUSE = 3_500       # milliseconds between steps
DRY_RUN = False      # True = no Save/Commit actions; False = real changes (save) --note: on True it doesn't click save but does all steps

#----------------------------
# ----Instance Detection-----
#----------------------------
#Instance URL - can be set in .env file as TENANT_BASE_URL or hardcoded here
INSTANCE_URL = os.getenv("TENANT_BASE_URL") # <-- change here only
HOME_URL     = f"{INSTANCE_URL}/fscmUI/faces/AtkHomePageWelcome"

# Derive instance label automatically (e.g., DEV8, DEV9, DEV10, TEST)
host =  (urlparse(INSTANCE_URL).hostname or "").lower() #'euum-test-saasfaprod1.fa.ocs.oraclecloud.com'

# Prefer patterns like dev10 / dev9 / test / prod in the hostname
m = re.search(r"(dev\d+|test|prod)\b", host, re.I)
if m:
    INSTANCE_LABEL = m.group(1).upper()        # e.g. 'DEV10'
else:
    # Fallback: last part of first hostname chunk (e.g. (client)-(client) -> DEV10)
    first_part = host.split(".")[0] if host else ""
    INSTANCE_LABEL = (first_part.split("-")[-1] or first_part or "UNKNOWN").upper()

#----------------------------------------
#-----PLAYWRIGHT PERSISTENT PROFILE------
#----------------------------------------
# Used for Playwright persistent profile, stays logged in between runs
#Creates a folder like .pw-profile-euum-test-saasfaprod1-fa-ocs-oraclecloud-com
host_for_profile = (urlparse(INSTANCE_URL).hostname or "").replace(".", "-")
PROFILE_DIR = f".pw-profile-{host_for_profile}"

#------------------------------------
#-------------CREDENTIALS------------
#------------------------------------
# Credentials (prefer env vars; these are fallbacks if env not configured)
FUSION_USERNAME = os.getenv("FUSION_USERNAME")
FUSION_PASSWORD = os.getenv("FUSION_PASSWORD")

# =================================================================
# ----------------------LOGIN HELPERS------------------------------
# =================================================================

def password_login_only(page, instance_url, username, password, PAUSE=3500):
    """Login for instance using pasword and username.
    WHY THIS EXISTS:
        Handles login for instances to not go through SSO
    WHAT IT DOES:
        1. Navigate to login URL
        2. Check if already logged in (no login fields present)
        3. If not logged in: fill username + password + click Sign In
        4. Wait for page to load
    DESIGN DECISION - Check if Already Logged In:
        Playwright persistent context keeps cookies between runs, so might
        already be logged in. If login fields aren't present, just return early.
        Wanted it to be faster not go through login always. Not sure if it always works, no crash but maybe just logs in
        each time.
    """
    def snooze(ms=PAUSE): 
        page.wait_for_timeout(ms)

    host = urlparse(instance_url).hostname or ""

    # For now, just always go straight to the instance URL
    login_url = instance_url

    # 1) Go to login / home page
    page.goto(login_url)
    page.wait_for_load_state("domcontentloaded")
    snooze(600)

    # 2) Fill credentials + Sign In (if login fields are present)
    user_box = page.get_by_role("textbox", name=re.compile(r"^User\s*ID$", re.I))
    pass_box = page.get_by_role("textbox", name=re.compile(r"^Password$", re.I))

    # If we’re already logged in (no login fields), just return
    if user_box.count() == 0 and pass_box.count() == 0:
        return
    
    # 3) Fill credentials and sign in
    user_box.click(); snooze(120)
    user_box.fill(username); snooze(150)

    pass_box.click(); snooze(120)
    pass_box.fill(password); snooze(150)

    page.get_by_role("button", name=re.compile(r"^Sign\s*In$", re.I)).click()
    page.wait_for_load_state("domcontentloaded")
    snooze(800)
    #wrote it like this because it is safest way and doesn't change

#=====================================================
# LOGIN AND HOME
#====================================================
def ensure_logged_in_and_home(page, instance_url, username, password, home_url, PAUSE=3500):
    """
    Ensure user is logged in and navigated to the Fusion home page.
    WHY THIS EXISTS:
        Called at the start of each browser session to guarantee code is in a
        known-good state before running tasks. Handles login + navigation to home.

    WHAT IT DOES:
        1. Call password_login_only() to handle authentication
        2. Wait for page to load
        3. Click "Home" link to normalize to Fusion Home shell
    
    DESIGN DECISION - Suppress Home Click Errors:
        The code sometimes lands on the correct home page and so this ensures we don't crash - if we're already at the correct home,
        the click fails silently and we continue.
        """
    def snooze(ms=PAUSE): page.wait_for_timeout(ms)
    # Native login (no SSO)
    password_login_only(page, instance_url, username, password, PAUSE=PAUSE)
    # Normalize to the Fusion Home shell
    #page.goto(home_url) commented it out because was causing errors after an update but don't need we automatically go home
    page.wait_for_load_state("domcontentloaded")
    snooze()
    # Try to click Home link (might already be there, so suppress errors)
    with suppress(Exception):
        page.get_by_role("link", name="Home", exact=True).click()
        snooze()
        #screenshot(page) -- this is example I left of screenshots and where I placed, left for anyone to see so they know how to add and where

# =====================================================
# Pre-Task: Grant roles + data access for USER
# Runs once after sign-in, before Task 1
# =====================================================
#Sets up procurement roles and data access for a specific user
#Kept mostly simple structured because was under impression wouldn't need to add roles/access so after building simple version just left in case

def setup_procurement_access_for_user(
    page,
    user_search_text: str = "(client)", #change for USER (maybe will do via .env)--kept short because if type full might not come up properly and misclick
    user_link_text: str = "(client) (client)", #change for USER (maybe will do via .env)
    user_login_option: str = "(client).(client)", #change for USER (maybe will do via .env)
    PAUSE: int = 3500,
    DRY_RUN: bool = True,
):
    """
    Configure procurement roles and data access for a user.
    WHY THIS EXISTS:
        After an environment refresh, users lose their roles and data access.
        This function automates re-granting everything needed for procurement tasks.
        I made this section before I was told that roles/data can be given prior.
        Not sure if stil the case so kept in regardless.
        Works fine only one error on data access that happens, mentioned in description at beginning of file.
    WHAT IT DOES:
        1. Navigate to Security Console → Users
        2. Search for and open the user record
        3. Add three procurement-related roles
        4. Configure data access for two role contexts (Procurement Catalog + IRC Recruiting)
        5. (Optional) Set up Procurement Agent access (currently commented out)-- told won't be needed will have role auomatically
        when refreshed so never did much for it.
    KNOWN ISSUES:
        - Data Access Row 1: 25% of time Oracle deselects "(client) BU" after clicking OK
        - Data Access Row 2: 90% of time Oracle deselects "(client) BU" or doesn't save
        - These are Oracle UI quirks - the automation code is correct but Oracle doesn't respond correctly
    
    DESIGN DECISION - User Parameters:
        Takes user_search_text, user_link_text, user_login_option as parameters.
        TODO: Could move these to .env file for easier configuration. Just never changed it but commented the idea long ago.
    """
    def snooze(ms=PAUSE): #defining wait as snooze
        page.wait_for_timeout(ms)
        
    def try_click(loc, timeout=9000):
        """Helper: Try to click element, return True if successful, False otherwise."""
        try:
            loc.wait_for(state="visible", timeout=timeout)
            loc.click(timeout=timeout)
            return True
        except Exception:
            return False

    def type_in_placeholder(text: str):
        """Helper: Find the Oracle LOV search box and type into it."""
        box = page.get_by_placeholder("Enter 3 or more characters to")
        box.click()
        box.fill(text)
        return box
    
    # ------------------------------------------------------------------
    # 1) Open Security Console → Users → open  user record
    # ------------------------------------------------------------------
    # Try to click Navigator (sometimes it's in a td, sometimes it's a direct link)
    try:
        page.locator("td").filter(has_text="Navigator").first.click()
        snooze()
    except Exception:
        pass

    try_click(page.get_by_role("link", name="Navigator"))
    snooze()
    #screenshot(page)
    
    # Click Tools tile
    try_click(page.get_by_title("Tools", exact=True))
    snooze()
    # Click Security Console
    try_click(page.get_by_role("link", name="Security Console"))
    snooze()
    #screenshot(page)
    # Click Users tile
    try_click(page.get_by_title("Users"))
    snooze()
    # Dismiss Oracle warning dialog if present (e.g. "Import User and Role..." warning)
    try:
        ok_btn = page.get_by_role("button", name="OK")
        if ok_btn.count() > 0:
            ok_btn.first.click()
            page.wait_for_timeout(2000)
            print("[Session 1] Dismissed Oracle warning dialog")
    except Exception:
        pass

    try_click(page.get_by_title("Users"))
    snooze()


     # Click the search filter area 
    page.locator("td").filter(has_text="*SearchAllActive").nth(1).click()
    snooze()

    box = type_in_placeholder(user_search_text)
    box.press("Enter")
    snooze()
    #screenshot(page)

    try_click(page.get_by_role("link", name=user_link_text))
    snooze()
    #screenshot(page)

    try_click(page.get_by_role("button", name="Edit"))
    snooze()

    #-------------------------------------------------------------------
    # 2) Add roles to user
    # ------------------------------------------------------------------
    def add_role(role_text: str):
        """
        Add a single role to the user.
        
        WHAT IT DOES:
            1. Click "Add Role" button
            2. Search for role by name in LOV popup
            3. Click "Add Role Membership" (or Cancel in DRY_RUN)
        
        DESIGN DECISION - DRY_RUN Handling:
            In DRY_RUN mode, still go through steps just don't save.
        """
        try_click(page.get_by_role("button", name="Add Role"))
        snooze()
        box = type_in_placeholder(role_text)
        snooze()
        #screenshot(page)
        page.locator('[id="__af_Z_window"]').get_by_role("link", name="Search").click()
        snooze()
        #screenshot(page)
        if not DRY_RUN:
            # Actually add the role
            try_click(page.get_by_role("button", name="Add Role Membership"))
            snooze()
            #screenshot(page)
        else:
            print(f"[Roles] DRY RUN — would add role: {role_text}")
            # Close Add Role dialog without saving? keep simple:
            try:
                page.get_by_role("button", name="Cancel").click()
                snooze()
                #screenshot(page)
            except Exception:
                pass
        #adds the following roles:
    # 2.1 Procurement Catalog Administrator
    add_role("Procurement Catalog Administrator")

    # 2.2 (client)-BPR IRC Recruiting Setup and Maintenance_JOB
    add_role("(client)-BPR IRC Recruiting Setup and Maintenance_JOB")

    # 2.3 (client)-BPR IRC Recruiting Setup and Maintenance View All
    add_role("(client)-BPR IRC Recruiting Setup and Maintenance View All")

    if not DRY_RUN:
        try_click(page.get_by_role("button", name="Done"))
        snooze()
        #screenshot(page)
        try_click(page.get_by_role("button", name="Save and Close"))
        snooze()
        try_click(page.get_by_role("button", name="Done"))
        snooze()
        #screenshot(page)
    else:
        print("[Roles] DRY RUN — skipping Save and Close / Done on user roles")

    
        
    """
    # ------------------------------------------------------------------
    # 3) Manage Procurement Agents (give user agent access in (client) BU)
    # ------------------------------------------------------------------
     # Navigate to Setup and Maintenance → Tasks → Search
    try_click(page.get_by_role("link", name="Settings and Actions"))
    snooze()
    try_click(page.get_by_role("link", name="Setup and Maintenance"))
    snooze()
    #screenshot(page)
    try_click(page.get_by_role("link", name="Tasks")); snooze()
    try_click(page.locator("[id='__af_Z_window']").get_by_role("link", name="Search")); snooze()
    '''---------------------------------------------------------------------------------
    THIS PART HAS BEEN COMMENTED OUT BECAUSE WAS TOLD WILL BE ADDED ALREADY BEFORE CODE RUNS

    Kept the code here for reference in case it's needed in the future.
    WHAT THIS WOULD DO:
        1. Search for "Manage Procurement Agents"
        2. Create new agent record for user
        3. Set Procurement BU to "(client) BU"
        4. Set Agent to the user being configured
        5. Configure access levels for different procurement functions:
           - Manage Requisitions: Level 2 (Access to Other Agents' Documents)
           - Manage Purchase Orders: Level 3 (Full Access)
           - Manage Purchase Agreements: Level 3 (Full Access)
           - Manage Negotiations: Level 2 (Access to Other Agents' Documents)
           - Manage Sourcing Programs: Level 2 (Access to Other Agents' Documents)
           - Manage Supplier Qualifications: Level 2 (Access to Other Agents' Documents)
           - [Additional category]: Level 2 (Access to Other Agents' Documents)
    --------------------------------------------------------------------------------------

    search_label = page.get_by_label("", exact=True)
    search_label.click()
    search_label.fill("Manage Proc")
    search_label.press("Enter")
    snooze()

    try_click(page.get_by_role("button", name="Search"))
    snooze()
    try_click(page.get_by_role("link", name="Manage Procurement Agents"))
    snooze()

    try_click(page.get_by_role("button", name="Create"))
    snooze()

    # Procurement BU
    cb_bu = page.get_by_role("combobox", name="Procurement BU")
    cb_bu.click()
    cb_bu.fill("(client) B")
    page.get_by_role("option", name="(client) BU").click() #fix
    snooze()

    # Agent
    cb_agent = page.get_by_role("combobox", name="Agent", exact=True)
    cb_agent.click()
    cb_agent.fill("(client), (client)(client)")
    page.get_by_role("option", name="(client), (client)").click()
    snooze()

    # Access levels
    page.get_by_role("row", name="Manage Requisitions None").get_by_label("Access to Other Agents'").select_option("2")
    page.get_by_role("row", name="Manage Purchase Orders None").get_by_label("Access to Other Agents'").select_option("3")
    page.get_by_role("row", name="Manage Purchase Agreements").get_by_label("Access to Other Agents'").select_option("3")
    page.get_by_role("row", name="Manage Negotiations None").get_by_label("Access to Other Agents'").select_option("2")
    page.get_by_role("row", name="Manage Sourcing Programs None").get_by_label("Access to Other Agents'").select_option("2")
    page.get_by_role("row", name="Manage Supplier Qualifications None Access to Other Agents' Documents").get_by_label("Access to Other Agents'").select_option("2")
    page.get_by_role("cell", name="None Access to Other Agents'").get_by_label("Access to Other Agents'").select_option("2")
    snooze()

    if not DRY_RUN:
        try_click(page.get_by_role("button", name="Save and Close"))
        snooze()
        try_click(page.get_by_role("button", name="Done"))
        snooze()
    else:
        print("[Agents] DRY RUN — skipping Save and Close / Done")
    '''
    # ------------------------------------------------------------------
    # 4) Manage Data Access for Users(has some issue where after typing in and selecting Oracle will not acknowledge the bot did that)
    # ------------------------------------------------------------------
    # NOTE: Has issues where after typing and selecting, Oracle sometimes
    #       doesn't acknowledge the selection (known Oracle UI quirk)

    # Search for "Manage Data Access for Users"
    search_label = page.get_by_label("", exact=True)
    search_label.click()
    search_label.fill("Manage Data")
    snooze()
    #screenshot(page)

    try_click(page.get_by_role("button", name="Search"))
    snooze()
    try_click(page.get_by_role("link", name="Manage Data Access for Users"))
    snooze()
    #screenshot(page)

    try_click(page.get_by_role("button", name="Create"))
    snooze()
    #screenshot(page)

    # First row: Procurement Catalog + (client) BU
    # First row: Procurement Catalog + (client) BU
    tbl = page.get_by_role("table", name="Create Data Access for Users")
    # User Name field
    user_cell = tbl.get_by_label("User Name")
    user_cell.click()
    user_cell.fill(user_search_text) #possible that type instead of fill avoids the backspace requirement not sure
    user_cell.press("Backspace")  # <<< REQUIRED for Oracle autocomplete, otherwise Oracle won't acknowledge our typing(fill)
    page.get_by_role("option", name=user_login_option).click()
    snooze()
    # Role field
    role_cell = tbl.get_by_label("Role")
    role_cell.click()
    role_cell.fill("Proc") #have to type the beginning for results to show, if fullwon't show even with backspace
    role_cell.press("Backspace")  # <<< REQUIRED for Oracle autocomplete, otherwise Oracle won't acknowledge code fill
    page.get_by_role("option", name="Procurement Catalog").click()
    snooze()
    # Security Context = Business Unit (option value "5") typically is option 5, if Oracle changes then have to change option number
    #better way would be to read the name but wasn't able to get that, at least in this simpler format
    tbl.get_by_label("Security Context", exact=True).select_option("5")
    page.get_by_title("Search: Security Context Value").click()
    snooze()
    page.get_by_text("(client) BU").click()
    snooze()
    #screenshot(page)

    if not DRY_RUN:
        try_click(page.get_by_role("button", name="Save and Close"))
        snooze()
        #screenshot(page)

    # Second row: (client)-BPR IRC Recruiting Setup + (client) BU
    try_click(page.get_by_role("button", name="Create"))
    snooze()
    #screenshot(page)

    # User Name second row
    second_user_cell = page.get_by_role(
        "cell",
        name="User Name Search: User Name Autocompletes on TAB",
        exact=True
    ).get_by_label("User Name")

    second_user_cell.click()
    #second_user_cell.click(user_search_text[-1])
    second_user_cell.type('(client).(client)')# Type manually to trigger autocomplete, had to do actual name to make it work and with type
    #the second row was very strange, this was only way it was working, will have to change to whatever username you need, don't fill full name
    snooze()

    page.get_by_role("option", name=user_login_option).click()
    snooze()
    #screenshot(page)

    # Role field (second row - even more specific selector because of dynamic cell name)
    second_role_cell = page.get_by_role(
        "cell",
        name="(client).(client) User Name Search: User Name Autocompletes on TAB Role Search" #will have to adjust based on name
        # if we jsut did like this page.get_by_label("Role") without hardcode, code might misclick,this section finicky
    ).get_by_label("Role")

    second_role_cell.click()
    second_role_cell.type("(client)-BPR IR")# Type manually to trigger autocomplete
    snooze()
    page.get_by_role("option", name="(client)-BPR IRC Recruiting Setup").click()
    snooze()

    # Security context (client) BU
    page.get_by_role(
        "cell", name="(client).(client) User Name Search: User Name Autocompletes on TAB (client)-BPR" #have to adjust based on name or add feature for dynamic name if works
         #second row very finicky so these dynamic stuff sometimes fail that is why mostly hardcoded
         # Security Context = Business Unit (option value "5")
        ).get_by_label("Security Context", exact=True).select_option("5")
    snooze()
    page.get_by_title("Search: Security Context Value").first.click()
    snooze()
    page.get_by_role("cell", name="(client) BU").nth(1).click()
    


    snooze()
    #screenshot(page)

    if not DRY_RUN:
        try_click(page.get_by_role("button", name="Save and Close"))
        snooze()
        try_click(page.get_by_role("button", name="Done"))
        snooze()
        #screenshot(page)
    else:
        print("[Data Access] DRY RUN — skipping Save and Close / Done")

    print(f"[Setup] Procurement roles & data access configured for {user_link_text}. DRY_RUN={DRY_RUN}")
    #log out log in
"""
        # ------------------------------------------------------------------
    # 4) Data Access via REST API (replaces flaky UI data access section)
    # ------------------------------------------------------------------
    """
    WHY THIS REPLACED THE OLD UI SECTION:
        The original "Manage Data Access for Users" browser automation was the
        weakest part of the pretask. Oracle autocomplete and row selection were
        inconsistent, especially on the second row.

        The UI role addition is kept but now replacing data access with more reliable REST API.

    FLOW:
        1) UI adds required roles above
        2) This REST step grants:
           - Procurement Catalog Administrator / Business unit / (client) BU
           - (client)-BPR IRC Recruiting Setup and Maintenance_JOB / Business unit / (client) BU
        3) If a row already exists, the REST helper will skip it
        4) If Oracle has not yet recognized the newly-added role, the REST API
           may still reject the row. In that case, add a short wait and retry.

    DESIGN DECISION:
        We now use confirmed internal Oracle role codes in the REST helper,
        so there is no longer any need for role mapping or spreadsheet input.
    """
    print("\n[Setup] Starting REST data access step...")

    # Give Oracle a moment after UI role assignment before REST data access POSTs.
    if not DRY_RUN:
        snooze(3000)

    try:
        rest_results = run_fixed_procurement_data_access(
            target_username=user_login_option,
            dry_run=DRY_RUN,
        )

        posted  = sum(1 for r in rest_results if r["status"] == "posted")
        skipped = sum(1 for r in rest_results if r["status"] == "skipped")
        failed  = sum(1 for r in rest_results if r["status"] == "failed")
        dry     = sum(1 for r in rest_results if r["status"] == "dry_run")

        print(
            f"[Setup] REST data access step complete for {user_login_option}. "
            f"Posted={posted} Skipped={skipped} Failed={failed} DryRun={dry}"
        )

    except Exception as e:
        print(f"[Setup] REST data access step FAILED for {user_login_option}: {e}")
        raise

    print(f"[Setup] Procurement roles + REST data access configured for {user_link_text}. DRY_RUN={DRY_RUN}")
# =====================================================
# Task 1 — Disable email notifications via Worklist
# =====================================================
def task1_disable_notifications(page, PAUSE=3500, DRY_RUN=True, home_url=None):
    def snooze(ms=PAUSE): page.wait_for_timeout(ms)
    def try_click(loc, timeout=6000):
        try:
            loc.wait_for(state="visible", timeout=timeout)
            loc.click(timeout=timeout); return True
        except Exception:
            return False

    '''
    """
Disable email notifications via Worklist.

WHAT IT DOES:
        1. Open Notifications panel
        2. Click "Show All"
        3. Open Worklist popup
        4. Navigate to Administration tab
        5. Set Notification Mode to "None" (value "1")
        6. Save changes (or skip in DRY_RUN)
DESIGN DECISION - Flexible Selectors:
    Originally had simpler selectors, but notification count changes
    (e.g., "Notifications (3 unread)" vs "Notifications (0 unread)")
    caused the automation to break. Now uses regex to match any count.
"""
   '''

    # --- Notifications (covers 0 or N unread) ---
    opened = (
        try_click(page.get_by_role("link",  name=re.compile(r"^Notifications \(\d+ unread\)$", re.I))) or
        try_click(page.get_by_role("link",  name=re.compile(r"^Notifications \(0 unread\)$", re.I))) or
        try_click(page.get_by_role("button",name=re.compile(r"^Notifications$", re.I))) or
        try_click(page.get_by_role("link",  name=re.compile(r"^Notifications$", re.I)))
    )
    if not opened:
        raise RuntimeError("Couldn't open Notifications.")
    snooze()
    #screenshot(page)

    # --- Show All ---
    if not (
        try_click(page.get_by_role("button", name=re.compile(r"^Show All$", re.I))) or
        try_click(page.get_by_role("link",   name=re.compile(r"^Show All$", re.I)))
    ):
        raise RuntimeError("Couldn't find 'Show All'.")
    snooze()
    screenshot(page, "task1")

    # --- Worklist popup ---
    with page.expect_popup() as pop_info:
        if not try_click(page.get_by_role("button", name=re.compile(r"^Worklist$", re.I))):
            raise RuntimeError("Worklist button not found.")
    work = pop_info.value
    work.wait_for_load_state("domcontentloaded")
    snooze()
    #screenshot(page)

    # --- Administration tab ---
    # Sometimes need to click menu first to reveal tabs
    with suppress(Exception):
        work.get_by_role("menuitem").first.locator("div").click()
        snooze()
        #screenshot(page)

    if not (
        try_click(work.get_by_text(re.compile(r"\bAdministration\b", re.I))) or
        try_click(work.get_by_role("menuitem", name=re.compile(r"Administration", re.I)))
    ):
        raise RuntimeError("Administration not reachable in Worklist.")
    snooze()
    screenshot(page, "task1")

    # --- Notification Mode = None (value "1") ---
    mode = work.get_by_label(re.compile(r"^Notification Mode$", re.I))
    mode.scroll_into_view_if_needed()
    work.wait_for_timeout(500)
    mode.select_option("1") #1 always = none
    snooze()
    screenshot(page, "task1")


    if not DRY_RUN:
        try_click(work.get_by_role("button", name=re.compile(r"^Save$", re.I)))
        snooze()
    else:
        print("[Task 1] Dry run: skipped Save")

    work.close() #close popup window
    snooze()
    #screenshot(page)

    # --- Back Home ---
    with suppress(Exception):
        try_click(page.get_by_role("link", name="Home", exact=True))
        snooze()
        #screenshot(page)

    print(f"[Task 1] Notifications set to None (value=1). DRY_RUN={DRY_RUN}")



# =====================================================
# Task 2 — Update Banner Message (STRICT sequence)
# =====================================================
def task2_banner_message(page, PAUSE=3500, DRY_RUN=True, instance_label=None, STRICT=True):
    """
    Exact sequence required by user:
      1) Profile Option Code = FND_BANNER
      2) Search
      3) New
      4) Profile Level = 0 (Site)
      5) Profile Value = "<Dev N> Refreshed from PROD on <DD Mon>"
      6) Save
      7) Save and Close

    """
    import re, datetime
    from contextlib import suppress

    def snooze(ms=PAUSE): page.wait_for_timeout(ms)
    def must_click(loc, timeout=8000):
        loc.wait_for(state="visible", timeout=timeout)
        loc.click(timeout=timeout)

        # derive label if not passed (e.g., DEV10)
    if not instance_label:
        instance_label = INSTANCE_LABEL

    # Make it pretty: DEV10 -> "Dev 10"
    friendly_label = re.sub(r"^DEV(\d+)$", r"Dev \1", instance_label, flags=re.I)

    # Format like: "Dev 10 Refreshed from PROD on 12 Nov"
    banner_text = f"{friendly_label} Refreshed from PROD on {datetime.date.today():%d %b}"


    # --- Navigate to Setup and Maintenance ---
    must_click(page.get_by_role("link", name="Settings and Actions")); snooze()
    #screenshot(page)
    must_click(page.get_by_role("link", name="Setup and Maintenance")); snooze()
    #screenshot(page)
    must_click(page.get_by_role("link", name="Tasks")); snooze()
    #screenshot(page)
    # --- Search for Manage Administrator Profile ---
    must_click(page.locator("[id='__af_Z_window']").get_by_role("link", name="Search")); snooze()
    first_input = page.get_by_label("", exact=True)
    first_input.click(); snooze()
    first_input.fill("Manage Administrator Profile"); snooze()
    #screenshot(page)
    must_click(page.get_by_role("button", name="Search")); snooze()
    must_click(page.get_by_role("link", name="Manage Administrator Profile")); snooze()
    screenshot(page, "task2")

    # --- EXACT STEPS ---
    # 1) Profile Option Code
    poc = page.get_by_role("textbox", name="Profile Option Code")
    poc.click(); snooze()
    poc.fill("FND_BANNER"); snooze()
    #screenshot(page)

    # 2) Search 
    must_click(page.get_by_role("button", name="Search", exact=True)); snooze()

    # 3) New (strict order)
    clicked_new = False
    with suppress(Exception):
        page.get_by_role("button", name="New").click()
        clicked_new = True
    snooze()
    #screenshot(page)

    # If New wasn’t present but STRICT demanded it, then continue with a note
    if not clicked_new and STRICT:
        print("[Task 2][Note] 'New' button not found — editing existing value row instead.")

    # 4) Profile Level = "0" (Site) — only relevant if New created a row
    if clicked_new:
        with suppress(Exception):
            page.get_by_label("Profile Level", exact=True).select_option("0")
            snooze(200)
            #screenshot(page)

    # 5) Profile Value
    pv = page.get_by_role("textbox", name="Profile Value")
    pv.click(); snooze()
    with suppress(Exception):
        pv.press("ControlOrMeta+A"); snooze(120)
    pv.fill(banner_text); snooze()
    screenshot(page, "task2")

    if DRY_RUN:
        # Don’t commit — click Cancel so nothing persists
        with suppress(Exception):
            page.get_by_role("button", name="Cancel").click(); snooze()
        print(f"[Task 2] DRY_RUN=True → would set Profile Value to: {banner_text!r}")
    else:
        # 6) Save
        with suppress(Exception):
            page.get_by_role("button", name="Save", exact=True).click(); snooze(450)
        # 7) Save and Close
        page.get_by_role("button", name="Save and Close").click(); snooze()
        print(f"[Task 2] Banner message set to: {banner_text!r}")

    # Back Home (best-effort)
    with suppress(Exception):
        page.get_by_role("link", name="Home", exact=True).click(); snooze()
        #screenshot(page)
# =====================================================
# Task 2.2 — Create Sandbox (Appearance) and upload instance-specific Logo THIS TASK DOES NOT WORK TO THE FULLEST SO DISCONTINUED HAS ERROR WHEN UPLOAD/DOWNLOAD    
# =====================================================
# THIS TASK DOES NOT WORK TO THE FULLEST SO DISCONTINUED HAS ERROR WHEN UPLOAD/DOWNLOAD    
#The idea was have branding folder with sub folders for different instances. Would upload the branding logo for each dev respective to what 
#env the P2T automation is happening in. This way there is folder for each logo for each dev but upload and download was error in the browser
def task2_2_update_logo_theme(
    page,
    PAUSE=3500,
    DRY_RUN=True,
    image_root_dir="branding"  # expects subfolders like branding/Dev 10/, branding/Dev 9/, etc.
):
    """
    Navigator → Configuration → Sandboxes → tick 'Appearance' → Create Sandbox 'Logo' → Create and Enter
    → Tools → Appearance → pick theme (index 0) → upload latest logo file from branding/<Dev N>/ → Apply
    → set Theme Name 'Logo' → OK → Publish sandbox.

    Instance-aware:
      - Tools/Sandboxes URL derived from INSTANCE_URL
      - Logo file auto-picked from branding/<Dev N>/ newest file (jpg/png/svg/gif/webp)
    """
    import os, re, glob
    from contextlib import suppress

    def snooze(ms=PAUSE): page.wait_for_timeout(ms)

    def try_click(loc, timeout=8000):
        try:
            loc.wait_for(state="visible", timeout=timeout)
            loc.click(timeout=timeout)
            return True
        except Exception:
            return False

    # Build the instance Tools→Sandboxes URL dynamically
    instance_tools_url = f"{INSTANCE_URL}/fscmUI/faces/FuseOverview?fndGlobalItemNodeId=itemNode_tools_sandboxes"

    # Map INSTANCE_LABEL (e.g., DEV10) to a friendly folder name (e.g., "Dev 10")
    friendly_label = re.sub(r"^DEV(\d+)$", r"Dev \1", INSTANCE_LABEL, flags=re.I)

    # Find newest image in branding/<friendly_label>/
    logo_dir = os.path.join(image_root_dir, friendly_label)
    candidates = []
    with suppress(Exception):
        for ext in ("*.jpg", "*.jpeg", "*.png", "*.gif", "*.webp", "*.svg"):
            candidates.extend(glob.glob(os.path.join(logo_dir, ext)))
    if not candidates:
        raise FileNotFoundError(
            f"No logo files found for {friendly_label!r} in {logo_dir!r}. "
            "Expected something like branding/Dev 10/Dev 10.jpg"
        )
    latest_logo = max(candidates, key=os.path.getmtime)
    print(f"[Task 2.2] Using logo file: {latest_logo}")

    # ----------------- Create Sandbox with Appearance tool -----------------
    try_click(page.get_by_role("link", name="Navigator")); snooze()
    # Click "Configuration" tile/link
    if not try_click(page.get_by_title("Configuration", exact=True)):
        try_click(page.get_by_role("link", name=re.compile(r"^Configuration$", re.I)))
    snooze()

    try_click(page.get_by_role("link", name="Sandboxes")); snooze()

    # Tick the 'Appearance' row
    try_click(page.locator("tr").filter(has_text=re.compile(r"^Appearance$", re.I)).locator("label")); snooze()

    try_click(page.get_by_role("button", name="Create Sandbox")); snooze()

    name_box = page.get_by_role("textbox", name="Name")
    name_box.click(); snooze()
    name_box.fill("Logo"); snooze()

    try_click(page.get_by_role("button", name="Create and Enter")); snooze()

    # Some tenants land elsewhere; go explicitly to Sandboxes Tools page
    with suppress(Exception):
        page.goto(instance_tools_url); snooze()

    # Tools → Appearance
    try_click(page.get_by_role("menuitem", name="Tools").locator("div")); snooze()
    try_click(page.locator("[id='__af_Z_window']").get_by_text("Appearance")); snooze()

    # Optional theme/skin select; had select_option("0")
    with suppress(Exception):
        # Prefer a role-based combobox if present; else fall back to the known name attr
        if page.get_by_role("combobox").count():
            page.get_by_role("combobox").first.select_option("0")
        else:
            page.locator("select[name*='soc']").first.select_option("0")
        snooze()

    
    # Upload the logo file: in your UI the "File" button is the file input,
    # so we can call set_input_files() directly.
    upload_btn = page.get_by_role("button", name=re.compile(r"^File$", re.I))
    upload_btn.set_input_files(latest_logo)
    snooze()
   

    # Apply theme
    try_click(page.get_by_role("button", name="Apply")); snooze()

    # Theme Name = "Logo"
    tn = page.get_by_role("textbox", name=re.compile(r"^Theme Name$", re.I))
    tn.click(); snooze()
    tn.fill("Logo"); snooze()
    try_click(page.get_by_role("button", name="OK")); snooze()

    # Open sandbox menu by name and publish (or skip in DRY_RUN)
    try_click(page.get_by_role("menuitem", name="Logo").locator("div")); snooze()

    if DRY_RUN:
        print(f"[Task 2.2] DRY_RUN=True → uploaded {os.path.basename(latest_logo)!r} and set theme, skipping Publish.")
    else:
        # Publish flow per clicks
        try_click(page.get_by_text("Publish", exact=True)); snooze()
        with suppress(Exception):
            try_click(page.get_by_role("button", name="Yes")); snooze()
        with suppress(Exception):
            try_click(page.get_by_role("button", name="Publish")); snooze()
        with suppress(Exception):
            try_click(page.get_by_role("button", name="Yes")); snooze()
        print(f"[Task 2.2] Published sandbox 'Logo' with {os.path.basename(latest_logo)!r}")

    # Home
    with suppress(Exception):
        try_click(page.get_by_role("link", name="Home", exact=True)); snooze()

# =====================================================
# Task 3 — End-date + delete ADP extract deliveries (Payslip / US Third Party *)#fixed delete row
# =====================================================
#Disables ADP extract deliveries by:
#   1. Setting End Date to 01/01/2001 (effectively disables future runs)
#   2. Deleting the delivery row entirely (cleaner approach)
#
# Covers:
#   - Payslip → ADP_SC_GarnOnly_Payslip
#   - US Third Party Monthly Tax → ADP SFTP
#   - US Third Party Periodic Tax → ADP Tax SFTP (deletes twice)
#   - US Third Party Quarterly Tax → ADP Tax SFTP

def task3_disable_adp_deliveries(page, PAUSE=3500, DRY_RUN=True, is_retry=False):
    """
    End-date and delete ADP extract deliveries to prevent them from running.
    
    WHAT IT DOES:
        For each ADP-related extract:
        1. Search for the extract by name
        2. Open the Deliver tab
        3. Set End Date to 01/01/2001 (past date = won't run)
        4. Delete the delivery row entirely
        5. Validate and Done
    End date and delete due to the manual process always being like that.
    Provides safety net.

    Periodic Tax Extract:
        Sometimes needs TWO delete attempts (Oracle UI quirk). The code handles
        this by calling delete_delivery_row_by_text() twice with a category
        click in between to refresh the view.
        This was issue before but solved with click in between and doing the two delete attempts.
        Some weird Oracle thing.

    """
    import re
    from contextlib import suppress

    def snooze(ms=PAUSE): page.wait_for_timeout(ms)
    def try_click(loc, timeout=9000):
        """
        Helper: Try to click element, return True if successful.
        """
        try:
            loc.wait_for(state="visible", timeout=timeout)
            loc.click(timeout=timeout)
            return True
        except Exception:
            return False
    # ------------------------------------------
    # HELPER FUNCTIONS
    # ------------------------------------------

    def set_end_date_and_ok(delivery_link_name, end_date="01/01/2001"):
        """
        Open a delivery row, set its End Date, and click OK.
        
        WHY 01/01/2001:
            Setting End Date to a past date ensures the delivery won't run.
            This is a safety measure in addition to deleting the row. 
            This was part of manual process originally as well.
        """
        # Open specific delivery row → set End Date → OK
        #click link to open
        try_click(page.get_by_role("link", name=re.compile(rf"^{re.escape(delivery_link_name)}$", re.I))); snooze(200)
        # Fill End Date field
        end_box = page.get_by_role("textbox", name=re.compile(r"^End Date$", re.I))
        end_box.click(); snooze(120)
        with suppress(Exception):
            end_box.press("ControlOrMeta+A"); snooze(80) #have to do ctrl A to properly replace, is recurring theme through code this was workaround for many simple clicks/typing that are generally easy but throigh automation code was getting blocked
        end_box.fill(end_date); snooze(150)
        try_click(page.get_by_role("button", name=re.compile(r"^OK$", re.I))); snooze(250)
    def expand_categories_if_needed():
        """
        Expand Report Categories if collapsed.
        
        WHY THIS EXISTS:
            Oracle sometimes collapses the category tree, hiding delivery rows.
            This ensures the rows are visible before we try to delete them.
        """
        with suppress(Exception):
            try_click(page.get_by_role("button", name=re.compile(r"^Expand Report Categories$", re.I)))
            snooze(150)

    def delete_delivery_row_by_text(row_text):
        """
        Delete a delivery row by visible text.
        
        WHAT IT DOES:
            1. Find the table cell containing row_text (using has_text filter)
            2. Click the cell's inner span to select the row
            3. Wait 3 seconds for Oracle to enable Delete button
            4. Click the Delete button (nth(2) based on codegen pattern)
            5. Confirm deletion with Yes/OK
        """
        if DRY_RUN:
            print(f"[Task 3] DRY_RUN=True → skipping delete of '{row_text}'.")
            return
       
        if is_retry:
            try:
                row_exists = page.get_by_role("cell", name=row_text).count() > 0
                if not row_exists:
                    print(f"[Task 3] RETRY: '{row_text}' already deleted, skipping")
                    return
            except Exception:
                pass  # if check fails, try the delete anyway

        expand_categories_if_needed()
        
        print(f"[Task 3] Looking for row containing: '{row_text}'")

                        # METHOD 1: Look specifically in the Additional Details table
        try:
            print(f"[Task 3] Looking for '{row_text}' in Additional Details table...")
            
            # Click Additional Details heading to activate section
            with suppress(Exception):
                heading = page.get_by_role("heading", name=re.compile(r"Additional Details", re.I))
                if heading.count() > 0:
                    heading.first.click()
                    snooze(500)
            
            # Try to find the cell that contains both the row text and "Extract Delivery Mode"
            target = page.get_by_role("cell", name=re.compile(rf"{re.escape(row_text)}.*Extract Delivery Mode", re.I))
            
            if target.count() == 0:
                # Fallback: just look for cell with the row text after the heading
                target = page.locator("role=cell").filter(has_text=row_text)
            
            print(f"[Task 3] Found {target.count()} matching cells...")
            
            if target.count() > 0:
                target.last.click()
                snooze(3000)
            
            print(f"[Task 3] Waiting for Oracle to enable Delete button...")
            
            # Delete button
            delete_btns = page.get_by_role("button", name=re.compile(r"^Delete$", re.I))
            if delete_btns.count() >= 3:
                delete_btns.nth(2).click()
            else:
                delete_btns.last.click()
            snooze(1000)
            screenshot(page, "task3")
            
            try_click(page.get_by_role("button", name=re.compile(r"^(Yes|OK)$", re.I)))
            snooze(200)
            print(f"[Task 3]  Successfully deleted '{row_text}'")
            return
        except Exception as e:
            print(f"[Task 3] Method 1 failed: {e}")

        # METHOD 2: Fallback
        try:
            print(f"[Task 3] Trying fallback method...")
            row = page.locator("tr").filter(has_text=row_text).first
            
            if row and row.count() > 0:
                row.click()
                print(f"[Task 3] (Fallback) Clicked row, waiting for Oracle...")
                snooze(3000)
                
                delete_btns = page.get_by_role("button", name=re.compile(r"^Delete$", re.I))
                if delete_btns.count() >= 3:
                    delete_btns.nth(2).click()
                else:
                    delete_btns.last.click()
                snooze(500)
                screenshot(page, "task3")
                
                try_click(page.get_by_role("button", name=re.compile(r"^(Yes|OK)$", re.I)))
                snooze(200)
                print(f"[Task 3]  (Fallback) Successfully deleted '{row_text}'")
                return
        except Exception as e:
            print(f"[Task 3] Fallback failed: {e}")
        
        print(f"[Task 3]  WARNING: could not delete row containing '{row_text}'.")
        failed_deletes.append(row_text)


    def ldg_us():
        """
        Set Legislative Data Group filter to "US Legislative Data Group".
        
        DESIGN DECISION - Two Approaches:
            Method 1: Modern combobox (preferred)
                - Uses accessible combobox role
                - More reliable on newer Oracle versions
            
            Method 2: Fallback span/anchor pattern
                - For older Oracle UI versions
                - Uses specific text pattern matching
                -just second option if first doesn't work
        """
        with suppress(Exception):
            #Method 1: Prefer role-based combobox
            ldg = page.get_by_role("combobox", name=re.compile(r"Legislative Data Group", re.I))
            if ldg.count() > 0:
                ldg.first.click(); snooze(120)
                try_click(page.get_by_role("option", name=re.compile(r"^US Legislative Data Group$", re.I))); snooze(150)
                return
        #Method 2: Fallback to older label/anchor pattern
        with suppress(Exception):
            page.locator("span").filter(
                has_text=re.compile(r"^US Legislative Data Group\s+Legislative Data Group$", re.I)
            ).locator("a").click()
            snooze(150)
            try_click(page.get_by_role("option", name=re.compile(r"^US Legislative Data Group$", re.I))); snooze(150)

    def search_by_name(name_text):
        """
        Search for an extract by name with US Legislative Data Group filter.
        
        WHAT IT DOES:
            1. Ensure filter panel is visible (click Show Filters if needed)
            2. Type extract name into Name field
            3. Set Legislative Data Group to "US Legislative Data Group"
            4. Click Search button
        
        DESIGN DECISION - Smart Filter Panel Check:
            Only clicks "Show Filters" if the Name textbox isn't visible.
            Never clicks "Hide Filters" - this prevents accidentally hiding
            the panel when it's already open. Sometimes it is hidden, sometimes it isn't.
        
        DESIGN DECISION - Search Region Scoping:
            Looks for Search button inside page.get_by_role("search") region first.
            This is more specific than just clicking any "Search" button on the page,
            preventing accidental clicks on other search functionality.
            Had issues with clicking wrong search button.
        """
        print(f"[Task 3] Searching for {name_text!r}")
        # Make sure the filter panel is visible (only click Show Filters, never Hide Filters)
        with suppress(Exception):
            # If Name textbox isn't visible, click Show Filters
            if page.get_by_role("textbox", name=re.compile(r"^Name$", re.I)).count() == 0:
                try_click(page.get_by_role("link", name=re.compile(r"^Show Filters$", re.I)))
                snooze(200)

        # Type into Name field
        name_box = page.get_by_role("textbox", name=re.compile(r"^Name$", re.I))
        name_box.click(); snooze(120)
        with suppress(Exception):
            name_box.press("ControlOrMeta+A"); snooze(80)
        name_box.fill(name_text); snooze(200)

        # Set Legislative Data Group to US Legislative Data Group
        ldg_us()

        # Click Search 
        search_region = page.get_by_role("search")
        if search_region.count() > 0:
            btn = search_region.get_by_role("button", name=re.compile(r"^Search$", re.I))
            try_click(btn); snooze(500)
        else:
            # Fallback: plain button, just in case
            try_click(page.get_by_role("button", name=re.compile(r"^Search$", re.I))); snooze(500)

    # ========================================================================
    # NAVIGATE TO EXTRACT DEFINITIONS
    # ========================================================================
    failed_deletes = []
    # Start from Home
    with suppress(Exception):
        try_click(page.get_by_role("link", name="Home", exact=True)); snooze()
        #screenshot(page)
    # Navigator → My Client Groups → Data Exchange → Extract Definitions
    try_click(page.get_by_role("link", name="Navigator")); snooze()
    # "My Client Groups" tile can be a title (tile) or link — try both
    if not try_click(page.get_by_title("My Client Groups", exact=True).locator("div").nth(1)):
        try_click(page.get_by_role("link", name=re.compile(r"^My Client Groups$", re.I)))
    snooze()
    #screenshot(page)
    try_click(page.get_by_role("link", name=re.compile(r"^Data Exchange$", re.I))); snooze()
    #screenshot(page)
    try_click(page.get_by_role("link", name=re.compile(r"^Extract Definitions$", re.I))); snooze()
    #screenshot(page)

    # ========================================================================
    # EXTRACT 1: Payslip → ADP_SC_GarnOnly_Payslip
    # ========================================================================

    search_by_name("Payslip")
    try_click(page.get_by_role("link", name=re.compile(r"^Payslip$", re.I))); snooze()
    #screenshot(page)
    try_click(page.get_by_role("link", name=re.compile(r"^Deliver", re.I))); snooze()
    #screenshot(page)
    set_end_date_and_ok("ADP_SC_GarnOnly_Payslip")
    expand_categories_if_needed()
    #  select row then delete
    delete_delivery_row_by_text("ADP_SC_GarnOnly_Payslip") 
    #validate and done
    with suppress(Exception):
        try_click(page.get_by_role("button", name=re.compile(r"^Validate$", re.I))); snooze(550)
        screenshot(page, "task3")
        try_click(page.get_by_role("button", name=re.compile(r"^Done$", re.I))); snooze(250)

    # ========================================================================
    # EXTRACT 2: US Third Party Monthly Tax → ADP SFTP
    # ========================================================================
    # Had combobox search but created issues so workaround was just search by Name again for robustness
    search_by_name("US Third Party Monthly Tax Extract")
    try_click(page.get_by_role("link", name=re.compile(r"^US Third Party Monthly Tax", re.I))); snooze()
    #screenshot(page)
    try_click(page.get_by_role("link", name=re.compile(r"^Deliver", re.I))); snooze()
    set_end_date_and_ok("ADP SFTP")
    expand_categories_if_needed()
    delete_delivery_row_by_text("ADP SFTP")
    with suppress(Exception):
        try_click(page.get_by_role("button", name=re.compile(r"^Validate$", re.I))); snooze(550)
        screenshot(page, "task3")
        try_click(page.get_by_role("button", name=re.compile(r"^Done$", re.I))); snooze(250)

    ## ========================================================================
    # EXTRACT 3: US Third Party Periodic Tax → ADP Tax SFTP
    # ========================================================================
    # NOTE: This one sometimes needs TWO delete attempts (already implemented)
    search_by_name("US Third Party Periodic Tax Extract")
    try_click(page.get_by_role("link", name=re.compile(r"^US Third Party Periodic Tax Extract$", re.I))); snooze()
    #screenshot(page)
    try_click(page.get_by_role("link", name=re.compile(r"^Deliver", re.I))); snooze()
    set_end_date_and_ok("ADP Tax SFTP")
    expand_categories_if_needed()
    # They do two deletes and click a category text in between; replicate: attempt delete twice
    delete_delivery_row_by_text("ADP Tax SFTP")
    # Click category to refresh view (Oracle UI quirk)
    with suppress(Exception):
        page.get_by_text(re.compile(r"Report category for Third", re.I)).nth(1).click(); snooze(200)
        # Second delete attempt (catches any missed rows)
    delete_delivery_row_by_text("ADP Tax SFTP")
    with suppress(Exception):
        try_click(page.get_by_role("button", name=re.compile(r"^Validate$", re.I))); snooze(550)
        screenshot(page, "task3")
        try_click(page.get_by_role("button", name=re.compile(r"^Done$", re.I))); snooze(250)

     # ========================================================================
    # EXTRACT 4: US Third Party Quarterly Tax → ADP Tax SFTP
    # ========================================================================

    search_by_name("US Third Party Quarterly Tax Extract")
    try_click(page.get_by_role("link", name=re.compile(r"^US Third Party Quarterly Tax", re.I))); snooze()
    #screenshot(page)
    try_click(page.get_by_role("link", name=re.compile(r"^Deliver", re.I))); snooze()
    #screenshot(page)
    set_end_date_and_ok("ADP Tax SFTP")
    expand_categories_if_needed()
    delete_delivery_row_by_text("ADP Tax SFTP")
    with suppress(Exception):
        try_click(page.get_by_role("button", name=re.compile(r"^Validate$", re.I))); snooze(550)
        screenshot(page, "task3")
        try_click(page.get_by_role("button", name=re.compile(r"^Done$", re.I))); snooze(250)
    # ========================================================================
    # COMPLETION
    # ========================================================================
    print(f"[Task 3] End-dated (and {'deleted' if not DRY_RUN else 'skipped delete in DRY_RUN'}) ADP deliveries.")
    # After all extracts processed, raise if any deletes failed so retry kicks in
    if failed_deletes:
        raise RuntimeError(f"[Task 3] Failed to delete {len(failed_deletes)} row(s): {failed_deletes}")

# =====================================================
# Task 4 — Add IPs to Location-Based Access (Security Console)
# =====================================================
def task4_add_ip(page, ip_list=None, append=True, PAUSE=3500, DRY_RUN=True):
    """
    Add IP addresses to Location-Based Access whitelist.
    
    WHAT IT DOES:
        Navigate to Security Console → Administration → Location Based Access
        and add/replace IP addresses in the allowed list.
    
    PARAMETERS:
        ip_list: list[str], str, or None
            - None: Uses default IPs ((client), (client), (client))
            - str: Single IP or comma-separated IPs ("1.2.3.4" or "1.2.3.4,5.6.7.8")
            - list: List of IP strings (["1.2.3.4", "5.6.7.8"])
        
        append: bool
            - True: Add IPs to end of existing list (with comma separator)
            - False: Replace entire IP list with new IPs
    
    DESIGN DECISION - Flexible IP Input:
        Accepts IPs in multiple formats for convenience. All formats are normalized
        to a comma-separated string before insertion.
    
    DESIGN DECISION - Append vs Replace:
        Default is append=True to avoid accidentally removing existing IPs. Had to do this way other wise code could not type at the end.
        Use append=False only when you want to completely reset the IP list.
        Other option was to try to replace whole thing wth the whole thing + new line
    """
    from contextlib import suppress
    import re

    def snooze(ms=PAUSE): page.wait_for_timeout(ms)
    def try_click(loc, timeout=6000):
        try:
            loc.wait_for(state="visible", timeout=timeout)
            loc.click(timeout=timeout)
            return True
        except Exception:
            return False

    # Normalize IPs
    if ip_list is None:
        ips = ["(client)", "(client)", "(client)"]
    elif isinstance(ip_list, str):
        # accept CSV string or single IP
        ips = [s.strip() for s in ip_list.split(",") if s.strip()]
    else:
        ips = [str(s).strip() for s in ip_list if str(s).strip()]
    csv_ips = ",".join(ips)

    # --- Navigate to Security Console → Location Based Access ---
    try_click(page.get_by_role("link", name="Navigator"))
    snooze()

    # Some UIs use a tile with title=Tools; others are a link. Try both.
    if not (
        try_click(page.get_by_title("Tools", exact=True).locator("div").nth(1)) or
        try_click(page.get_by_role("link", name=re.compile(r"^Tools$", re.I)))
    ):
        raise RuntimeError("Could not open Tools from Navigator.")
    snooze()

    if not try_click(page.get_by_role("link", name="Security Console")):
        raise RuntimeError("Security Console link not found.")
    snooze()

    # Sometimes the breadcrumb shows "Administration Administration" – handle both.
    if not (
        try_click(page.get_by_role("link", name=re.compile(r"^Administration(\sAdministration)?$", re.I)))
    ):
        raise RuntimeError("Administration section not found in Security Console.")
    snooze()

    if not try_click(page.get_by_role("link", name=re.compile(r"^Location Based Access$", re.I))):
        raise RuntimeError("Location Based Access link not found.")
    snooze()

    # --- Enter IPs ---
    txt = page.get_by_role("textbox", name=re.compile(r"Enter one or more IP", re.I))
    txt.click()
    snooze()

    if append:
        # Move cursor to end then prepend a comma before your CSV
        with suppress(Exception):
            txt.press("ControlOrMeta+ArrowDown")
            snooze(300)
            #screenshot(page)
        txt.type("," + csv_ips)
    else:
        # Replace the field completely
        # Some UIs resist select-all; fill("") is most reliable
        with suppress(Exception):
            txt.press("ControlOrMeta+A")
            snooze(200)
            #screenshot(page)
        txt.fill(csv_ips)

    snooze()
    screenshot(page, "task4")

    # --- Save / Cancel (DRY RUN) ---
    if not DRY_RUN:
        try_click(page.locator("[id=\"_FOpt1:_FOr1:0:_FONSr2:0:_FOTr7:1:aSp1:r4:0:rhSp1:ph1::_afrStr\"]")) #need to click the page otherwise will miss save I don't know why it didn't let me just click save I guess just weird quirk have to click page first
        snooze()
        #screenshot(page)
        try_click(page.get_by_role("button", name=re.compile(r"^Save$", re.I)))
        snooze()
    else:
        print(f"[Task 4] Dry run: skipped Save. Would set IPs: {csv_ips}")

    # --- Back Home (optional) ---
    with suppress(Exception):
        try_click(page.get_by_role("link", name="Home", exact=True))
        snooze()

    print(f"[Task 4] Location-Based Access IPs {'appended' if append else 'replaced'} with: {csv_ips}. DRY_RUN={DRY_RUN}")

# =====================================================
# Task 7 — Turn Off PO Communication (save after EACH change)
# =====================================================
def task7_turn_off_po_communication(page, PAUSE=3500, DRY_RUN=True):
    """
    Configure three PO (Purchase Order) communication settings in Administrator Profile.
    
    WHAT IT DOES:
        Updates three profile options to disable PO email notifications:
        1) PO_NOTIFICATION_OVERRIDE_E-MAIL → demo@oracle.com → Save
        2) PO_CONTROL → DISABLE → Save
        3) PO_FROM_EMAIL_ADDRESS → BUYER → Save
    
    DESIGN DECISION - Save After Each Change:
        Oracle requires saving and reopening the page between profile changes.
        If you try to change multiple profiles without saving between them,
        Oracle silently discards the earlier changes. This is an Oracle quirk when having to do through code,
        not a bug in the automation system.
        
        Flow per change:
        - Search for profile by code
        - Set new value
        - Save and Close
        - Reopen Manage Administrator Profile page
        - Repeat for next profile
    """
    import re
    from contextlib import suppress

    def snooze(ms=PAUSE): page.wait_for_timeout(ms)
    def try_click(loc, timeout=8000):
        """Helper: Try to click element, return True if successful.""" 
        try:
            loc.wait_for(state="visible", timeout=timeout)
            loc.click(timeout=timeout)
            return True
        except Exception:
            return False
    #------------------------------------------
    # HELPER FUNCTIONS
    #------------------------------------------
    def open_manage_admin_profile():
        """
        Navigate to Manage Administrator Profile page.
        
        PATH:
            Settings and Actions → Setup and Maintenance → Tasks
            → Search "Manage Administrator Profile" → Open it
        
        WHY THIS IS A FUNCTION:
            I had to reopen this page after each save (Oracle requirement).
            Making it a function avoids code duplication.
        """
        # Settings and Actions → Setup and Maintenance → Tasks → Search “Manage Administrator Profile”
        if not try_click(page.get_by_role("link", name="Settings and Actions")): raise RuntimeError("Settings and Actions not found.")
        snooze()
        if not try_click(page.get_by_role("link", name="Setup and Maintenance")): raise RuntimeError("Setup and Maintenance not found.")
        snooze()
        try_click(page.get_by_role("link", name="Tasks")); snooze()
        #screenshot(page)

        try_click(page.locator("[id='__af_Z_window']").get_by_role("link", name="Search")); snooze()
        sb = page.get_by_label("", exact=True)
        sb.click(); snooze(150)
        sb.fill("Manage Administrator Profile"); snooze()
        #screenshot(page)
        try_click(page.get_by_role("button", name="Search")); snooze()
        if not try_click(page.get_by_role("link", name="Manage Administrator Profile")):
            raise RuntimeError("Manage Administrator Profile link not found.")
        snooze()

    def save_and_reopen_if_needed():
        """
        Save and Close, then reopen the Manage Administrator Profile page.
        Help to save and close the profile then open the next
        Handles the popup.
        """
        if DRY_RUN:
            return
        with suppress(Exception):
            try_click(page.get_by_role("button", name="Save and Close")); snooze()
            # Some tenants pop an OK; handle if present
            try_click(page.get_by_role("button", name="OK")); snooze()
        # Re-open the screen for the next change
        open_manage_admin_profile()

    def set_profile_value(profile_code: str, value: str, value_type: str = "text"):
        """
        Search for a profile by code and set its value.
        
        PARAMETERS:
            profile_code: The profile option code (e.g., "PO_CONTROL")
            value: The new value to set (e.g., "DISABLE")
            value_type: "text" for textbox fill, "select" for dropdown
        
        DESIGN DECISION - value_type Parameter:
            Some profiles use text input (email addresses), others use dropdowns
            (DISABLE, BUYER). Code needs to handle both types differently.
        
        DESIGN DECISION - Multiple Select Strategies:
            For dropdown profiles, I tried THREE approaches:
            1. select_option(value) - by option value attribute
            2. select_option(label=value) - by visible label text
            3. Fallback to text input - in case it's actually a textbox
            
            This handles different Oracle UI versions and profile types.
        """
        code = page.get_by_role("textbox", name="Profile Option Code")
        code.click(); snooze(150)
        with suppress(Exception):
            code.press("ControlOrMeta+A"); snooze(120) #have to ctrl A t replace full text
        code.fill(profile_code); snooze()
        #screenshot(page)
        try_click(page.get_by_role("button", name=re.compile(r"^Search$", re.I), exact=True)); snooze()

        if value_type == "select":
            # DROPDOWN PROFILE: Try multiple selection strategies
            # Try by value, then by label; fall back to typing if necessary
            sel = page.get_by_label("Profile Value", exact=True)
            # Strategy 1: Select by value attribute
            with suppress(Exception):
                sel.select_option(value); snooze(); return
            # Strategy 2: Select by visible label
            with suppress(Exception):
                sel.select_option(label=value); snooze(); return
             # Strategy 3: Fallback to text input (some "selects" are actually textboxes)
            # Fall through to textbox route below
        # Textbox route:
        # Fill textbox directly
        pv = page.get_by_role("textbox", name="Profile Value")
        pv.click(); snooze(150)
        with suppress(Exception):
            pv.press("ControlOrMeta+A"); snooze(120) #need to select all to replace
        pv.fill(value); snooze()

    # ------------------------------------------
    # MAIN FLOW
    # ------------------------------------------

    # Open the page once at the start
    open_manage_admin_profile()
    #--------------------------------------
    # CHANGE 1: Override Notification Email
    #--------------------------------------
    # PO_NOTIFICATION_OVERRIDE_E-MAIL = demo@oracle.com
    # Purpose: Route all PO notification emails to a dummy address
    set_profile_value("PO_NOTIFICATION_OVERRIDE_E-MAIL", "demo@oracle.com", value_type="text")
    save_and_reopen_if_needed()
    screenshot(page, "task7")

    #--------------------------------------
    # CHANGE 2: Disable PO Control
    #--------------------------------------
    # Purpose: Turn off automatic PO notifications entirely
    set_profile_value("PO_CONTROL", "DISABLE", value_type="select")
    save_and_reopen_if_needed()
    screenshot(page, "task7")

    #--------------------------------------------
    # CHANGE 3: Set From Email Address to BUYER
    #--------------------------------------------
    # Purpose: Use buyer's email as sender (instead of system email)

    set_profile_value("PO_FROM_EMAIL_ADDRESS", "BUYER", value_type="select")
    #preferred to define everything first to get differnet dynamic approaches then at end call the task flow.
    screenshot(page, "task7")
    # Final save or cancel.
    if not DRY_RUN:
        with suppress(Exception):
            try_click(page.get_by_role("button", name="Save and Close")); snooze()
            #screenshot(page)
            try_click(page.get_by_role("button", name="OK")); snooze()
    else:
        with suppress(Exception):
            try_click(page.get_by_role("button", name="Cancel")); snooze()

    # Return Home
    with suppress(Exception):
        try_click(page.get_by_role("link", name="Home", exact=True)); snooze()

    print(f"[Task 7] PO Communication updated (+save after each). DRY_RUN={DRY_RUN}")

# =====================================================
# Task 9 — Disable AP Payment Transmission to the bank
# =====================================================
def task9_disable_ap_payment_transmission(page, PAUSE=3500, DRY_RUN=True):
    """
    Home → Settings and Actions → Setup and Maintenance → Tasks → Manage Payment Process
    Then for:
      1) (client) JPMC CC DIRECT DEBIT:
         - Reporting: Delivery Method = blank (0)
         - Payment System: Payment System = blank (0)
         - Save and Close (or Cancel in DRY_RUN)
      2) (client) JPMC CVPAY:
         - turn OFF 'Automatically transmit'
         - Reporting: Delivery Method = blank (0)
         - Save and Close (or Cancel in DRY_RUN)
      3) (client) Printed Check:
         - Reporting: Delivery Method = blank (0)
         - Payment System: turn OFF 'Automatically transmit'
         - Save and Close + OK (or Cancel in DRY_RUN)
      Finally: Done

      KNOWN ISSUE - "Automatically Transmit" Checkbox:
        Oracle renders this checkbox inconsistently across tenants:
        - Sometimes it's an ARIA checkbox
        - Sometimes it's a div with aria-checked attribute
        - Sometimes it's just clickable text
        
        The code tries THREE different approaches to find and uncheck it.
        This was a bug that took time to fix.

        DESIGN DECISION - Save After Each Payment Process:
        Each payment process is saved separately (Save and Close).
        This follows Oracle's expected workflow and prevents data loss.
    """

    import re
    from contextlib import suppress

    def snooze(ms=PAUSE): page.wait_for_timeout(ms)

    def try_click(loc, timeout=6000):
        """Helper: Try to click element, return True if successful."""
        try:
            loc.wait_for(state="visible", timeout=timeout)
            loc.click(timeout=timeout)
            return True
        except Exception:
            return False
    # -----------------------------------
    # HELPER FUNCTIONS
    # -----------------------------------
    def commit_or_cancel(expect_ok=False):
        """Save and Close (and OK if needed) or Cancel in DRY_RUN.
        PARAMETERS:
            expect_ok: bool - If True, also click OK button after Save and Close
        
        WHY expect_ok PARAMETER:
            The third payment process ((client) Printed Check) shows an extra
            confirmation dialog after Save and Close. The first two don't.
        
        """
        if not DRY_RUN:
            try_click(page.get_by_role("button", name="Save and Close")); snooze()
            if expect_ok:
                with suppress(Exception):
                    try_click(page.get_by_role("button", name="OK")); snooze()
        else:
            try_click(page.get_by_role("button", name="Cancel")); snooze()
            with suppress(Exception):
                try_click(page.get_by_role("button", name="Yes")); snooze()

    def ensure_transmit_unchecked():
        """
        Ensure 'Automatically transmit' checkbox is unchecked.
            
            WHY THIS EXISTS:
                I only want to click the checkbox if it's currently CHECKED.
                Clicking an already-unchecked checkbox would turn it ON (bad!).
            
            DESIGN DECISION - Multiple Detection Strategies:
                Oracle renders this checkbox differently accross envs.
                
                Strategy 1: ARIA checkbox role
                    - Most accessible, preferred approach
                    - Can check .is_checked() state
                
                Strategy 2: Toggle div with aria-checked
                    - Used in some older Oracle UIs
                    - Check aria-checked attribute value
                
                Strategy 3: Clickable text
                    - Fallback for weird Oracle rendering
                    - Check aria-checked or aria-pressed attributes

            Had to make this multi-approach becuase sometimes 1/3 or 2/3 would work or 3/3 mostly one always would not uncheck
            this is solution to confirm.
            """
        # Strategy 1: Prefer a checkbox role if present
        with suppress(Exception):
            cb = page.get_by_role("checkbox", name=re.compile(r"Automatically transmit", re.I))
            if cb.is_visible():
                if cb.is_checked():
                    print("[Task 9] Automatically transmit is ON → unchecking.")
                    cb.click(); snooze()
                else:
                    print("[Task 9] Automatically transmit already OFF.")
                return
        # Strategy 2: Fallbackto toggle by text if rendered differently
        with suppress(Exception):
            tgl = page.get_by_text("Automatically transmit", exact=False)
            # many Oracle toggles expose aria-checked or aria-pressed
            state = (tgl.get_attribute("aria-checked") or
                     tgl.get_attribute("aria-pressed") or "").lower()
            if state == "true":
                print("[Task 9] Automatically transmit is ON → clicking to uncheck.")
                tgl.click(); snooze()
            else:
                print("[Task 9] Automatically transmit already OFF or not present.")

    def ensure_select_blank_by_label(lbl):
        """
        Ensure a dropdown is set to blank (option value '0').
        
        WHAT IT DOES:
            1. Find the dropdown by its label text
            2. Check if it's already blank (value "0" or "")
            3. If not blank, set it to option "0"
        
        DESIGN DECISION - Check Before Setting:
            Avoids unnecessary DOM manipulation if already correct.
            Also provides helpful console output for debugging.
        """
        sel = page.get_by_label(lbl, exact=True)
        #Check current value
        with suppress(Exception):
            current = sel.input_value()
            if current == "0" or current == "":
                print(f"[Task 9] '{lbl}' already blank.")
                return
        # Set to blank (option value "0")
        print(f"[Task 9] Setting '{lbl}' to blank (0).")
        sel.select_option("0"); snooze()

    #-------------------------------------------------------------------------
    # ------------------ NAVIGATE TO MANAGE PAYMENT PROCESS ------------------
    #-------------------------------------------------------------------------

    try_click(page.get_by_role("link", name="Home", exact=True)); snooze()

    try_click(page.get_by_role("link", name="Settings and Actions")); snooze()
    try_click(page.get_by_role("link", name="Setup and Maintenance")); snooze()
    #screenshot(page)
    try_click(page.get_by_role("link", name="Tasks")); snooze()

    try_click(page.locator("[id='__af_Z_window']").get_by_role("link", name="Search")); snooze()
    inp = page.get_by_label("", exact=True)
    inp.click(); snooze()
    #screenshot(page)
    inp.fill("Manage Payment Process"); snooze()
    #screenshot(page)
    with suppress(Exception):
        inp.press("Enter"); snooze()

    try_click(page.get_by_role("link", name="Manage Payment Process")); snooze()
    #screenshot(page)
    # Filter by name "(client)" to see only our payment processes
    name_box = page.get_by_role("textbox", name="Name")
    name_box.click(); snooze()
    name_box.fill("(client)"); snooze()
    #screenshot(page)
    with suppress(Exception):
        name_box.press("Enter"); snooze()

    # ===== PAYMENT PROCESS 1: (client) JPMC CC DIRECT DEBIT =====
    try_click(page.get_by_role("link", name="(client) JPMC CC DIRECT DEBIT")); snooze()
    #screenshot(page)

    # Payment System tab (2nd occurrence), then Reporting tab, set Delivery=blank
    page.locator("div").filter(has_text=re.compile(r"^Payment System$")).nth(1).click(); snooze()
    #screenshot(page)
    page.locator("div").filter(has_text=re.compile(r"^Reporting$")).nth(1).click(); snooze()
    #screenshot(page)
    ensure_select_blank_by_label("Delivery Method")

    # Back to Payment System and set Payment System = blank (0)
    try_click(page.get_by_role("link", name="Payment System")); snooze()
    screenshot(page, "task9")
    ensure_select_blank_by_label("Payment System")

    commit_or_cancel(expect_ok=False)

    # ===== PAYMENT PROCESS2: (client) JPMC CVPAY =====
    try_click(page.get_by_role("link", name="(client) JPMC CVPAY")); snooze()
    #screenshot(page)

    # Turn OFF Automatically transmit
    # First try: direct text click (sometimes works)
    with suppress(Exception):
        page.get_by_text("Automatically transmit").click(); snooze()  
        #screenshot(page)
    # Also guard it:(idempotent - safe to call even if already unchecked)
    ensure_transmit_unchecked()

    # Reporting → Delivery Method = blank
    try_click(page.get_by_role("link", name="Reporting")); snooze()
    screenshot(page, "task9")
    ensure_select_blank_by_label("Delivery Method")

    commit_or_cancel(expect_ok=False)

        # =====PAYMENT PROCESS 3: (client) Printed Check =====
        #NOTE: This one requires THREE different checkbox detection strategies

    try_click(page.get_by_role("link", name="(client) Printed Check")); snooze()

    # Reporting first → Delivery Method = blank
    ensure_select_blank_by_label("Delivery Method")

    # Payment System → turn OFF Automatically transmit
    try_click(page.get_by_role("link", name="Payment System")); snooze()

    print("[Task 9] Unchecking Automatically transmit for (client) Printed Check...")

    #Three-Strategy Checkbox Detection as this was the solution to fixing a bug where it would miss the check mark
    # STRATEGY 1: Try ARIA checkbox
    unchecked = False
    with suppress(Exception):
        cb = page.get_by_role("checkbox", name=re.compile(r"Automatically transmit", re.I))
        if cb.count() > 0:
            if cb.first.is_checked():
                cb.first.click(); snooze()
            unchecked = True

    # STRATEGY 2: Try toggle div with aria-checked
    if not unchecked:
        with suppress(Exception):
            tg = page.locator("div[aria-checked]").filter(has_text=re.compile("Automatically transmit", re.I))
            if tg.count() > 0:
                if tg.first.get_attribute("aria-checked") == "true":
                    tg.first.click(); snooze()
                unchecked = True

    # STRATEGY 3: Try literal text click (Oracle sometimes uses weird spans)
    if not unchecked:
        with suppress(Exception):
            lbl = page.get_by_text("Automatically transmit", exact=False)
            if lbl.count() > 0:
                lbl.first.click(); snooze()
                unchecked = True

    if not unchecked:
        print(" Task 9 WARNING: Could not locate or uncheck 'Automatically transmit' for Printed Check.")
    else:
        print(" Successfully unchecked 'Automatically transmit' for Printed Check.")
    screenshot(page, "task9")
    # Save and Close + OK
    commit_or_cancel(expect_ok=True)

    screenshot(page, "task9")
    # Save and Close + OK (per your sequence)
    commit_or_cancel(expect_ok=True)

    # Done
    try_click(page.get_by_role("button", name="Done")); snooze()

    print(f"[Task 9] Completed — Delivery Method & Payment System set to blank (0), "
          f"'Automatically transmit' unchecked where present. DRY_RUN={DRY_RUN}")

# =====================================================
# Task 10 — Update Corp Card Program to Non-PROD SFTP
# =====================================================
def task10_update_corp_card_program_to_nonprod_sftp(
    page,
    existing_profile_name="(client)",         # the row you click
    new_download_profile_name="(client)XX",   # what you type into Download Profile Name
    new_account_name="(client)_(client)XX",  # what you type into Account Name
    PAUSE=3500,
    DRY_RUN=True,
):
    """
    Update corporate card SFTP connection to use non-prod server.
    
    WHAT IT DOES:
        1. Search for "Manage Corporate Card Programs"
        2. Open "(client) Corporate Card Program"
        3. Click Transfer Parameters tile
        4. Open existing profile row ((client))
        5. Update Download Profile Name to include "XX" suffix
        6. Update Account Name to include "XX" suffix
        7. Save changes (or Cancel in DRY_RUN)
     PARAMETERS:
        existing_profile_name: Name of the profile row to edit (default: "(client)")
        new_download_profile_name: New value for Download Profile Name field
        new_account_name: New value for Account Name field
    
    DESIGN DECISION - Double-Fill Download Profile:
        We fill the Download Profile Name field TWICE (before and after Account Name).
        This is because Oracle sometimes loses the first value when you click
        to another field. The second fill ensures it sticks.
    """
    import re
    from contextlib import suppress

    def snooze(ms=PAUSE): page.wait_for_timeout(ms)
    def try_click(loc, timeout=6000):
        """Helper: Try to click element, return True if successful."""
        try:
            loc.wait_for(state="visible", timeout=timeout)
            loc.click(timeout=timeout)
            return True
        except Exception:
            return False
        
    #----------------------------------------------------
    # --- # SEARCH FOR MANAGE CORPORATE CARD PROGRAMS ---
    #----------------------------------------------------
     # Navigate to Setup and Maintenance (self-contained for --tasks 10)
    try_click(page.get_by_role("link", name="Home", exact=True)); snooze()

    try_click(page.get_by_role("link", name="Settings and Actions")); snooze()
    try_click(page.get_by_role("link", name="Setup and Maintenance")); snooze()
    #screenshot(page)
    try_click(page.get_by_role("link", name="Tasks")); snooze()

    try_click(page.locator("[id='__af_Z_window']").get_by_role("link", name="Search")); snooze()
    inp = page.get_by_label("", exact=True)
    inp.click(); snooze()

    try_click(page.get_by_label("", exact=True)); snooze()
    page.get_by_label("", exact=True).fill("Manage Corporate Card Programs"); snooze()
    #screenshot(page)
    with suppress(Exception):
        page.get_by_label("", exact=True).press("Enter"); snooze()

    try_click(page.get_by_role("link", name="Manage Corporate Card Programs")); snooze()
    #screenshot(page)

    #-----------------------------------------------------------
    # ---  OPEN CORPORATE CARD PROGRAM & TRANSFER PARAMETERS ---
    #-----------------------------------------------------------

    try_click(page.get_by_role("link", name="(client) Corporate Card Program")); snooze()
    # Your recording shows a title hover/click on the card:
    try_click(page.get_by_title(re.compile(r"Enter parameters needed to", re.I)).locator("div")); snooze()
     #------------------------
     # SELECT AND EDIT PROFILE
     #------------------------
    # --- Select the profile row to edit ---
    try_click(page.get_by_role("link", name=existing_profile_name)); snooze()

    # --- Update: Download Profile Name ---
    dp = page.get_by_role("textbox", name="Download Profile Name")
    dp.click(); snooze()
    with suppress(Exception):
        dp.press("ControlOrMeta+A"); snooze(120)
    dp.fill(new_download_profile_name); snooze()

    # --- Update: Account Name ---
    acct = page.get_by_role("textbox", name="Account Name")
    acct.click(); snooze()
    with suppress(Exception):
        acct.press("ControlOrMeta+A"); snooze(120)
    acct.fill(new_account_name); snooze()
    #screenshot(page)

    #--------------------------------------------------------------------------------------------------
    # Optional: ensure DP field remains as desired  RE-FILL DOWNLOAD PROFILE (Oracle Quirk Workaround)
    #--------------------------------------------------------------------------------------------------
    #had to do it again because it was sometimes not stayng filled
    dp.click(); snooze()
    with suppress(Exception):
        dp.press("ControlOrMeta+A"); snooze(120)
    dp.fill(new_download_profile_name); snooze()
    screenshot(page, "task10")

    # --- Save / Cancel sequence exactly like your steps ---
    if not DRY_RUN:
        # inner dialog Save, then Save and Close
        with suppress(Exception):
            try_click(page.locator("[id='__af_Z_window']").get_by_role("button", name="Save", exact=True)); snooze()
        with suppress(Exception):
            try_click(page.locator("[id='__af_Z_window']").get_by_role("button", name="Save and Close")); snooze()
        # outer Save and Close
        with suppress(Exception):
            try_click(page.get_by_role("button", name="Save and Close")); snooze()
    else:
        
        with suppress(Exception):
            try_click(page.locator("[id='__af_Z_window']").get_by_role("button", name="Cancel")); snooze()
        with suppress(Exception):
            try_click(page.get_by_role("button", name="Cancel")); snooze()

    # Done
    with suppress(Exception):
        try_click(page.get_by_role("button", name="Done")); snooze()

    print(f"[Task 10] Updated Corp Card profile "
          f"(row='{existing_profile_name}') → "
          f"Download Profile='{new_download_profile_name}', "
          f"Account='{new_account_name}'. DRY_RUN={DRY_RUN}")

# =====================================================
# Task 11 — Disable GetThere Configuration
# =====================================================
def task11_disable_getthere_configuration(
    page,
    username="XXXDemo", #username and passowrd an be changed if want to do with another account or password
    password="XXX(client)",
    PAUSE=3500,
    DRY_RUN=True,
):
    """
    Update GetThere travel partner connection credentials.
    
    WHAT IT DOES:
        Navigate to Manage Travel Partner → GetThere
        Update Connection User Name and Password to dummy/test values
     DESIGN DECISION - Clear Then Fill Username:
        I fill the username field with empty string ("") first, then fill
        with the new username. Manually I can just type xxx for example at beginning but in code it was harder to program that as clicks 
        were weird, so I just have it fully replace and fill.
    """
    import re
    from contextlib import suppress #these imports are at beginning of file, maybe you saw in ther task yes they are technically redudant, when I built I just put them 
    #there for the task I was doing to know what I need to import for certain tasks because when I built I didn't start top down I started with random tasks I thought
    # would be easiest to automate so these imports are from then and everything works so I just left it, it could be removed though.

    def snooze(ms=PAUSE): page.wait_for_timeout(ms)
    def try_click(loc, timeout=6000):
        """Helper: Try to click element, return True if successful."""
        try:
            loc.wait_for(state="visible", timeout=timeout)
            loc.click(timeout=timeout)
            return True
        except Exception:
            return False

    # --- Navigate ---
    try_click(page.get_by_role("link", name="Settings and Actions")); snooze()
    try_click(page.get_by_role("link", name="Setup and Maintenance")); snooze()
    try_click(page.get_by_role("link", name="Tasks")); snooze()

    try_click(page.locator("[id='__af_Z_window']").get_by_role("link", name="Search")); snooze()

    # Blank-labeled input is the search box
    sb = page.get_by_label("", exact=True)
    sb.click(); snooze()
    sb.fill("Manage Travel Partner "); snooze()
    #screenshot(page)

    try_click(page.get_by_role("button", name="Search")); snooze()
    try_click(page.get_by_role("link", name="Manage Travel Partner")); snooze()
    #screenshot(page)

    try_click(page.get_by_role("link", name="GetThere")); snooze()

    # --- Connection User Name ---
    uname = page.get_by_role("textbox", name="Connection User Name")
    uname.click(); snooze()
    with suppress(Exception):
        uname.press("ControlOrMeta+A"); snooze(150)
    uname.fill("")  #clean field first 
    snooze()
    #screenshot(page)
    uname.fill(username); snooze()
    #screenshot(page)

    # --- Connection Password ---
    pwd = page.get_by_role("textbox", name="Connection Password")
    pwd.click(); snooze()
    with suppress(Exception):
        pwd.press("ControlOrMeta+A"); snooze(150)
    pwd.fill(password); snooze() #then fill with dummy
    screenshot(page, "task11")

    # --- Save / Cancel per DRY_RUN ---
    if not DRY_RUN:
        try_click(page.get_by_role("button", name="Save and Close")); snooze()
        with suppress(Exception):
            try_click(page.get_by_role("button", name="OK", exact=True)); snooze()
    else:
        try_click(page.get_by_role("button", name="Cancel")); snooze()
        with suppress(Exception):
            try_click(page.get_by_role("button", name="Yes")); snooze()

    # --- Back Home ---
    with suppress(Exception):
        try_click(page.get_by_role("link", name="Home", exact=True)); snooze()

    print(f"[Task 11] GetThere configuration updated (username={username!r}). DRY_RUN={DRY_RUN}")

# =====================================================
# Task 12 — Remove email "From" values in Receivables System Options
# =====================================================
def task12_remove_receivables_emails(page, PAUSE=3500, DRY_RUN=True):
    """
    Clear email 'from' fields in Receivables System Options.
    
    WHAT IT DOES:
        Navigate to Manage Receivables System Options
        Clear 6 email 'from' fields to prevent test emails from being sent
    DESIGN DECISION - Use Oracle ADF Input Names:
        Oracle uses "pt1:r1:0:rt:1:r2:0:dynamicRegion1:0:ap1:it1" for the fields, there were no other ways I could find
        Possible in future if changed, that have to recapture the field names.
    """
    from contextlib import suppress

    def snooze(ms=PAUSE): page.wait_for_timeout(ms)
    def try_click(loc, timeout=6000):
        """Helper: Try to click element, return True if successful."""
        try:
            loc.wait_for(state="visible", timeout=timeout)
            loc.click(timeout=timeout)
            return True
        except Exception:
            return False

    def clear_input_by_name(name_attr: str):
        """Clear an input field by its name attribute."""
        inp = page.locator(f'input[name="{name_attr}"]')
        inp.click(); snooze()
        with suppress(Exception):
            inp.press("ControlOrMeta+A"); snooze(120)
        inp.fill(""); snooze()

    # --- Navigate ---
    try_click(page.get_by_role("link", name="Settings and Actions")); snooze()
    try_click(page.get_by_role("link", name="Setup and Maintenance")); snooze()
    try_click(page.get_by_role("link", name="Tasks")); snooze()

    try_click(page.locator("[id='__af_Z_window']").get_by_role("link", name="Search")); snooze()

    # Search box (blank-labeled)
    sb = page.get_by_label("", exact=True)
    sb.click(); snooze()
    sb.fill("Manage Receivables System"); snooze()
    #screenshot(page)

    try_click(page.get_by_role("button", name="Search")); snooze()
    try_click(page.get_by_role("link", name="Manage Receivables System")); snooze()
    #screenshot(page)

    # --- Clear email fields  ---
    clear_input_by_name("pt1:r1:0:rt:1:r2:0:dynamicRegion1:0:ap1:it1")
    clear_input_by_name("pt1:r1:0:rt:1:r2:0:dynamicRegion1:0:ap1:it5")
    clear_input_by_name("pt1:r1:0:rt:1:r2:0:dynamicRegion1:0:ap1:it12")
    clear_input_by_name("pt1:r1:0:rt:1:r2:0:dynamicRegion1:0:ap1:it13")
    clear_input_by_name("pt1:r1:0:rt:1:r2:0:dynamicRegion1:0:ap1:it6")
    clear_input_by_name("pt1:r1:0:rt:1:r2:0:dynamicRegion1:0:ap1:it9")
    screenshot(page, "task12")
    # --- Save / Cancel ---
    if not DRY_RUN:
        try_click(page.get_by_role("button", name="Save and Close")); snooze()
        
    else:
        try_click(page.get_by_role("button", name="Cancel")); snooze()

    # --- Back Home ---
    try_click(page.get_by_role("link", name="Home", exact=True)); snooze()

    print(f"[Task 12] Receivables System email 'from' fields cleared. DRY_RUN={DRY_RUN}")

# =====================================================
# Task 14 — Create Sandbox, set CIF & PLE Page Integration THIS TASK IS INCOMPLETE HAS SOME ISSUES SO CANNOT BE USED
# =====================================================
def task14_setup_sandbox_page_integration(
    page,
    sandbox_name="Test-1",
    PAUSE=3500,
    DRY_RUN=True,
):
    """
    Home → Navigator → Sandboxes → select 'Page Integration' → Create Sandbox (Name=sandbox_name) → Create and Enter
    Tools → Page Integration → CIF/PLE → set Web Page URLs by *reading existing value* and swapping instance tag.
    If field is empty, fall back to same host as INSTANCE_URL.
    DRY_RUN=False will Save & Publish; DRY_RUN=True will Cancel & Leave.
    """
    import re
    from contextlib import suppress

    def snooze(ms=PAUSE): page.wait_for_timeout(ms)
    def try_click(loc, timeout=8000):
        try:
            loc.wait_for(state="visible", timeout=timeout)
            loc.click(timeout=timeout)
            return True
        except Exception:
            return False

    # derive instance tag like 'dev10' from INSTANCE_URL
    m = re.search(r'(dev\d+|test\d+|p2t\d+)', INSTANCE_URL, re.I)
    inst_tag = (m.group(1).lower() if m else "dev")

    def build_new_url_from(existing_url: str, app_code: str) -> str:
        """
        If existing_url present: replace instance tag segment (devX/testX/p2tX) in the host if found.
        Else: fallback to same-host builder path.
        app_code: '(client)_CIF' or '(client)_PLE_FORM'
        """
        if existing_url and "://" in existing_url:
            # Replace dev/test tag anywhere in the host
            return re.sub(
                r'(dev\d+|test\d+|p2t\d+)',
                inst_tag,
                existing_url,
                count=1,
                flags=re.I
            )
        # fallback: same-host path
        return f"{INSTANCE_URL}/ic/builder/rt/{app_code}/live/webApps/ocswebapp/"

    # ----------------- Create & Enter Sandbox -----------------
    try_click(page.get_by_role("link", name="Home", exact=True)); snooze()
    try_click(page.get_by_role("link", name="Navigator")); snooze()
    try_click(page.get_by_role("link", name="Sandboxes")); snooze()

    # Select 'Page Integration' row checkbox
    try_click(page.locator("tr").filter(has_text=re.compile(r"^Page Integration$", re.I)).locator("label")); snooze()

    try_click(page.get_by_role("button", name="Create Sandbox")); snooze()
    name_box = page.get_by_role("textbox", name="Name")
    name_box.click(); snooze()
    name_box.fill(sandbox_name); snooze()
    try_click(page.get_by_role("button", name="Create and Enter")); snooze()

    # Go to the Sandboxes tools area (stable URL without session params)
    with suppress(Exception):
        page.goto(f"{INSTANCE_URL}/fscmUI/faces/FuseOverview?fndGlobalItemNodeId=itemNode_tools_sandboxes"); snooze()

    # Tools → Page Integration
    try_click(page.get_by_role("menuitem", name="Tools").locator("div")); snooze()
    try_click(page.locator("[id='__af_Z_window']").get_by_text("Page Integration")); snooze()

    # ----------------- CIF -----------------
    try_click(page.get_by_role("link", name="CIF")); snooze()
    wp = page.get_by_role("textbox", name="Web Page")
    # read existing and compute safe new
    existing_cif = ""
    with suppress(Exception):
        existing_cif = wp.input_value(timeout=3000)
    new_cif = build_new_url_from(existing_cif, "(client)_CIF")

    wp.click(); snooze()
    with suppress(Exception):
        wp.press("ControlOrMeta+A"); snooze(120)
    wp.fill(new_cif); snooze()
    if not DRY_RUN:
        try_click(page.get_by_role("button", name="Save and Close")); snooze()
    else:
        try_click(page.get_by_role("button", name="Cancel")); snooze()

    # ----------------- PLE -----------------
    try_click(page.get_by_role("link", name="PLE")); snooze()
    wp2 = page.get_by_role("textbox", name="Web Page")
    existing_ple = ""
    with suppress(Exception):
        existing_ple = wp2.input_value(timeout=3000)
    new_ple = build_new_url_from(existing_ple, "(client)_PLE_FORM")

    wp2.click(); snooze()
    with suppress(Exception):
        wp2.press("ControlOrMeta+A"); snooze(120)
    wp2.fill(new_ple); snooze()
    if not DRY_RUN:
        try_click(page.get_by_role("button", name="Save and Close")); snooze()
    else:
        try_click(page.get_by_role("button", name="Cancel")); snooze()

    # ----------------- Publish vs Leave Sandbox -----------------
    if not DRY_RUN:
        with suppress(Exception):
            try_click(page.get_by_role("menuitem", name=sandbox_name).locator("div")); snooze()
        with suppress(Exception):
            try_click(page.get_by_text("Publish", exact=True)); snooze()
            try_click(page.get_by_role("button", name="Yes")); snooze()
            try_click(page.get_by_role("button", name="Publish")); snooze()
            try_click(page.get_by_role("button", name="Yes")); snooze()
    else:
        with suppress(Exception):
            try_click(page.get_by_text("Leave Sandbox")); snooze()
            try_click(page.get_by_role("button", name="Yes")); snooze()

    # ----------------- Back Home -----------------
    with suppress(Exception):
        try_click(page.get_by_role("link", name="Home", exact=True)); snooze()

    print(f"[Task 14] Sandbox '{sandbox_name}' CIF/PLE set (CIF={new_cif}, PLE={new_ple}). DRY_RUN={DRY_RUN}")

# =====================================================
# Task 15 — Update or Remove Hire Right Configuration
# =====================================================
def task15_update_or_remove_hireright_config(
    page,
    ref_key="(client)-PROD",
    client_id="(client)",
    client_secret="(client)",
    assign_user=None,       # ← None = skip assigning user
    do_inactivate=False,    # ← only used if not DRY_RUN
    PAUSE=3500,
    DRY_RUN=True,
):
    """
   Update HireRight background check partner configuration.
    
    WHAT IT DOES:
        Navigate to Recruiting Category Provisioning and Configuration
        → Background Check Partners
        Update Reference Key, Client ID, and Client Secret
        Optionally assign a user account or inactivate the partner
    PARAMETERS:
        ref_key: Reference key for HireRight integration
        client_id: Client ID for HireRight API
        client_secret: Client secret for HireRight API
        assign_user: Optional username to assign (None = skip)
        do_inactivate: If True (and not DRY_RUN), inactivates the partner
    DESIGN DECISION - Multiple Save Steps:
        The 4-step save sequence (Save → Inner Save → Save → Save and Close)
        seems redundant but is necessary.
        Oracle requires saving at multiple levels (toolbar → inner window → toolbar again) when I was doing with code.
        This ensures all changes are committed. The 5000ms waits give Oracle
        time to process each save operation
    """
    import re
    from contextlib import suppress

    def snooze(ms=PAUSE): 
        page.wait_for_timeout(ms)

    def try_click(loc, timeout=8000):
        """Helper: Try to click element, return True if successful."""
        try:
            loc.wait_for(state="visible", timeout=timeout)
            loc.click(timeout=timeout)
            return True
        except Exception:
            return False

    # --- Navigate  ---
    try_click(page.get_by_role("link", name="Settings and Actions")); snooze()
    try_click(page.get_by_role("link", name="Setup and Maintenance")); snooze()
    try_click(page.get_by_role("link", name="Tasks")); snooze()

    try_click(page.locator("[id='__af_Z_window']").get_by_role("link", name="Search")); snooze()
    sb = page.get_by_label("", exact=True)
    sb.click(); snooze()
    sb.fill("Recruiting Category"); snooze()
    #screenshot(page)

    try_click(page.get_by_role("button", name="Search")); snooze()
    try_click(page.get_by_role("link", name="Recruiting Category Provisioning and Configuration")); snooze()
    #screenshot(page)

    # Partners grid link 
    try_click(
        page.locator("div")
        .filter(has_text=re.compile(r"^Background Check\s*Partners\s*All\s*Active\s*Inactive\s*Provisioned\s*Status\s*Active$", re.I))
        .get_by_role("link")
    ); snooze()

    # --- Update fields ---
    def fill_box(role_name, value):
        """Fill a textbox, selecting all existing text first."""
        el = page.get_by_role("textbox", name=role_name)
        el.click(); snooze(150)
        #screenshot(page)
        with suppress(Exception):
            el.press("ControlOrMeta+A"); snooze(120)
        el.fill(value); snooze()
        #screenshot(page)
    # Update main fields
    fill_box("Reference Key", ref_key)
    fill_box("Client ID", client_id)
    fill_box("Client Secret", client_secret)
    screenshot(page, "task15")

    # Optional inactivate (only when not DRY_RUN)
    if do_inactivate and not DRY_RUN:
        with suppress(Exception):
            page.locator("button").first.click(); snooze()
            try_click(page.get_by_text("Inactivate")); snooze()

    # Optional Assign User Account (only if provided)
    if assign_user:
        try_click(page.get_by_role("link", name="Assign User Account")); snooze()
        fill_box("User Name", assign_user)

       # --- Save & Close / Cancel ---
    if not DRY_RUN:
        # 1) Toolbar Save
        with suppress(Exception):
            page.get_by_role("button", name="Save").click()
            snooze(5000)

        # 2) Inner Save in the small window
        with suppress(Exception):
            page.locator("[id='__af_Z_window']").get_by_text("Save", exact=True).click()
            snooze(5000)

        # 3) Toolbar Save again
        with suppress(Exception):
            page.get_by_role("button", name="Save").click()
            snooze(5000)

        # 4) Save and Close
        with suppress(Exception):
            page.get_by_text("Save and Close").click()
            snooze(5000)
    else:
        with suppress(Exception):
            page.locator("[id='__af_Z_window']").get_by_role("button", name="Cancel").click()
            snooze()
        with suppress(Exception):
            page.get_by_role("button", name="Cancel").click()
            snooze()
    # --- Back Home ---
    with suppress(Exception):
        try_click(page.get_by_role("link", name="Home", exact=True)); snooze()

    print(
        f"[Task 15] HireRight updated (ref={ref_key}, client={client_id}). "
        f"AssignedUser={'SKIPPED' if not assign_user else assign_user}. "
        f"Inactivate={do_inactivate}. DRY_RUN={DRY_RUN}"
    )


# =====================================================
# Task 16 — Pre-Note: Update JPMC SFTP to non-prod or disable delivery (with deletes, sometimes misses second row delete)
# =====================================================
def task16_prenote_update_sftp_or_disable_delivery(
    page,
    PAUSE=3500,
    DRY_RUN=True,
    deliveries_to_delete=("US Generate Prenote EFT File SFTP","US Generate Prenote EFT File CIF"),
    is_retry=False,  
):
    """
    Delete prenote EFT delivery rows to disable automatic prenote generation.
    
    WHAT IT DOES:
        Navigate to Extract Definitions → Generate Prenote File
        Delete two delivery rows:
        - US Generate Prenote EFT File SFTP
        - US Generate Prenote EFT File CIF
    KNOWN ISSUE - Sometimes Misses Second Row Delete:
        The CIF delivery row is sometimes hard to find with normal selectors.
        I use a fallback strategy (nth(3) Extract Delivery span) but it's not
        100% reliable. You may need to manually delete the CIF row if automation misses it.
    DESIGN DECISION - Two-Tier Delete Strategy:
        Method 1: Find cell by delivery name (normal approach)
        Method 2: Fallback for CIF - use nth(3) Extract Delivery span
        
        The fallback is specific to CIF because I had trouble with it and I think Oracle renders it differently
        than other delivery rows (weird table structure).
    """
    import re
    from contextlib import suppress
    failed_deletes = []
    def snooze(ms=PAUSE): page.wait_for_timeout(ms)
    def try_click(loc, timeout=9000):
        """Helper: Try to click element, return True if successful."""
        try:
            loc.wait_for(state="visible", timeout=timeout)
            loc.click(timeout=timeout)
            return True
        except Exception:
            return False

    # --- Home ---
    with suppress(Exception):
        try_click(page.get_by_role("link", name="Home", exact=True)); snooze()

    # --- Navigator (your exact selector) ---
    try_click(page.locator("td").filter(has_text="Navigator").nth(1)); snooze()

    # --- Data Exchange → Extract Definitions ---
   # Try Data Exchange directly (works if My Client Groups already expanded)
    if not try_click(page.get_by_role("link", name="Data Exchange")):
        # My Client Groups must be collapsed — expand it first
        try_click(page.get_by_title("My Client Groups", exact=True).locator("div").nth(1)); snooze()
        try_click(page.get_by_role("link", name="Data Exchange"))
    snooze()
    #screenshot(page)
    try_click(page.get_by_role("link", name="Extract Definitions")); snooze()
    #screenshot(page)

    # --- Show Filters ---
    try_click(page.get_by_role("link", name=re.compile(r"^Show Filters$", re.I))); snooze()

    # --- Name = Generate Prenote File ---
    name_box = page.get_by_role("textbox", name="Name")
    name_box.click(); snooze(120)
    with suppress(Exception):
        name_box.press("ControlOrMeta+A"); snooze(80)
    name_box.fill("Generate Prenote File"); snooze()
    #screenshot(page)

    # --- LDG = US Legislative Data Group ---
    try_click(page.get_by_role("combobox", name="Legislative Data Group")); snooze()
    try_click(page.get_by_role("option", name="US Legislative Data Group")); snooze()

    # --- Search + open extract ---
    try_click(page.get_by_role("search").get_by_role("button", name="Search")); snooze()
    try_click(page.get_by_role("link", name="Generate Prenote File")); snooze()

    # --- Deliver tab (some tenants show "Deliver Deliver") ---
    if not try_click(page.get_by_role("link", name=re.compile(r"^Deliver Deliver$", re.I))):
        try_click(page.get_by_role("link", name=re.compile(r"^Deliver$", re.I)))
    snooze()

    # --- Expand Report Categories (if present) ---
    with suppress(Exception):
        try_click(page.get_by_role("button", name=re.compile(r"^Expand Report Categories$", re.I))); snooze()

        # --- Delete each requested delivery row (only when DRY_RUN=False) ---
    for delivery_name in deliveries_to_delete:
        print(f"[Task 16] Processing: '{delivery_name}'")
        
        if DRY_RUN:
            print(f"[Task 16] DRY_RUN=True → would delete: {delivery_name}")
            continue
        
        # On retry, check if row still exists before trying to delete
        if is_retry:
            try:
                row_exists = page.get_by_role("cell", name=delivery_name).count() > 0
                if not row_exists:
                    print(f"[Task 16] RETRY: '{delivery_name}' already deleted, skipping")
                    continue
            except Exception:
                pass  # if check fails, try the delete anyway
        
        found = False

        # METHOD 1: Find cells and click the LAST one (in Additional Details)
        
        try:
            # Click Additional Details heading to activate section
            with suppress(Exception):
                heading = page.get_by_role("heading", name=re.compile(r"Additional Details", re.I))
                if heading.count() > 0:
                    heading.first.click()
                    snooze(500)
            
            # Try to find the cell that contains both the row text and "Extract Delivery Mode"
            target = page.get_by_role("cell", name=re.compile(rf"{re.escape(delivery_name)}.*Extract Delivery Mode", re.I))
            
            if target.count() == 0:
                # Fallback: just look for cell with the delivery name
                target = page.locator("role=cell").filter(has_text=delivery_name)
            
            if target.count() > 0:
                print(f"[Task 16] Found {target.count()} cell(s) containing '{delivery_name}'")
                print(f"[Task 16] Clicking last cell (Additional Details row)...")
                
                target.last.click()
                
                print(f"[Task 16] Waiting for Oracle to enable Delete button...")
                snooze(3000)
                found = True
                
        except Exception as e:
            print(f"[Task 16] Method 1 failed: {e}")
                
        except Exception as e:
            print(f"[Task 16] Method 1 failed: {e}")

        # METHOD 2: Fallback - try finding row
        if not found:
            try:
                print(f"[Task 16] Trying fallback method...")
                rows = page.locator("tr").filter(has_text=delivery_name)
                
                if rows.count() > 0:
                    # Click last row
                    rows.last.locator("td").filter(has_text=delivery_name).first.locator("span").nth(1).click()
                    
                    print(f"[Task 16] (Fallback) Waiting for Oracle to enable Delete button...")
                    snooze(3000)
                    found = True
                    
            except Exception as e:
                print(f"[Task 16] Fallback failed: {e}")

        if not found:
            print(f"[Task 16]  WARNING: Could not find row for '{delivery_name}'")
            failed_deletes.append(delivery_name)
            continue

        # DELETE
        try:
            # Wait for delete button to be enabled
            delete_btns = page.get_by_role("button", name=re.compile(r"^Delete$", re.I))
            print(f"[Task 16] Found {delete_btns.count()} Delete buttons")
            
            if delete_btns.count() >= 3:
                delete_btns.nth(2).click()
            else:
                delete_btns.last.click()
            
            snooze(1000)
            screenshot(page, "task16")
            
            # Confirm deletion
            try_click(page.get_by_role("button", name=re.compile(r"^(Yes|OK)$", re.I)))
            snooze(1000)
            
            print(f"[Task 16]  Successfully deleted '{delivery_name}'")
        # Save and Done
            print("[Task 16] Saving changes...")
            try_click(page.get_by_role("button", name=re.compile(r"^Save", re.I)))
            snooze(1000)

            print("[Task 16] Clicking Done...")
            try_click(page.get_by_role("button", name=re.compile(r"^Done", re.I)))
            snooze(500)

            print("[Task 16]  Prenote deliveries deleted and saved!")
        except Exception as e:
            print(f"[Task 16]  ERROR: Failed to delete '{delivery_name}': {e}")
    if failed_deletes:
        raise RuntimeError(f"[Task 16] Failed to delete {len(failed_deletes)} row(s): {failed_deletes}")

# =====================================================
# Task 17 — ADMIN User Accounts creation ((client)s)
# =====================================================
def task17_admin_user_accounts_creation(page, PAUSE=3500, DRY_RUN=True):
    """
    Create two OPKey admin users in Security Console.
    
    WHAT IT DOES:
        Creates two administrative user accounts for OPKey automation:
        
        User 1: (client)
            - Name: (client) BI Administrator
            - Email: (client)@demo.com
            - Password: (client)
            - Role: (client)-BPR BI Administrator
        
        User 2: (client)
            - Name: (client) Sec Administrator
            - Email: (client)@demo.com
            - Password: (client)
            - Role: IT Security Manager
    DESIGN DECISION:
    I made it hardcode becuase it worked best like that when I was developing it.
    Since it is account creation i wanted it to be as accurate as possible.
    Could be improved on by say making the passwords dynamic like called from function or from the env.

    1.0.2 changes:
    Changed the way we click on the users tab in security console to be more secure and try multiple methods.
    """
    import re

    def snooze(ms=PAUSE):
        page.wait_for_timeout(ms)

    def try_click(loc, timeout=9000):
        try:
            loc.wait_for(state="visible", timeout=timeout)
            loc.click(timeout=timeout)
            return True
        except Exception:
            return False

    # Task 17 ADMIN User Accounts creation
    page.get_by_role("link", name="Navigator").click()
    snooze()

    #page.get_by_title("Tools", exact=True).locator("div").nth(1).click() # don't need these step, this step won't work because the tools section dropdown is already open, if not open uncomment
    #snooze()

    # Try Security Console directly (works if Tools already expanded)
    if not try_click(page.get_by_role("link", name="Security Console")):
        # Tools section must be collapsed — expand it first
        try_click(page.get_by_title("Tools", exact=True).locator("div").nth(1)); snooze()
        page.get_by_role("link", name="Security Console").click()
    snooze()

    #page.get_by_role("button", name="OK").click()
    #snooze()
        # Give Oracle a second to fully render the Security Console menu/tile area
    snooze(1500)

    if not (
        try_click(page.get_by_title("Users")) or
        try_click(page.get_by_role("link", name="Users")) or
        try_click(page.get_by_role("link", name="Users Users"))
    ):
        raise RuntimeError("Could not open Users in Security Console.") #these are the changed lines in 1.0.2

    snooze()
    #page.get_by_role("link", name="Users").click() #sometimes this box will be name = "Users Users" if the current ="Users" is where fail happens try ="Users Users"
   # snooze()

    # -------- First user: (client) ((client)-BPR BI Administrator) --------
    page.get_by_role("button", name="Add User Account").click()
    snooze()
    #screenshot(page)

    page.get_by_role("textbox", name="First Name").click()
    snooze()
    page.get_by_role("textbox", name="First Name").fill("(client)") 
    #these sections of user generation is where you would have to change in cod eif you wanted to do a different account name/password
    snooze()

    page.get_by_role("textbox", name="Last Name").click()
    snooze()
    page.get_by_role("textbox", name="Last Name").fill("BI Administrator")
    snooze()

    page.get_by_role("textbox", name="Email").click()
    snooze()
    page.get_by_role("textbox", name="Email").fill("(client)@demo.com")
    snooze()

    page.get_by_role("textbox", name="User Name").click()
    snooze()
    page.get_by_role("textbox", name="User Name").press("ControlOrMeta+a")
    snooze()
    page.get_by_role("textbox", name="User Name").fill("(client)")
    snooze()

    page.get_by_role("textbox", name="Password", exact=True).click()
    snooze()
    page.get_by_role("textbox", name="Password", exact=True).fill("(client)")
    snooze()

    page.get_by_role("textbox", name="Confirm Password").click()
    snooze()
    page.get_by_role("textbox", name="Confirm Password").fill("(client)")
    snooze()
    screenshot(page, "task17")

    page.get_by_role("button", name="Add Role").click()
    snooze()

    page.get_by_placeholder("Enter 3 or more characters to").click()
    snooze()
    page.get_by_placeholder("Enter 3 or more characters to").fill("(client)-BPR BI Administrator")
    snooze()
    #screenshot(page)

    page.locator("[id=\"__af_Z_window\"]").get_by_role("link", name="Search").click()
    snooze()

    page.get_by_role("button", name="Add Role Membership").click()
    snooze()
    screenshot(page, "task17")

    page.get_by_role("button", name="Done").click()
    snooze()
    #screenshot(page)

    # ------ Save/Cancel for first user (DRY_RUN aware) -------
    if not DRY_RUN:
        page.get_by_role("button", name="Save and Close").click()
        snooze()
    else:
        page.get_by_role("button", name="Cancel").click()
        snooze()

    # -------- Second user: (client) (IT Security Manager) --------
    page.get_by_role("button", name="Add User Account").click()
    snooze()

    page.get_by_role("textbox", name="First Name").click()
    snooze()
    page.get_by_role("textbox", name="First Name").fill("(client)")
    snooze()
    #screenshot(page)

    page.get_by_role("textbox", name="Last Name").click()
    snooze()
    page.get_by_role("textbox", name="Last Name").fill("Sec Administrator")
    snooze()

    page.get_by_role("textbox", name="Email").click()
    snooze()
    page.get_by_role("textbox", name="Email").fill("(client)@demo.com")
    snooze()

    page.get_by_role("textbox", name="User Name").click()
    snooze()
    page.get_by_role("textbox", name="User Name").press("ControlOrMeta+a")
    snooze()
    page.get_by_role("textbox", name="User Name").fill("(client)")
    snooze()

    page.get_by_role("textbox", name="Password", exact=True).click()
    snooze()
    page.get_by_role("textbox", name="Password", exact=True).fill("(client)")
    snooze()

    page.get_by_role("textbox", name="Confirm Password").click()
    snooze()
    page.get_by_role("textbox", name="Confirm Password").fill("(client)")
    snooze()
    screenshot(page, "task17")

    page.get_by_role("button", name="Add Role").click()
    snooze()

    page.get_by_placeholder("Enter 3 or more characters to").click()
    snooze()
    page.get_by_placeholder("Enter 3 or more characters to").fill("IT Security Manager")
    snooze()
    #screenshot(page)

    page.locator("[id=\"__af_Z_window\"]").get_by_role("link", name="Search").click()
    snooze()
    
    page.get_by_role("button", name="Add Role Membership").click()
    snooze()
    screenshot(page, "task17")

    page.get_by_role("button", name="Done").click()
    snooze()

    # ------ Save/Cancel for second user (DRY_RUN aware) -------
    if not DRY_RUN:
        page.get_by_role("button", name="Save and Close").click()
        snooze()
    else:
        page.get_by_role("button", name="Cancel").click()
        snooze()
    
    page.locator("td").filter(has_text=re.compile(r"^Home$")).click()
    snooze()

    print(f"[Task 17] Admin user accounts creation complete. DRY_RUN={DRY_RUN}")
# =====================================================
# Task 18 — Admin Tech User (env-specific GUID user)
# =====================================================
def task18_admin_tech_user_creation(
    page,
    username: str,
    PAUSE: int = 3500,
    DRY_RUN: bool = True,
):
    """
    Create a technical admin user with environment-specific GUID username.
    
    WHAT IT DOES:
        Creates one technical admin user where:
        - User Name = {username} (GUID like "dededde")
        - Last Name = {username}
        - Password = {username}
        - Roles: 4 Application Implementation roles + IT Integration Specialist
    PARAMETERS:
        username: Environment-specific GUID (e.g., "dedededed" for DEV1)
    
    """

    import re
    from contextlib import suppress

    def snooze(ms=PAUSE):
        page.wait_for_timeout(ms)

    def try_click(loc, timeout=9000):
        """Helper: Try to click element, return True if successful."""
        try:
            loc.wait_for(state="visible", timeout=timeout)
            loc.click(timeout=timeout)
            return True
        except Exception:
            return False

    print(f"[Task 18] Creating admin tech user '{username}' (DRY_RUN={DRY_RUN})")

    # ----------------- Navigate to Users -----------------
    # Navigator → Tools → Security Console → Users
    try_click(page.get_by_role("link", name="Navigator")); snooze()

    # Tools tile (same as other tasks) don't need because already open
    #if not try_click(page.get_by_title("Tools", exact=True).locator("div").nth(1)):
      #  try_click(page.get_by_role("link", name=re.compile(r"^Tools$", re.I)))
   # snooze()

    
    # Try Security Console directly (works if Tools already expanded)
    if not try_click(page.get_by_role("link", name="Security Console")):
        # Tools section must be collapsed — expand it first
        try_click(page.get_by_title("Tools", exact=True).locator("div").nth(1)); snooze()
        page.get_by_role("link", name="Security Console").click()
    snooze()

    # Some tenants show "Users Users"
    if not try_click(page.get_by_role("link", name=re.compile(r"^Users Users$", re.I))):
        try_click(page.get_by_role("link", name=re.compile(r"^Users$", re.I)))
    snooze()

    # ----------------- Add User Account -----------------
    try_click(page.get_by_role("button", name="Add User Account")); snooze()
    #screenshot(page)

    # First Name 
    with suppress(Exception):
        fn = page.get_by_role("textbox", name="First Name")
        fn.click(); snooze(120)
        fn.fill(username); snooze(150)

    # Last Name = username
    ln = page.get_by_role("textbox", name="Last Name")
    ln.click(); snooze(120)
    ln.fill(username); snooze(150)

    # User Name = username
    un = page.get_by_role("textbox", name="User Name")
    un.click(); snooze(120)
    with suppress(Exception):
        un.press("ControlOrMeta+A"); snooze(80)
    un.fill(username); snooze(150)

    # Password + Confirm = username
    pw = page.get_by_role("textbox", name="Password", exact=True)
    pw.click(); snooze(120)
    pw.fill(username); snooze(150)

    cpw = page.get_by_role("textbox", name="Confirm Password")
    cpw.click(); snooze(120)
    cpw.fill(username); snooze(150)
    screenshot(page, "task18")

    # ----------------- Add Roles -----------------
    roles_to_add = [
        "Application Implementation Administrator",
        "Application Implementation Consultant",
        "Application Implementation Manager",
        "(client)-BPR_IT_INTEGRATION_SPECIALIST_JOB",
        "(client)-BPR_IT_INTEGRATION_SPECIALIST_DATA",
    ]

    for role_name in roles_to_add:
        print(f"   [Task 18] Adding role: {role_name}")
        # Click Add Role
        try_click(page.get_by_role("button", name="Add Role")); snooze()

        # Role search LOV textbox (same pattern as Task 17)
        srch = page.get_by_placeholder("Enter 3 or more characters to") #need to enter 3 to get the correct role to show
        srch.click(); snooze(120)
        srch.fill(role_name); snooze(250)
        #screenshot(page)

        # Click Search in the LOV popup
        with suppress(Exception):
            page.locator("[id=\"__af_Z_window\"]").get_by_role("link", name="Search").click()
        snooze(250)

        # Add Role Membership
        try_click(page.get_by_role("button", name="Add Role Membership")); snooze()
        screenshot(page, "task18")
        # Done for this role
        try_click(page.get_by_role("button", name="Done")); snooze()

    # ----------------- Save / Cancel (DRY_RUN aware) -----------------
    if not DRY_RUN:
        print(f"[Task 18] Saving user {username}")
        with suppress(Exception):
            page.get_by_role("button", name="Save and Close").click()
            snooze()
    else:
        print(f"[Task 18] DRY_RUN=True → cancelling instead of saving user {username}")
        with suppress(Exception):
            page.get_by_role("button", name="Cancel").click()
            snooze()

    # Back Home (optional)
    with suppress(Exception):
        page.get_by_role("link", name="Home", exact=True).click()
        snooze()

    print(f"[Task 18] Admin tech user '{username}' complete. DRY_RUN={DRY_RUN}")

# =====================================================
# Task 20 — Preferred Gender / Absence Links in Structure THIS TASK IS INCOMPLETE TOO LOW SUCCESS RATE
# =====================================================
def task20_update_preferred_gender_links(
    page,
    FUSION_BASEURL: str,
    PAUSE: int = 3500,
    DRY_RUN: bool = True,
    home_url: str | None = None,
    sandbox_name: str = "Test-03",
):
    """
    Creates/enters a Structure sandbox and updates:
      - Preferred Gender destination
      - Request for Absence destination
      - Resignation / Retirement destination

    All URLs are built from FUSION_BASEURL so you only change the base once.
    """

    if not FUSION_BASEURL:
        raise ValueError(
            "FUSION_BASEURL is required "
            "(e.g. 'https://(client)-(client).fa.ocs.oraclecloud.com')."
        )

    def snooze(ms=PAUSE):
        page.wait_for_timeout(ms)

    def try_click(loc, timeout=10_000):
        try:
            loc.wait_for(state="visible", timeout=timeout)
            loc.click(timeout=timeout)
            return True
        except Exception:
            return False

    def overwrite_destination(full_url: str):
        dest_box = page.get_by_role("textbox", name="Destination")
        dest_box.click()
        dest_box.press("ControlOrMeta+a")
        dest_box.fill(full_url)
        snooze()
        if not DRY_RUN:
            page.get_by_role("button", name="Save and Close").click()
            snooze()
        else:
            print(f"[Task 20] DRY RUN - would Save and Close with Destination={full_url!r}")

    # ---------- Build URLs from base ----------
    PREF_GENDER_URL = (
        FUSION_BASEURL
        + "/fscmUI/faces/deeplink"
          "?objType=DOCUMENT_RECORDS_ANY"
          "&action=NONE"
          "&objKey=pSystemDocType=GLB_PREFERRED_GENDER;pMode=CREATE"
    )

    REQUEST_ABSENCE_URL = (
        FUSION_BASEURL
        + "/fscmUI/faces/deeplink"
          "?objType=DOCUMENT_RECORDS_ANY"
          "&action=NONE"
          "&objKey=pSystemDocType=GLB_REQUEST_FOR_ABSENCE;pMode=CREATE"
    )

    RESIGN_RETIRE_URL = (
        FUSION_BASEURL
        + "/fscmUI/redwood/worker-journeys/journey/journey-details"
          "?navigateBackFlag=true"
          "&journeyId=300000019269671"
    )

    # This is the “Structure” sandbox overview URL you recorded
    SANDBOX_FUSE_URL = (
        FUSION_BASEURL
        + "/fscmUI/faces/FuseOverview"
          "?_afrLoop=25371528852976568"
          "&fndGlobalItemNodeId=itemNode_tools_sandboxes"
          "&_adf.ctrl-state=1bkbq4n8tv_530"
    )

    # ---------- Normalize to Home ----------
    if home_url:
        page.goto(home_url)
        page.wait_for_load_state("domcontentloaded")
        snooze()

    # ---------- Navigator → Tools → My Client Groups → Configuration ----------
    with suppress(Exception):
        try_click(page.get_by_role("link", name="Home", exact=True))
        snooze()

    if not try_click(page.get_by_role("link", name="Navigator")):
        raise RuntimeError("Navigator link not found.")
    snooze()

    if not try_click(page.get_by_title("Tools", exact=True).locator("div").nth(1)):
        raise RuntimeError("Tools tile not found.")
    snooze()

    if not try_click(page.get_by_title("My Client Groups", exact=True).locator("div").nth(1)):
        raise RuntimeError("My Client Groups tile not found.")
    snooze()

    if not try_click(page.get_by_title("Configuration", exact=True).locator("div").nth(1)):
        raise RuntimeError("Configuration tile not found.")
    snooze()

    if not try_click(page.get_by_role("link", name="Sandboxes")):
        raise RuntimeError("Sandboxes link not found.")
    snooze()

    # ---------- Select Structure sandbox type ----------
    page.locator("tr").filter(has_text=re.compile(r"^Structure$")).locator("label").click()
    snooze()

    if not try_click(page.get_by_role("button", name="Create Sandbox")):
        raise RuntimeError("Create Sandbox button not found.")
    snooze()

    name_box = page.get_by_role("textbox", name="Name")
    name_box.click()
    name_box.fill(sandbox_name)
    snooze()

    if DRY_RUN:
        print(f"[Task 20] DRY RUN - would click 'Create and Enter' for sandbox {sandbox_name!r}")
    else:
        page.get_by_role("button", name="Create and Enter").click()
        snooze()

    # ---------- Go to Sandboxes → Structure (FuseOverview) ----------
    page.goto(SANDBOX_FUSE_URL)
    page.wait_for_load_state("domcontentloaded")
    snooze()

    # Menu: Tools → Structure
    if not try_click(page.get_by_role("menuitem", name="Tools").locator("div")):
        raise RuntimeError("Tools menu in Structure page not found.")
    snooze()

    page.locator('[id="__af_Z_window"]').get_by_text("Structure").click()
    snooze()

    # Expand the node and open "Preferred Gender"
    page.get_by_role("cell", name="Expand Me").get_by_role("link").first.click()
    snooze()

    # ---------- Preferred Gender ----------
    page.get_by_role("link", name="Preferred Gender", exact=True).click()
    snooze()
    overwrite_destination(PREF_GENDER_URL)

    # ---------- Request for Absence ----------
    page.get_by_role("link", name="Request for Absence").click()
    snooze()
    overwrite_destination(REQUEST_ABSENCE_URL)

    # ---------- Resignation / Retirement ----------
    page.get_by_role("link", name="Resignation / Retirement").click()
    snooze()
    overwrite_destination(RESIGN_RETIRE_URL)

    # ---------- Publish sandbox (if not DRY_RUN) ----------
    if DRY_RUN:
        print(f"[Task 20] DRY RUN - would publish sandbox {sandbox_name!r}")
    else:
        page.get_by_role("menuitem", name=re.compile(rf"^{re.escape(sandbox_name)}")).locator("div").click()
        snooze()
        page.get_by_text("Publish", exact=True).click()
        snooze()
        page.get_by_role("button", name="Yes").click()
        snooze()
        page.get_by_role("button", name="Publish").click()
        snooze()
        page.get_by_role("button", name="Yes").click()
        snooze()

    # Back Home
    with suppress(Exception):
        page.get_by_role("link", name="Home", exact=True).click()
        snooze()

    print(f"[Task 20] Preferred Gender / Absence / Resignation links updated. DRY_RUN={DRY_RUN}")

# =====================================================
# Task 21 — Disable Separate Remittance Advice outgoing emails
# =====================================================
def task21_disable_separate_remittance_emails(page, PAUSE=3500, DRY_RUN=True):
    """
    Clear the 'Separate Remittance Advice from Email' field.
    
    WHAT IT DOES:
        Navigate to Manage Disbursement System Options
        Clear the "Separate Remittance Advice from Email" field
    """
    import re
    from contextlib import suppress

    def snooze(ms=PAUSE): 
        page.wait_for_timeout(ms)

    def try_click(loc, timeout=6000):
        """Helper: Try to click element, return True if successful."""
        try:
            loc.wait_for(state="visible", timeout=timeout)
            loc.click(timeout=timeout)
            return True
        except Exception:
            return False

    # --- Navigation---
    try_click(page.get_by_role("link", name="Settings and Actions")); snooze()
    try_click(page.get_by_role("link", name="Setup and Maintenance")); snooze()
    try_click(page.get_by_role("link", name="Tasks")); snooze()

    try_click(page.locator("[id='__af_Z_window']").get_by_role("link", name="Search")); snooze()

    sb = page.get_by_label("", exact=True)
    sb.click(); snooze()
    sb.fill("Manage Disbursement System Options"); snooze()
    #screenshot(page)

    try_click(page.get_by_role("button", name="Search")); snooze()
    try_click(page.get_by_role("link", name=re.compile(r"^Manage Disbursement System", re.I))); snooze()

    # --- Clear field ---
    field = page.get_by_role("textbox", name="Separate Remittance Advice from Email")
    field.click(); snooze()
    #screenshot(page)
    with suppress(Exception):
        field.press("ControlOrMeta+A"); snooze(150)
    field.fill(""); snooze()
    screenshot(page, "task21")

    # --- Save or Cancel ---
    if not DRY_RUN:
        try_click(page.get_by_role("button", name="Save and Close")); snooze()
        with suppress(Exception):
            try_click(page.get_by_role("button", name="OK")); snooze()
    else:
        try_click(page.get_by_role("button", name="Cancel")); snooze()
        with suppress(Exception):
            try_click(page.get_by_role("button", name="Yes")); snooze()

    # --- Back Home ---
    with suppress(Exception):
        page.locator("td").filter(has_text=re.compile(r"^Home$", re.I)).click()
        snooze()

    print(f"[Task 21] Cleared 'Separate Remittance Advice from Email' field. DRY_RUN={DRY_RUN}")

#======================================================
#======================================================
#TASK 22
#======================================================
#======================================================
"""
Task 22 — Update Checklist Task URLs (Classic + Redwood Compatible)

VERSION: 1.0.2

OVERVIEW:
    This task updates task URLs inside Oracle Checklist Templates for multiple
    journeys (Medical Leave, Leave of Absence, Leave Extension).

    The implementation supports BOTH:
        - Classic UI (older Oracle pages)
        - Redwood UI (new Oracle UI framework)

WHY THIS WAS REDESIGNED (v1.0.2):
    Wasn't tested on the Redwood UI pages as Redwood for this page only came recently Mar-26.
    The previous implementation relied on static locators and assumptions about:
        - task row structure
        - edit button placement
        - page navigation

    These assumptions no longer hold in Redwood.
    But in case the UI is not in Redwood I left the other version in too.

NEW DESIGN (v1.0.2):
    The task is now split into 4 layers:

    1) Shared Navigation Layer
        - Opens Checklist Templates once
        - Avoids duplication across Classic + Redwood

    2) UI Detection Layer
        - Detects whether the page is Redwood or Classic AFTER navigation
        - Prevents incorrect early detection

    3) Wrapper Layer
        - Routes execution to the correct implementation (Redwood vs Classic)
        - Includes fallback logic if Redwood fails

    4) Implementation Layers
        - Classic flow (unchanged logic, stabilized)
        - Redwood flow (fully dynamic, locator-resilient)

KEY IMPROVEMENTS:
    - Dynamic locator strategies (no reliance on fixed DOM structure)
    - Multiple fallback selectors for all interactions
    - Row-based task detection instead of static button references
    - Reusable helper functions (click_first_working, fill_first_working)
    - Improved reliability across environments (Dev/Test/Prod)

IMPORTANT:
    Redwood detection MUST happen after opening Checklist Templates.
    Detecting earlier leads to false positives and broken flows.

RESULT:
    Task 22 is now environment-agnostic and resilient to Oracle UI changes.
"""


# =====================================================
# Task 22 — Shared opener: go to Checklist Templates
# =====================================================
def task22_open_checklist_templates_shared(
    page,
    PAUSE: int = 3500,
    home_url: str | None = None,
):
    def snooze(ms: int = PAUSE) -> None:
        page.wait_for_timeout(ms)

    def try_click(loc, timeout: int = 10000) -> bool:
        try:
            loc.wait_for(state="visible", timeout=timeout)
            loc.click(timeout=timeout)
            return True
        except Exception:
            return False

    if home_url:
        page.wait_for_load_state("domcontentloaded")
        snooze()
        with suppress(Exception):
            try_click(page.get_by_role("link", name="Home", exact=True))
            snooze()

    if not try_click(page.get_by_role("link", name="Settings and Actions")):
        raise RuntimeError("Settings and Actions link not found.")
    snooze()

    if not try_click(page.get_by_role("link", name="Setup and Maintenance")):
        raise RuntimeError("Setup and Maintenance link not found.")
    snooze()

    # Classic-only tab sometimes exists
    with suppress(Exception):
        page.locator('[id="pt1:r1:0:r0:0:r1:0:AP1:pd1::tabp"]').click()
        snooze()

    # Open search if needed
    with suppress(Exception):
        page.locator('[id="__af_Z_window"]').get_by_role("link", name="Search").click()
        snooze()

    search_box_candidates = [
        page.get_by_label("", exact=True),
        page.get_by_role("textbox", name=re.compile(r"Search", re.I)),
        page.locator("input[type='search']").first,
        page.locator("input").first,
    ]

    found_box = False
    for loc in search_box_candidates:
        try:
            loc.click()
            with suppress(Exception):
                loc.press("ControlOrMeta+a")
            loc.fill("Checklist Templates")
            snooze()
            found_box = True
            break
        except Exception:
            pass

    if not found_box:
        raise RuntimeError("Could not find Checklist Templates search box.")

    with suppress(Exception):
        page.get_by_role("button", name="Search").click()
        snooze()

    open_candidates = [
        page.get_by_role("link", name="Checklist Templates", exact=True),
        page.get_by_text("Checklist Templates", exact=True),
        page.get_by_role("button", name="Checklist Templates"),
    ]

    for loc in open_candidates:
        try:
            loc.click()
            snooze()
            return
        except Exception:
            pass

    raise RuntimeError("Checklist Templates link not found.")

# =====================================================
# Task 22 — Wrapper
# =====================================================
"""
Wrapper function that determines which UI (Classic vs Redwood) is active
and routes execution accordingly.

WHY THIS EXISTS:
    Oracle environments are inconsistent:
        - Some environments still use Classic UI
        - Others use Redwood UI
        - Some switch dynamically

    Hardcoding one flow would break the task in other environments.

HOW IT WORKS:
    1. Opens Checklist Templates using shared navigation
    2. Detects UI type INSIDE Checklist Templates
    3. Routes to:
        - Redwood implementation (preferred)
        - Classic implementation (fallback)

FALLBACK LOGIC:
    If Redwood flow fails:
        → Automatically falls back to Classic

DESIGN DECISION:
    Detection is done AFTER navigation to avoid false positives.
"""
def task22_update_checklist_urls(
    page,
    FUSION_BASEURL: str,
    PAUSE: int = 3500,
    DRY_RUN: bool = True,
    home_url: str | None = None,
):
    """Task 22 - REDWOOD ONLY (Oracle migrated to Redwood UI)"""
    
    task22_open_checklist_templates_shared(
        page,
        PAUSE=PAUSE,
        home_url=home_url,
    )
    
    # ALWAYS USE REDWOOD (no detection, no fallback)
    print("[Task 22] Using Redwood UI (Oracle's new interface)")
    return task22_update_checklist_urls_redwood(
        page,
        FUSION_BASEURL=FUSION_BASEURL,
        PAUSE=PAUSE,
        DRY_RUN=DRY_RUN,
        home_url=None,
        already_at_checklist_templates=True,
    )

# =====================================================
# Task 22 — Redwood
# =====================================================
"""
Redwood UI implementation for updating Checklist Task URLs.

WHY THIS EXISTS:
    Redwood UI changed Oracle page structure significantly:
        - No stable row structure
        - Dynamic component rendering (oj-c, oj-table, etc.)
        - "Edit Task" buttons are not tied to fixed IDs
        - Navigation behavior differs from Classic

OLD APPROACH (FAILED):
    - Click static "Edit Task" buttons
    - Assume fixed row structure
    - Use simple locators

NEW APPROACH (v1.0.2):
    Fully dynamic and resilient:

    1) Find task row dynamically
        - Uses multiple strategies:
            - role='row'
            - ancestor traversal
            - text matching

    2) Find Edit Task button INSIDE row
        - Avoids clicking wrong task
        - Uses multiple locator fallbacks

    3) Fill URL field dynamically
        - Supports different field labels ("Task URL", "URL", etc.)

    4) Navigation control
        - Uses "Go back" between journeys
        - Avoids full page reload

HELPER FUNCTIONS:
    click_first_working():
        Tries multiple locators until one works

    fill_first_working():
        Handles inconsistent textbox selectors

    find_task_row():
        Core logic for identifying correct task row

KEY BENEFIT:
    Works even if Oracle changes:
        - class names
        - DOM structure
        - button placement
"""
def task22_update_checklist_urls_redwood(
    page,
    FUSION_BASEURL: str,
    PAUSE: int = 3000,
    DRY_RUN: bool = True,
    home_url: str | None = None,
    already_at_checklist_templates: bool = False,
):
    if not FUSION_BASEURL:
        raise ValueError(
            "FUSION_BASEURL is required "
            "(e.g. 'https://(client)-(client).fa.ocs.oraclecloud.com')."
        )

    FUSION_BASEURL = FUSION_BASEURL.rstrip("/")

    def snooze(ms: int = PAUSE) -> None:
        page.wait_for_timeout(ms)

    def try_click(locator, timeout: int = 8000) -> bool:
        try:
            locator.wait_for(state="visible", timeout=timeout)
            locator.click(timeout=timeout)
            return True
        except Exception:
            return False

    def click_first_working(locators: list, what: str, timeout: int = 8000) -> None:
        last_error = None
        for loc in locators:
            try:
                loc.wait_for(state="visible", timeout=timeout)
                loc.click(timeout=timeout)
                return
            except Exception as e:
                last_error = e
        raise RuntimeError(f"Could not click {what}. Last error: {last_error}")

    def fill_first_working(locators: list, value: str, what: str, timeout: int = 8000) -> None:
        last_error = None
        for loc in locators:
            try:
                loc.wait_for(state="visible", timeout=timeout)
                loc.click(timeout=timeout)
                loc.press("ControlOrMeta+a")
                loc.fill(value, timeout=timeout)
                return
            except Exception as e:
                last_error = e
        raise RuntimeError(f"Could not fill {what}. Last error: {last_error}")

    def safe_wait_for_redwood_page(extra_ms: int = 1200) -> None:
        with suppress(Exception):
            page.wait_for_load_state("domcontentloaded", timeout=10000)
        page.wait_for_timeout(extra_ms)

    def goto_setup_and_maintenance_if_needed() -> None:
        if home_url:
            page.goto(home_url)
            safe_wait_for_redwood_page()

        entry_attempts = [
            page.get_by_role("link", name="Settings and Actions"),
            page.get_by_role("button", name="Settings and Actions"),
            page.get_by_label("Settings and Actions"),
        ]
        for entry in entry_attempts:
            if try_click(entry, timeout=5000):
                snooze()
                break

        setup_attempts = [
            page.get_by_role("link", name="Setup and Maintenance"),
            page.get_by_role("button", name="Setup and Maintenance"),
            page.get_by_text("Setup and Maintenance", exact=True),
        ]
        click_first_working(setup_attempts, "Setup and Maintenance")
        safe_wait_for_redwood_page()

    def open_checklist_templates() -> None:
        search_box_attempts = [
            page.get_by_role("textbox", name=re.compile(r"Search", re.I)),
            page.get_by_placeholder(re.compile(r"Search", re.I)),
            page.get_by_label(re.compile(r"Search", re.I)),
            page.locator("input[type='search']").first,
            page.locator("input").first,
        ]
        fill_first_working(search_box_attempts, "Checklist Templates", "Setup search box")
        snooze(1500)
        screenshot(page, "task22")

        with suppress(Exception):
            click_first_working(
                [
                    page.get_by_role("button", name=re.compile(r"Search", re.I)),
                    page.get_by_role("link", name=re.compile(r"Search", re.I)),
                ],
                "Search button",
                timeout=4000,
            )
            snooze(1500)

        templates_open_attempts = [
            page.get_by_role("link", name="Checklist Templates", exact=True),
            page.get_by_text("Checklist Templates", exact=True),
            page.get_by_role("button", name="Checklist Templates"),
        ]
        click_first_working(templates_open_attempts, "Checklist Templates")
        safe_wait_for_redwood_page(1800)

    def clear_and_search_journey(journey_name: str) -> None:
        search_box_attempts = [
            page.get_by_role("textbox", name=re.compile(r"Search by name", re.I)),
            page.get_by_role("searchbox", name=re.compile(r"Search by name", re.I)),
            page.get_by_placeholder(re.compile(r"Search by name", re.I)),
            page.get_by_role("textbox", name=re.compile(r"Search", re.I)),
            page.locator("input[type='search']").first,
        ]
        fill_first_working(search_box_attempts, journey_name, f"journey search box for {journey_name}")
        snooze(1500)
        screenshot(page, "task22")

        with suppress(Exception):
            page.keyboard.press("Enter")
            snooze(1500)

        with suppress(Exception):
            click_first_working(
                [
                    page.get_by_role("button", name=re.compile(r"Search", re.I)),
                    page.get_by_role("link", name=re.compile(r"Search", re.I)),
                ],
                "journey Search button",
                timeout=3000,
            )
            snooze(1500)

    def open_journey(journey_name: str) -> None:
        clear_and_search_journey(journey_name)

        journey_open_attempts = [
            page.get_by_role("link", name=journey_name, exact=True),
            page.get_by_text(journey_name, exact=True),
            page.get_by_role("button", name=journey_name, exact=True),
        ]
        click_first_working(journey_open_attempts, f"journey '{journey_name}'")
        safe_wait_for_redwood_page(2000)

    def find_task_row(task_name: str):
        task_text_exact = page.get_by_text(task_name, exact=True)
        task_text_loose = page.get_by_text(re.compile(re.escape(task_name), re.I))

        with suppress(Exception):
            task_text_exact.first.scroll_into_view_if_needed(timeout=3000)
        with suppress(Exception):
            task_text_loose.first.scroll_into_view_if_needed(timeout=3000)

        candidate_locators = [
            page.get_by_role("row", name=re.compile(re.escape(task_name), re.I)).first,
            page.locator("[role='row']", has=task_text_exact).first,
            page.locator("[role='row']", has=task_text_loose).first,
            page.locator("tr", has=task_text_exact).first,
            page.locator("tr", has=task_text_loose).first,
            task_text_exact.locator(
                "xpath=ancestor::*[self::tr or @role='row' or contains(@class,'oj-table-body-row') "
                "or contains(@class,'oj-c-table-body-row') or contains(@class,'oj-table-data-row')][1]"
            ).first,
            task_text_loose.locator(
                "xpath=ancestor::*[self::tr or @role='row' or contains(@class,'oj-table-body-row') "
                "or contains(@class,'oj-c-table-body-row') or contains(@class,'oj-table-data-row')][1]"
            ).first,
            page.locator("div", has=task_text_exact).filter(
                has=page.get_by_text(re.compile(r"Edit Task", re.I))
            ).first,
            page.locator("div", has=task_text_loose).filter(
                has=page.get_by_text(re.compile(r"Edit Task", re.I))
            ).first,
        ]

        last_error = None
        for loc in candidate_locators:
            try:
                if loc.count() > 0:
                    with suppress(Exception):
                        loc.scroll_into_view_if_needed(timeout=3000)
                    return loc
            except Exception as e:
                last_error = e

        raise RuntimeError(f"Could not find row/container for task '{task_name}'. Last error: {last_error}")

    def click_edit_task_for_row(task_name: str) -> None:
        row = find_task_row(task_name)

        edit_candidates = [
            row.get_by_role("button", name=re.compile(r"^Edit Task$", re.I)).first,
            row.get_by_role("link", name=re.compile(r"^Edit Task$", re.I)).first,
            row.get_by_label(re.compile(r"Edit Task", re.I)).first,
            row.locator("button", has_text=re.compile(r"Edit Task", re.I)).first,
            row.locator("a", has_text=re.compile(r"Edit Task", re.I)).first,
            row.locator("[role='button']", has_text=re.compile(r"Edit Task", re.I)).first,
            row.locator("*", has_text=re.compile(r"Edit Task", re.I)).first,
        ]

        last_error = None
        for edit in edit_candidates:
            try:
                if edit.count() > 0:
                    edit.scroll_into_view_if_needed(timeout=3000)
                    edit.click(timeout=8000)
                    safe_wait_for_redwood_page(2200)
                    return
            except Exception as e:
                last_error = e

        raise RuntimeError(
            f"Found row for task '{task_name}', but could not find/click dynamic Edit Task. "
            f"Last error: {last_error}"
        )

    def set_task_url(full_url: str) -> None:
        url_box_attempts = [
            page.get_by_role("textbox", name=re.compile(r"Task URL", re.I)),
            page.get_by_role("textbox", name=re.compile(r"URL", re.I)),
            page.get_by_label(re.compile(r"Task URL", re.I)),
            page.get_by_label(re.compile(r"URL", re.I)),
            page.locator("input[type='url']").first,
            page.locator("textarea").first,
            page.locator("input").first,
        ]

        fill_first_working(url_box_attempts, full_url, "Task URL field")
        snooze(1800)
        screenshot(page, "task22")

        if DRY_RUN:
            print(f"[Task 22 Redwood] DRY RUN - would Save URL: {full_url}")
            cancel_attempts = [
                page.get_by_role("button", name=re.compile(r"^Cancel$", re.I)),
                page.get_by_role("link", name=re.compile(r"^Cancel$", re.I)),
                page.get_by_text(re.compile(r"^Cancel$", re.I)),
            ]
            click_first_working(cancel_attempts, "Cancel button")
            safe_wait_for_redwood_page(1800)
            return

        save_attempts = [
            page.get_by_role("button", name=re.compile(r"^Save$", re.I)),
            page.get_by_role("button", name=re.compile(r"Save and Close", re.I)),
            page.get_by_text(re.compile(r"^Save$", re.I)),
        ]
        click_first_working(save_attempts, "Save button")
        safe_wait_for_redwood_page(2200)

    def go_back() -> None:
        back_attempts = [
            page.get_by_role("button", name=re.compile(r"Go back", re.I)),
            page.get_by_role("link", name=re.compile(r"Go back", re.I)),
            page.get_by_label(re.compile(r"Go back", re.I)),
            page.get_by_role("button", name=re.compile(r"Back", re.I)),
        ]
        click_first_working(back_attempts, "Go back")
        safe_wait_for_redwood_page(2200)

    FMLA_BIP_URL = (
        FUSION_BASEURL
        + "/analytics/saw.dll?bipublisherEntry&Action=open&itemType=.xdo"
          "&bipPath=%2FCustom%2FHuman%20Capital%20Management%2F(client)%20Reports%2FCore%20HR"
          "%2F(client)%20FMLA%20Eligibility%20Approval%20Tracker"
          "%2F(client)_FMLA_Eligibility_Approval_Tracker_RPT.xdo"
          "&path=%2Fshared%2FCustom%2FHuman%20Capital%20Management%2F(client)%20Reports%2FCore%20HR"
          "%2F(client)%20FMLA%20Eligibility%20Approval%20Tracker"
          "%2F(client)_FMLA_Eligibility_Approval_Tracker_RPT.xdo"
    )

    CHECK_LEAVE_ELIG_URL = (
        FUSION_BASEURL
        + "/hcmUI/faces/FndOverview?fnd=%3B%3B%3B%3Bfalse%3B256%3B%3B%3B"
          "&fndGlobalItemNodeId=itemNode_workforce_management_absence_administration"
          "&_adf.ctrl-state=xbnctuo83_1&_afrLoop=4848888649830289&_afrWindowMode=0"
          "&_afrWindowId=null&_afrFS=16&_afrMT=screen&_afrMFW=1920&_afrMFH=899"
          "&_afrMFDW=1280&_afrMFDH=720&_afrMFC=8&_afrMFCI=0&_afrMFM=0&_afrMFR=96"
          "&_afrMFG=0&_afrMFS=0&_afrMFO=0"
    )

    DOC_RECORDS_URL = (
        FUSION_BASEURL
        + "/fscmUI/redwood/human-resources/feature/launch"
          "?vbFlowStringKey=documentRecords"
          "&action=ManageDocumentRecords"
          "&vbAppUi=person-documentrecords"
          "&vbcsFlow=documentrecords"
          "&vbPage=documentrecords-list"
          "&vbPageParams=pCaller%3DMyClientGroups"
    )

    ENTER_ABSENCE_ADMIN_URL = (
        FUSION_BASEURL
        + "/fscmUI/redwood/human-resources/feature/launch"
          "?vbFlowStringKey=manageAbsencesAndEntitlements"
          "&action=ManageAbsenceRecords"
          "&fndGlobalItemNodeId=itemNode_workforce_management_absence_administration"
          "&invokedFromLandingPage=true"
          "&vbAppUi=absences"
          "&vbcsFlow=absence-administration"
          "&vbPage=manage-absences-plans"
          "&useSessionStoredFilters=true"
    )

    ENTER_ABSENCE_DEEPLINK_URL = (
        FUSION_BASEURL
        + "/fscmUI/faces/deeplink?objType=ABSENCE_RECORDS&action=NONE"
    )

    RESIGNATION_ACTION_URL = (
        FUSION_BASEURL
        + "/fscmUI/redwood/employment-termination/update/resign-from-employment"
          "?JourneyFlow=4Dd9LdBxzlfd1584XrTm%2FOeUKs7F4Je2AnzBgskm"
    )

    journey_map = {
        "Medical Leave Journey": {
            "FMLA Eligibility Report": FMLA_BIP_URL,
            "Check Leave Eligibility": CHECK_LEAVE_ELIG_URL,
            "Send Leave Paperwork": DOC_RECORDS_URL,
            "Validate Leave Paperwork": DOC_RECORDS_URL,
            "Send Approval Letter": DOC_RECORDS_URL,
            "Enter Absence": ENTER_ABSENCE_ADMIN_URL,
        },
        "Leave of Absence": {
            "FMLA Eligibility Report": FMLA_BIP_URL,
            "Send Leave Paperwork": DOC_RECORDS_URL,
            "Enter Absence": ENTER_ABSENCE_ADMIN_URL,
        },
        "Leave Extension": {
            "Update Medical Request": DOC_RECORDS_URL,
            "Enter Absence": ENTER_ABSENCE_DEEPLINK_URL,
        },
        "Resignation / Retirement Off Boarding": {
            "Submit Resignation / Retirement": RESIGNATION_ACTION_URL,
        },
    }

    if not already_at_checklist_templates:
        goto_setup_and_maintenance_if_needed()
        open_checklist_templates()

    for journey_name, tasks in journey_map.items():
        print(f"[Task 22 Redwood] Opening journey: {journey_name}")
        open_journey(journey_name)

        for task_name, target_url in tasks.items():
            print(f"[Task 22 Redwood] Editing task: {journey_name} -> {task_name}")
            click_edit_task_for_row(task_name)
            set_task_url(target_url)
            snooze(1500)
            screenshot(page, "task22")

        print(f"[Task 22 Redwood] Finished journey: {journey_name} - going back for next journey")
        go_back()
        snooze(1500)

    print(f"[Task 22 Redwood] Checklist URLs updated. DRY_RUN={DRY_RUN}")
# =====================================================
# Task 23 — Workforce Structure: Positions (E-Flexfields)
# =====================================================
def task23_workforce_structure_positions(page, PAUSE=3500, DRY_RUN=True):
    """
    Deploy and refresh extensible flexfields for Position data.
    WHAT IT DOES:
        Navigate to Manage Extensible Flexfields
        Filter for PER_POSITIONS_ flexfields
        Deploy/refresh two position flexfields:
        1) Position EIT Information
        2) Position Legislative Information
        
        For each flexfield:
        - First: Deploy Offline
        - Then: Actions → Refresh & Deploy Offline
    DESIGN DECISION - Exact Sequence:
        The order matters:
        1. Deploy EIT
        2. Deploy Legislative
        3. Refresh & Deploy EIT
        4. Refresh & Deploy Legislative
        
        Doing both deploys first, then both refreshes ensures dependencies
        resolve correctly. And when having code do both at once it would not for some reason register both to deploy so had to do one at a time deploy and then refresh.
    """
    import re
    from contextlib import suppress

    def snooze(ms=PAUSE): page.wait_for_timeout(ms)
    def try_click(loc, timeout=8000):
        """Helper: Try to click element, return True if successful."""
        try:
            loc.wait_for(state="visible", timeout=timeout)
            loc.click(timeout=timeout)
            return True
        except Exception:
            return False

    def confirm_ok_or_cancel():
        if DRY_RUN:
            with suppress(Exception):
                try_click(page.get_by_role("button", name="Cancel")); snooze()
            return
        try_click(page.get_by_role("button", name="OK")); snooze()

    # --- Navigate to Manage Extensible Flexfields ---
    try_click(page.get_by_role("link", name="Settings and Actions")); snooze()
    try_click(page.get_by_role("link", name="Setup and Maintenance")); snooze()
    try_click(page.get_by_role("link", name="Tasks")); snooze()

    try_click(page.locator("[id='__af_Z_window']").get_by_role("link", name="Search")); snooze()
    sb = page.get_by_label("", exact=True)
    sb.click(); snooze()
    sb.fill("Manage Extensible "); snooze()
    #screenshot(page)
    try_click(page.get_by_role("button", name="Search")); snooze()
    try_click(page.get_by_role("link", name="Manage Extensible Flexfields")); snooze()

    # --- Filter Flexfield Code: PER_POSITIONS_ ---
    ffc = page.get_by_role("textbox", name="Flexfield Code")
    ffc.click(); snooze()
    ffc.fill("PER_POSITIONS_"); snooze()
    with suppress(Exception):
        ffc.press("Enter"); snooze(400)

    # --- Select Position EIT Information → Deploy Offline ---
   
    try_click(page.get_by_text("Position EIT Information", exact=True)); snooze()
    #screenshot(page)
    try_click(page.get_by_role("button", name="Deploy Offline")); snooze()
    confirm_ok_or_cancel()

    # --- Select Position Legislative Information → Deploy Offline ---
    try_click(page.get_by_text("Position Legislative Information", exact=True)); snooze()
    #screenshot(page)
    try_click(page.get_by_role("button", name="Deploy Offline")); snooze()
    confirm_ok_or_cancel()

    # --- Select Position EIT Information → Actions → Refresh & Deploy Offline ---
    
    with suppress(Exception):
        try_click(page.get_by_role("cell", name="Position EIT Information", exact=True)); snooze()
    try_click(page.get_by_role("menuitem", name="Actions").locator("div")); snooze()
    try_click(page.get_by_text("Refresh & Deploy Offline")); snooze()
    #screenshot(page)
    confirm_ok_or_cancel()

    # --- Select Position Legislative Information → Actions → Refresh & Deploy Offline ---
    try_click(page.get_by_text("Position Legislative Information", exact=True)); snooze()
    # some tenants show Actions as a link; keep both fallbacks
    if not try_click(page.get_by_role("link", name="Actions", exact=True)):
        try_click(page.get_by_role("menuitem", name="Actions").locator("div"))
    snooze()
    try_click(page.get_by_text("Refresh & Deploy Offline")); snooze()
    screenshot(page, "task23")
    confirm_ok_or_cancel()

    # --- Done → Home ---
    with suppress(Exception):
        try_click(page.get_by_role("button", name="Done")); snooze()
    with suppress(Exception):
        try_click(page.get_by_role("link", name="Home", exact=True)); snooze()

    print(f"[Task 23] Position EIT + Legislative: Deploy + Refresh&Deploy done. DRY_RUN={DRY_RUN}")



 #=====================================================
# Main Playwright Runner
# =====================================================
def run(playwright: Playwright) -> None:
    import argparse
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--tasks", type=str, default="all")
    cli_args, _ = parser.parse_known_args()
    
    run_ess = False
    tasks_to_run = set()
    
    if cli_args.tasks.lower() == "all":
        tasks_to_run = "all"
        run_ess = True
    else:
        for item in cli_args.tasks.split(","):
            item = item.strip().upper()
            if item == "ESS":
                run_ess = True
            else:
                try:
                    tasks_to_run.add(int(item))
                except ValueError:
                    print(f"[WARNING] Ignoring unknown task: {item}")
    
    def should_run(task_num):
        """Check if a task should run based on --tasks argument."""
        if tasks_to_run == "all":
            return True
        return task_num in tasks_to_run
    # =========================
    # Session 1: Data Access
    # =========================
    print("\n[Session 1] Starting procurement data-access setup...")

    context1 = playwright.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR,
        headless=False,
    )
    page1 = context1.new_page()

    print(f"[Run] Launching environment: {INSTANCE_URL}")
    print(f"[Run] Using persistent profile: {PROFILE_DIR}")

    # Login + go Home
    ensure_logged_in_and_home(
        page1,
        INSTANCE_URL,
        FUSION_USERNAME,
        FUSION_PASSWORD,
        HOME_URL,
        PAUSE=PAUSE,
    )
    
    if should_run(0):
        # Run your data access step and roles, comment out if not needed
        setup_procurement_access_for_user(
            page1,
            user_search_text="(client).(client)",
            user_link_text="(client) (client)",
            user_login_option="(client).(client)",
            PAUSE=PAUSE,
            DRY_RUN=DRY_RUN,
            
        )
    
    print("[Session 1] Procurement access completed. Closing browser...")
    context1.close()

    # =========================
    # Session 2: Main tasks
    # =========================
    print("\n[Session 2] Starting main post-refresh tasks...")

    context2 = playwright.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR,
        headless=False,
    )
    page = context2.new_page()

    print(f"[Run] Launching environment: {INSTANCE_URL}")
    print(f"[Run] Using persistent profile: {PROFILE_DIR}")

    # Login again with fresh session
    ensure_logged_in_and_home(
        page,
        INSTANCE_URL,
        FUSION_USERNAME,
        FUSION_PASSWORD,
        HOME_URL,
        PAUSE=PAUSE,
    )
    

    
    
    if should_run(1):
        run_task_safe(
            "Task 1 — Disable Notifications",
            task1_disable_notifications,
            page,
            HOME_URL,
            PAUSE=PAUSE,
            DRY_RUN=DRY_RUN,
            home_url=HOME_URL,
            max_retries=2,
        )
        
    if should_run(2):
        run_task_safe(
            "Task 2 — Banner Message",
            task2_banner_message,
            page,
            HOME_URL,
            PAUSE=PAUSE,
            DRY_RUN=DRY_RUN,
            instance_label=INSTANCE_LABEL,
            max_retries=2,
        )
        
        #task2_2_update_logo_theme(page, PAUSE=PAUSE, DRY_RUN=DRY_RUN, image_root_dir="branding") Success rate too low needs fixe or to be deleted
    if should_run(3):    
        run_task_safe(
            "Task 3 — Disable ADP Deliveries",
            task3_disable_adp_deliveries,
            page,
            HOME_URL,
            PAUSE=PAUSE,
            DRY_RUN=DRY_RUN,
            max_retries=2,
        )
    if should_run(4):    
        run_task_safe(
            "Task 4 — Add IP",
            task4_add_ip,
            page,
            HOME_URL,
            PAUSE=PAUSE,
            ip_list=["(client)", "(client)", "(client)"],
            append=True,
            DRY_RUN=DRY_RUN,
            max_retries=2,
        )
    if should_run(7):    
        run_task_safe(
            "Task 7 — Turn Off PO Communication",
            task7_turn_off_po_communication,
            page,
            HOME_URL,
            PAUSE=PAUSE,
            DRY_RUN=DRY_RUN,
            max_retries=2,
        )
    if should_run(9):    
        run_task_safe(
            "Task 9 — Disable AP Payment Transmission",
            task9_disable_ap_payment_transmission,
            page,
            HOME_URL,
            PAUSE=PAUSE,
            DRY_RUN=DRY_RUN,
            max_retries=2,
        )
    if should_run(10):    
        run_task_safe(
            "Task 10 — Update Corp Card Program",
            task10_update_corp_card_program_to_nonprod_sftp,
            page,
            HOME_URL,
            PAUSE=PAUSE,
            existing_profile_name="(client)",
            new_download_profile_name="(client)XX",
            new_account_name="(client)_(client)XX",
            DRY_RUN=DRY_RUN,
            max_retries=2,
        )
    if should_run(11):    
        run_task_safe(
            "Task 11 — Disable GetThere Configuration",
            task11_disable_getthere_configuration,
            page,
            HOME_URL,
            PAUSE=PAUSE,
            username="XXXDemo",
            password="XXX(client)",
            DRY_RUN=DRY_RUN,
            max_retries=2,
        )
    if should_run(12):    
        run_task_safe(
            "Task 12 — Remove Receivables Emails",
            task12_remove_receivables_emails,
            page,
            HOME_URL,
            PAUSE=PAUSE,
            DRY_RUN=DRY_RUN,
            max_retries=2,
        )
        
        '''task14_setup_sandbox_page_integration( #Success rate too low needs fixe or to be deleted
            page,
            sandbox_name="CLF and PLE",
            PAUSE=PAUSE,
            DRY_RUN=DRY_RUN,
            max_retries=2,
        )'''
    if should_run(15):    
        run_task_safe(
            "Task 15 — Update/Remove HireRight Config",
            task15_update_or_remove_hireright_config,
            page,
            HOME_URL,
            PAUSE=PAUSE,
            ref_key="(client)-PROD",
            client_id="(client)",
            client_secret="(client)!",
            DRY_RUN=DRY_RUN,
            max_retries=2,
        )
    
        
    if should_run(16):    
        run_task_safe(
            "Task 16 — Prenote Update SFTP / Disable Delivery",
            task16_prenote_update_sftp_or_disable_delivery,
            page,
            HOME_URL,
            PAUSE=PAUSE,
            DRY_RUN=DRY_RUN,
            max_retries=2,
        )
        
    if should_run(17):    
        run_task_safe(
            "Task 17 — Admin User Accounts Creation",
            task17_admin_user_accounts_creation,
            page,
            HOME_URL,
            PAUSE=PAUSE,
            DRY_RUN=DRY_RUN,
            max_retries=2,
        )
    if should_run(18):    
        TECH_USER_BY_INSTANCE = {
            "DEV1": "3fd3rr3",
            "DEV2": "fd3d3d",
            "DEV7": "d333d3",
            "TEST": "d3d3d3",
        }
        
        tech_username = TECH_USER_BY_INSTANCE.get(INSTANCE_LABEL)
        if tech_username:
            run_task_safe(
                "Task 18 — Admin Tech User Creation",
                task18_admin_tech_user_creation,
                page,
                HOME_URL,
                PAUSE=PAUSE,
                username=tech_username,
                DRY_RUN=DRY_RUN,
                max_retries=2,
            )
        else:
            print(f"[Task 18] No tech user configured for instance {INSTANCE_LABEL}")
        
        '''task20_update_preferred_gender_links(   #Success rate too low needs fixe or to be deleted
            page,
            FUSION_BASEURL=INSTANCE_URL,
            PAUSE=PAUSE,
            DRY_RUN=DRY_RUN,
            home_url=HOME_URL,
            max_retries=2,
        ) '''
    if should_run(21):        
        run_task_safe(
            "Task 21 — Disable Separate Remittance Emails",
            task21_disable_separate_remittance_emails,
            page,
            HOME_URL,
            PAUSE=PAUSE,
            DRY_RUN=DRY_RUN,
            max_retries=2,
        )
    if should_run(22):    
        run_task_safe(
            "Task 22 — Update Checklist URLs",
            task22_update_checklist_urls,
            page,
            HOME_URL,
            PAUSE=PAUSE,
            FUSION_BASEURL=INSTANCE_URL,
            DRY_RUN=DRY_RUN,
            home_url=HOME_URL,
            max_retries=2,
        )
    if should_run(23):    
        run_task_safe(
            "Task 23 — Workforce Structure Positions",
            task23_workforce_structure_positions,
            page,
            HOME_URL,
            PAUSE=PAUSE,
            DRY_RUN=DRY_RUN,
            max_retries=2,
        )
        
        #--------------UPDATE 1.0.1 NEW SECTION-------------------
        # =====================================================
        # REST API + UI ESS JOBS (Smart Retry System)
        # =====================================================
    if run_ess:    
        print("\n" + "="*60)
        print("UI TASKS COMPLETE. LAUNCHING REST API JOBS...")
        print("="*60)
        
        original_argv = sys.argv
        sys.argv = ["main.py", "--scenario", "P2T"]
        rest_api_return_code = None #comment out from after this line to decision point to skip restapi, but note it is going to still check the json for what failed last
        
        try:
            from RESTAPI_ESS.main import run as run_rest_api  # Rename to avoid conflict
            
            rest_api_return_code = run_rest_api()
        
            print(f"\n{'='*60}")
            print(f"REST API COMPLETED (Return Code: {rest_api_return_code})")
            print(f"{'='*60}\n")
            
        except Exception as e:
            print(f"\n{'='*60}")
            print(f" REST API CRASHED: {e}")
            print(f"{'='*60}\n")
            import traceback
            traceback.print_exc()
            rest_api_return_code = 1
            
        finally:
            sys.argv = original_argv
        
        # =====================================================
        # DECISION POINT: Do we need UI retry?
        # =====================================================
        
        if rest_api_return_code == 0:
            print(f"\n{'='*60}")
            print(f" ALL REST API JOBS SUCCEEDED")
            print(f"Skipping UI ESS Jobs (not needed)")
            print(f"{'='*60}\n")
            
        elif rest_api_return_code == 1:
            print(f"\n{'='*60}")
            print(f" SOME REST API JOBS FAILED/TIMED OUT")
            print(f"Launching UI ESS Jobs to retry failed jobs...")
            print(f"{'='*60}\n")
            
            try:
                from ui_ess_jobs import run_ui_ess_jobs, run_hardcoded_acl_jobs
                
                run_ui_ess_jobs(page)
                print(f"\n{'='*60}")
                print(f" UI ESS JOBS RETRY COMPLETE")
                print(f"{'='*60}\n")
                
                acl_result = run_hardcoded_acl_jobs(page)
                print(f"\n{'='*60}")
                print(f" ACL JOBS CHECK COMPLETE")
                if acl_result and acl_result.get("compute_users_acl") is True:
                    print(f" [OK] Compute Users ACL: submitted via UI")
                elif acl_result and acl_result.get("compute_users_acl") is False:
                    print(f" [FAIL] Compute Users ACL: FAILED via UI - run manually in Oracle Fusion")
                print(f"{'='*60}\n")
                
            except Exception as e:
                print(f"\n{'='*60}")
                print(f" UI ESS JOBS ALSO FAILED: {e}")
                print(f"{'='*60}\n")
                import traceback
                traceback.print_exc()
        
        else:
            print(f"\n{'='*60}")
            print(f"  WARNING: REST API return code unknown")
            print(f"Running UI ESS Jobs as safety measure...")
            print(f"{'='*60}\n")
            
            try:
                from ui_ess_jobs import run_ui_ess_jobs, run_hardcoded_acl_jobs
                run_ui_ess_jobs(page)
                acl_result = run_hardcoded_acl_jobs(page)
                if acl_result and acl_result.get("compute_users_acl") is True:
                    print(f" [OK] Compute Users ACL: submitted via UI")
                elif acl_result and acl_result.get("compute_users_acl") is False:
                    print(f" [FAIL] Compute Users ACL: FAILED via UI - run manually in Oracle Fusion")
            except Exception as e:
                print(f" UI ESS Jobs failed: {e}")
                import traceback
                traceback.print_exc()
        #----------END OF NEW SECTION-----------------
    # =====================================================
    # CLEANUP
    # =====================================================
    print("[Session 2] Main tasks completed. Closing browser...")
    # Print AI Healer report if it was active
    try:
        from ai_healer import get_healer
        healer = get_healer()
        if healer.enabled:
            healer.print_report()
    except Exception:
        pass
    
    context2.close()


if __name__ == "__main__":
    with sync_playwright() as p:
        run(p)