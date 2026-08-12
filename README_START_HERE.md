
Oracle Fusion Post-Refresh Automation
Project Overview:
This system automates the repetitive configuration tasks required after an Oracle Fusion environment refresh (P2T). It transitions from UI-based configuration to REST API bulk job submission, with a backup file for UI ESS jobs automation.
Current Capability: 18 out of 23 UI tasks + 43 ESS jobs automated(I am not sure if more tasks have been added but I worked with 23 and got 18 to work)
________________________________________
## Version 1.1.1 — (client) Feedback Fixes: ACL, Timeouts, Process IDs & Dup Jobs (August 2026)


### What Changed in v1.1.1

Version 1.1.1 addresses six specific issues raised by (client) after real refresh runs. The headline fixes: the ESS poll timeout is now configurable from the dashboard, the job summary now prints Process IDs so same-named jobs can be told apart, the "Compute Users ACL" job (which cannot be submitted via REST) now runs reliably through the UI, and the program no longer crashes at the end during the UI retry phase.

### Fixes & New Features

#### 1. **Procurement Access Setup — no more triple reruns**
The pre-task procurement security setup was failing the first one or two times and only succeeding on a manual third run. Root cause: a raw click on the Security Console "Users" tile fired before Oracle finished rendering (and an "Import User and Role" warning dialog was swallowing the first click). Fixed with a verify-the-page-landed retry so a slow render self-heals instead of crashing the whole script.

#### 2. **Configurable ESS Poll Timeout (dashboard + .env)**
Previously the global poll timeout was hardcoded, so the program often ended while ESS jobs were still running. It's now configurable:
- **Dashboard:** a new "ESS Poll Timeout (mm:ss)" field in the sidebar (default `30:00`). Enter e.g. `0:10` for quick testing or `45:00` for a heavy refresh.
- **`.env`:** `ESS_POLL_TIMEOUT=1800` (seconds) is the fallback for CLI/non-dashboard runs.
- The dashboard value flows: field → `mm:ss`→seconds → `/api/run` → `ESS_POLL_TIMEOUT` env → `main.py`.

#### 3. **Process IDs in the Job Summary**
Many ESS jobs share the same display name (e.g. 25 "…initial ingest to OSCS" rows) but differ by argument, making it impossible to match a log line to the real ESS request. The end-of-run summary now prints a per-job table:
Process ID Status Arg1 Job
8803371 SUCCEEDED fa-hcm-acl ESS job to create index...
8803374 SUCCEEDED fa-hcm-person ESS job to create index...
Each job now shows its Oracle **Process/Request ID** and distinguishing **Arg1**, so correlation is trivial. Appears in both the terminal and the dashboard.

#### 4. **Compute Users ACL — now runs via UI (REST is not viable)**
`Compute Users ACL` (ComputeUsersACLProcessor) **always errors when submitted via REST**, whether run-now or scheduled — confirmed via direct Postman testing (`requestedStartTime` schedule still returns `state: ERROR`). It succeeds only through the Fusion UI. So it now runs through a dedicated, hardened UI submission in `run_hardcoded_acl_jobs`:
- `exact=True` on the process cell (avoids matching "Compute Users ACL by Events")
- `robust_click` retry wrapper on the search/OK/Submit clicks
- The earlier hardcoded jobs (Maintain Candidates, Index Candidate Attachments) are now isolated so a failure there can't block ACL from running.
- Honest status reporting: prints `[OK] submitted via UI` (with a reminder to verify SUCCEEDED in Scheduled Processes) or `[FAIL] run manually` only if the UI attempt actually failed.

*Note: `[OK]` means the job was submitted successfully via UI. Confirm it reaches SUCCEEDED in Oracle Scheduled Processes after the run.*

#### 5. **Three Manual-Task Jobs Now Automated (run first + twice)**
Import User and Role Application Security Data, Send Pending LDAP Requests, and Retrieve Latest LDAP Changes are now in the ESS Excel at rows 1–3 (so they submit first) **and** kept in their original positions (so they run a second time later in the sequence). To let the same job legitimately submit twice, a new **`AllowDuplicate`** column bypasses the duplicate-request detection for flagged rows (`Y`). Row-number filters in `ui_ess_jobs.py` were bumped to account for the 3 inserted rows.

#### 6. **No More Crash at End of Run (UI ESS Retry)**
The program was abending during the UI ESS retry phase. Root cause: a raw click on the "Scheduled Processes" nav link in `open_scheduled_processes` timing out (30s) on slower client connections, after the retry browser had sat idle through the entire REST phase. Fixed with `robust_click` on the Navigator/Tools/Scheduled Processes clicks. The UI retry is a deliberate safety net — it re-runs any job that didn't reach SUCCEEDED, so it must not crash.

#### 7. **Task 22 update**
In task 22 had to add new journey due to new journey being created. 
If this happens again (client) team that makes the journey *has to inform* (client) P2T team.
Then (client) P2T team adds the `journey map` and `url` to task 22

### Configuration Changes (v1.1.1)

| Item | Change |
|---|---|
| `.env` | Added `ESS_POLL_TIMEOUT=1800` (seconds; dashboard overrides per-run) |
| `(client)P2T.xlsx` | Added `AllowDuplicate` column; LDAP jobs duplicated to rows 1–3; `Enabled` column honored |
| Dashboard | New "ESS Poll Timeout (mm:ss)" field |

## Version 1.1.0 — Dashboard, Retry System, CLI & AI Integration (May 2026)

### What Changed in v1.1.0

Version 1.1.0 is the biggest update to the P2T automation system. It introduces a **web dashboard** so users never need to touch the terminal, a **retry system** with destructive-step awareness, **task selection via CLI**, **fire-all-then-poll** for ESS jobs, **AI-powered failure analysis** (disabled by default — requires Ollama), and several quality-of-life improvements requested by (client).

### New Features

#### 1. **Web Dashboard**
No more editing code or typing terminal commands. Double-click a desktop icon and the dashboard opens in your browser.

**What it does:**
- Visual task selection with checkboxes (Select All / None / UI Only)
- Editable environment fields (URL, Username, Password) — pre-filled from `.env` but changeable per-run
- ESS Jobs toggle
- Live log streaming with color-coded output (blue=task start, green=success, red=failure, yellow=warning)
- Results summary (Passed / Failed / Skipped cards with counts)
- Run/Stop buttons with elapsed timer and status badge (IDLE / RUNNING / COMPLETE / FAILED)
- SQLite log files still generated in background (viewable/exportable after run)

**How it works:**
- Flask backend (`dashboard_api.py`) serves the React dashboard and runs `Ui_Automation.py` as a subprocess
- React frontend (built and bundled in `dashboard/dist/`) — no Node.js needed on client machine or VM
- Server-Sent Events (SSE) stream live log lines from automation to browser
- Dashboard field values override `.env` per-run — switch environments without editing files
- `P2T_DASHBOARD_MODE` environment variable tells `terminal_logger.py` to not hijack stdout (so output flows to dashboard) while still saving to SQLite in the background
- Python `-u` flag ensures unbuffered stdout for true real-time streaming
- `launch_dashboard.vbs` auto-kills any existing Flask process on port 5000 before starting a new one (prevents zombie processes)

**How to use:**
- First time: Double-click `setup.bat` in file explorer (installs Flask, creates desktop shortcut with P2T icon)
- Every time after: Double-click "P2T Automation" icon on Desktop
- Dashboard opens at `http://localhost:5000`
- Select tasks, verify credentials, click "Run Automation"
- Watch live output, see results when done
- Close browser when finished
- Log files saved to `~/Desktop/ui_automation_logs/` as always

**Architecture:**
```
User clicks "Run Automation" in browser
    ↓
Flask backend (dashboard_api.py)
    ↓ spawns subprocess with env overrides + P2T_DASHBOARD_MODE=1
python -u Ui_Automation.py --tasks 1,3,16,ESS
    ↓ stdout streams back via SSE (unbuffered)
Browser shows live colored log output
    ↓ on completion
Results summary (pass/fail/skip counts)
    + SQLite log file saved to Desktop
```

**Desktop Launcher System:**
- `setup.bat` — First-time setup: uses `.venv\Scripts\python.exe` and `pip.exe` directly (avoids venv activation issues), installs Flask, creates desktop shortcut via `create_shortcut.py`, verifies all dependencies
- `launch_dashboard.vbs` — Desktop launcher: kills existing Flask on port 5000 via `netstat`+`taskkill`, starts Flask silently (no terminal window), opens browser. Uses `.venv\Scripts\python.exe` directly
- `create_shortcut.py` — Creates `.lnk` shortcut with P2T icon. Handles OneDrive Desktop path detection
- `branding/p2t_icon.ico` + `branding/p2t_icon.png` — 512px source, dark background, P2T blue + (client) Oracle red

#### 2. **Task Selection via --tasks CLI**
Run specific tasks instead of everything. The dashboard uses this under the hood, but it also works from terminal.

**Usage:**
```powershell
# Run specific tasks
python Ui_Automation.py --tasks 1,3,16

# Run tasks + ESS jobs
python Ui_Automation.py --tasks 1,3,16,ESS

# Run only ESS jobs
python Ui_Automation.py --tasks ESS

# Run everything (default, same as no argument)
python Ui_Automation.py --tasks all
python Ui_Automation.py
```

**Key behaviors:**
- Tasks always run in code order (lowest to highest) regardless of input order
- `--tasks 22,1` runs Task 1 first, then Task 22
- Select All in dashboard includes Task 0 (pre-task) + all UI tasks + ESS
- Each task is self-contained — Tasks 16, 17, 18 now open their own navigator sections if needed

#### 3. **UI Task Retry System**
Tasks now retry automatically on failure instead of just skipping.

**How it works:**
- Every `run_task_safe()` call gets `max_retries=2` (try once, retry once on failure)
- On failure: screenshot taken → navigate Home → retry the task
- On retry: `is_retry=True` passed to task function (for destructive-step awareness)

**Destructive-step awareness (Tasks 3 & 16):**
- Task 3 (ADP deliveries) and Task 16 (Prenote) delete rows from Oracle
- On retry, these tasks check if each row still exists before trying to delete
- If row already deleted on first attempt: skip gracefully
- If row still there: try deleting again
- Failures tracked in `failed_deletes` list, raise at END of task (not per-row) so all rows get attempted
- Flow: first attempt tries all rows → tracks failures → raises at end → retry kicks in → skips already-deleted rows → retries failed ones

#### 4. **Task 3 & 16 Delete Row Fix**
Fixed the row selection issue where Oracle's Delete button stayed disabled.

**Problem:** The code was clicking the wrong table cell — the Extract Delivery Options table (top level) instead of the Additional Details table (below)on task 3 first extact and task 16 first run. Oracle only enables the Delete button when a row in the Additional Details section is properly selected.

**Fix:**
- Click the "Additional Details" heading first to activate the section
- Target cells using `get_by_role("cell", name=...)` matching both the row name AND "Extract Delivery Mode" — this uniquely identifies cells in the Additional Details table
- Fallback: if the combined name doesn't match, use standard cell filter
- Same fix applied to both Task 3 and Task 16

**Before:** Delete button disabled, 30s timeout, row not deleted
**After:** Heading click activates section → correct cell selected → Delete enabled → row deleted, now after testing works first try for both tasks

#### 5. **Fire-All-Then-Poll for ESS Jobs**
ESS jobs now submit rapidly then poll all at once, instead of waiting for each one individually.

**Before (v1.0.4):** Submit job 1 → wait up to 100s → submit job 2 → wait → submit job 3 → wait... (43 jobs × 100s = potentially 70+ minutes of waiting)

**After (v1.1.0):** Submit all 43 jobs in ~2 minutes → poll all outstanding jobs in round-robin until all complete (30 min global timeout)

**Phase 1 — Submit All:**
- Loop through Excel rows, submit each job with `time.sleep(3)` between
- Collect `request_id` into `pending_jobs` list
- Scheduled jobs counted as success immediately (same as before)
- Duplicates and skips handled same as before

**Phase 2 — Batch Poll:**
- After all submissions, poll every outstanding job every 10 seconds
- Remove from list when terminal state reached (SUCCEEDED, FAILED, ERROR, etc.)
- `GLOBAL_POLL_TIMEOUT = 1800` (30 minutes for all jobs combined)
- Progress logged: `[120s] 8 jobs still running, 35 completed. Waiting 10s...`

#### 6. **Enabled Column in Excel**
Added "Enabled" column (Y/N) as Column A in `(client)P2T.xlsx`.
Consolidated Excel, only one Excel file location
- Set to `N` to skip a row without deleting it
- Defaults to `Y` if column missing (backward compatible)
- Works in both REST API (`main.py`) and UI retry (`ui_ess_jobs.py`)
- Added `"Enabled"` to `RESERVED_COLS` so it doesn't get sent as an Oracle job parameter

#### 7. **Consolidated .env**
Single `.env` file in project root. Deleted `RESTAPI_ESS/.env`.

- One `TENANT_BASE_URL`, one `FUSION_USERNAME`, one `FUSION_PASSWORD`
- `main.py` auto-wires all credential aliases from the single values
- `get_job_details.py` updated to read from parent `.env`
- Dashboard overrides these values per-run from the UI fields

#### 8. **Task 18 — Integration User Roles Update**
Updated to create the integration user with all 5 required roles:

**Roles (updated):**
1. Application Implementation Administrator
2. Application Implementation Consultant
3. Application Implementation Manager
4. (client)-BPR_IT_INTEGRATION_SPECIALIST_JOB (searched by role code)
5. (client)-BPR_IT_INTEGRATION_SPECIALIST_DATA (searched by role code — **NEW**)

**GUID update:**
- DEV7: `d3ww` → `5b5a77308b174dwed3ed3dwd3bdewdde3d3a9f4741104409c1b`
- Other GUIDs confirmed matching Integration Users document

#### 9. **Navigator Self-Contained Fix**
Tasks 16, 17, and 18 now work standalone when run individually via `--tasks`.

**Problem:** Task 16 assumed My Client Groups was already expanded in Navigator (it was — when Task 3 ran before it). Running `--tasks 16` alone would fail.

**Fix:** Each task tries the direct click first. If it fails (section collapsed), expands the parent section then clicks.

#### 10. **Dashboard Logging — Dual Mode**
`terminal_logger.py` now supports two modes:

**Terminal mode** (running from command line): Same as before — SQLite hijacks stdout, every print goes to both terminal AND database. No changes.

**Dashboard mode** (running from web dashboard): `P2T_DASHBOARD_MODE=1` environment variable set by `dashboard_api.py`. In this mode:
- stdout is NOT hijacked (flows to subprocess pipe → dashboard SSE stream)
- SQLite log file is still created in the background (writes on every print)
- Both live streaming AND log file work simultaneously
- Python `-u` flag ensures unbuffered output for real-time streaming


#### 11. **AI Healer Integration (Disabled by Default)**
AI-powered failure analysis using Gemma 4. Code set up is in place, disabled by default.

**What it would do if added (when enabled):**
- On task failure, takes screenshot + reads DOM elements
- Sends to Gemma 4 with P2T-specific prompt
- AI suggests a Playwright selector fix
- Attempts to execute the fix before retry kicks in
- Prints report at end of run

**Why disabled:** Idea only, no concrete code, only set up code, would use Gemma 4 and it needs 5-6GB minimum (probably more to work functioanlly)
Needs permissions on if plan to add to future proof code is accepted and correct method to use either proper machine or hosting.
This is only set up code. None of what is added in the code currently affects anything or is involved in any security or data.
Idea with the google open source model is it will be local so no security concerns, idea is if any update comes that changes things a lot the AI which would be trained on
the P2T tasks could correct code if anything were to error out. In live time Ai intervenes to make the correct adjustment, sends report of probelm and solution to fix in code.

**To enable (when ready):**
*NOTE:* This was all just set up for potential AI plans in future not nessecary can be deleted from .env if prefered.
```env
AI_HEALER_ENABLED=true
AI_HEALER_MODEL=gemma4:e4b
AI_HEALER_URL=http://localhost:11434
AI_HEALER_MAX_RETRIES=1
```

**Zero impact when disabled:** Lazy import, single boolean check, no overhead. Safe to delete `ai_healer.py` entirely — the project will still work.




### Files Modified in v1.1.0

| File | Changes |
|------|---------|
| `Ui_Automation.py` | `--tasks` CLI, `should_run()`, `max_retries=2`, navigator fixes, Task 18 roles+GUIDs, Task 3 & 16 delete row fix (heading click + Extract Delivery Mode cell targeting), AI healer report |
| `post_refresh_automation_helpers.py` | `run_task_safe` retry loop + `inspect`-based `is_retry` stripping + AI healer integration |
| `terminal_logger.py` | Dual mode: dashboard mode (P2T_DASHBOARD_MODE=1) creates SQLite log without hijacking stdout; terminal mode unchanged |
| `RESTAPI_ESS/main.py` | Phase 1/2 batch polling, `pending_jobs` list, `GLOBAL_POLL_TIMEOUT`, Enabled check, `RESERVED_COLS`, consolidated `.env` loading |
| `ui_ess_jobs.py` | Enabled column check |
| `RESTAPI_ESS/get_job_details.py` | Load `.env` from parent, `TENANT_BASE_URL` fallback |

### New Files in v1.1.0

| File | Purpose |
|------|---------|
| `ai_healer.py` | AI-powered failure analysis (Gemma 4). Disabled by default. Optional — safe to delete. No code in file, just saved for potential future possibility |
| `dashboard_api.py` | Flask backend — serves React dashboard, triggers automation, streams logs via SSE |
| `dashboard/` | React frontend (source + built `dist/` files). Built with Vite + Tailwind CSS. |
| `setup.bat` | First-time setup — installs Flask via venv pip, creates desktop shortcut with P2T icon |
| `launch_dashboard.vbs` | Desktop launcher — kills port 5000, starts Flask silently, opens browser. Uses venv python directly. |
| `create_shortcut.py` | Helper for `setup.bat` — creates Windows `.lnk` shortcut with P2T icon, handles OneDrive Desktop path |
| `branding/p2t_icon.ico` | Desktop shortcut icon (P2T (client) logo, 512px source, multi-resolution ICO) |
| `branding/p2t_icon.png` | Same icon in PNG format |

### File Inventory & Line Counts

*1.1.0:*
| Component | File Name | Line Count | Status / Notes |
|-----------|-----------|------------|----------------|
| UI Core | `Ui_Automation.py` | 4516 | **v1.1.0: --tasks CLI, retry, navigator fixes, Task 3&16 delete fix, Task 18 5 roles** |
| Helper | `post_refresh_automation_helpers.py` | 301 | **v1.1.0: retry loop + AI healer integration** |
| UI Logger | `terminal_logger.py` | 372 | **v1.1.0: Dual mode (dashboard + terminal)** |
| REST API | `main.py` | 1355 | **v1.1.0: Fire-all-then-poll, Enabled column, consolidated .env** |
| REST API | `fusion_api.py` | 524 | Core API wrapper |
| REST API | `backfill_from_log.py` | 401 | Recovery tool |
| REST API | `job_audit_xlsx.py` | 133 | Excel audit reports |
| REST API | `get_job_details.py` | 122 | **v1.1.0: Parent .env loading** |
| REST API | `logger.py` | 33 | Standardized logging |
| REST API | `job_config.py` | 36 | Environment-specific mappings |
| UI Backup | `ui_ess_jobs.py` | 1692 | **v1.1.0: Enabled column check** |
| JSON | `job_status_tracker.json` | Auto-gen | Status tracker file |
| UI Export | `export_logs.py` | 190 | SQLite → text converter |
| Data Access | `pretask_data_access_api.py` | 307 | REST data access API |
| **NEW** | `ai_healer.py` | 30 | **v1.1.0: AI failure analysis (disabled, potential future idea, no code in place)** |
| **NEW** | `dashboard_api.py` | 242 | **v1.1.0: Flask backend for web dashboard** |
| **NEW** | `dashboard/` | React app | **v1.1.0: Web dashboard (bundled in dist/)** |
| **NEW** | `setup.bat` | 42 | **v1.1.0: First-time setup script** |
| **NEW** | `launch_dashboard.vbs` | 26 | **v1.1.0: Desktop launcher (no terminal)** |
| **NEW** | `create_shortcut.py` | 27 | **v1.1.0: Windows shortcut creator** |
| **TOTAL** | | **~10,349+** | |

### Installation & Setup (v1.1.0)

#### First Time Setup (New Machine)

1. **Install Python 3.12.10+** from https://www.python.org/downloads/

2. **Create virtual environment and install dependencies:**
```powershell
cd post_refresh_automation
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install playwright requests python-dotenv openpyxl pandas urllib3 python-dateutil flask flask-cors
python -m playwright install chromium
```

3. **Configure `.env` file** in project root (single file — no RESTAPI_ESS/.env needed):
```env
TENANT_BASE_URL=https://(client).fa.ocs.oraclecloud.com
FUSION_USERNAME=Your.Username
FUSION_PASSWORD=YourPassword123

FUSION_USERS=(client)
FUSION_(client)_LOGIN=Your.Username
FUSION_(client)_PASSWORD=YourPassword123

# Optional AI Healer (requires Ollama — disabled by default)
AI_HEALER_ENABLED=false
```

4. **Run first-time setup:**
    - Double-click `setup.bat` in the project folder (from Windows File Explorer, not VS Code)
    - This installs Flask, verifies dependencies, creates "P2T Automation" shortcut on Desktop with icon

5. **Launch the dashboard:**
    - Double-click "P2T Automation" on your Desktop
    - Browser opens to `http://localhost:5000`
    - Select tasks, verify credentials, click Run
    - Live logs stream in real-time
    - Log files also saved to `~/Desktop/ui_automation_logs/`

#### Running from Terminal (Alternative)
```powershell
# Activate venv
.venv\Scripts\Activate.ps1

# Run with dashboard
python dashboard_api.py
# Then open http://localhost:5000

# Run without dashboard (terminal mode — same as before)
python Ui_Automation.py                     # all tasks + ESS
python Ui_Automation.py --tasks 1,3,16      # specific tasks only
python Ui_Automation.py --tasks ESS         # ESS jobs only
python Ui_Automation.py --tasks 1,3,16,ESS  # specific tasks + ESS
python Ui_Automation.py --tasks 0           # pre-task only (procurement access)
```

#### Updating Code

- **Python file changes** (Ui_Automation.py, dashboard_api.py, etc.): Just restart the dashboard — close browser, double-click icon again (it auto-kills the old Flask process)
- **React dashboard changes** (App.jsx, CSS): Rebuild first (`cd dashboard && npm run build`), then restart dashboard
- **No rebuild needed** for Python-only changes

#### Stopping the Dashboard

- Close the browser tab
- The Flask process stays running in the background
- Next time you double-click the icon, it automatically kills the old process and starts fresh
- To manually stop: Task Manager → find `python.exe` → End Task

### Migration from v1.0.4

**Good news: Backward compatible!**

- Existing `.env` files work (new fields are optional, defaults are safe)
- `(client)P2T.xlsx` just needs "Enabled" column added as Column A (defaults to Y if missing)
- `--tasks all` is the default behavior (same as before)
- Dashboard is optional — terminal mode still works exactly as before
- AI healer is disabled by default — zero impact on existing behavior
- Delete `RESTAPI_ESS/.env` (consolidated into root `.env`)

### Known Limitations (v1.1.0)

- AI Healer would use Gemma 4 and it needs 5-6GB minimum (probably more to work functioanlly) — code in place for the retyr systems and .env, no affect on anything, no AI added.
- ACL jobs (rows 37, 40-42) still require manual verification if fail on ESS — UI fallback improvement planned for future


### Benefits of v1.1.0

**User Experience**: No terminal needed — double-click icon, click buttons, watch live results
**Reliability**: Retry system catches transient Oracle UI failures automatically
**Speed**: Fire-all-then-poll cuts ESS job time from 70+ minutes to ~15 minutes
**Flexibility**: Run any combination of tasks without editing code
**Visibility**: Live dashboard with color-coded logs, pass/fail summary, AND SQLite log files
**Stability**: Task 3 & 16 delete row issue fixed with heading activation + precise cell targeting
**Future-Ready**: AI healer code set up in place, not active but there for future potential, AI needs 1) permission from (client) and 2) correct machine to run or hosting option.

---
**Developed by Alex Cacaras**
**Version 1.1.0 — End of May 2026**

## Version 1.0.3 - ESS JOB UPDATE (End of April 2026)
### What Changed in v1.0.4
Removed the Oracle class is framework from Task 22 as I do not believe Oracle will go back to it. Only considers redwood.
Updated task 3 and 16 row deletion locators/timing.
Updated ESS job configuration timing for running, before 500 seconds now 100 for speeding up


  ## Version 1.0.3 - ESS JOB UPDATE (End of March 2026)
  
  ### What Changed in v1.0.3
  Version 1.0.3 fixes logging accuracy, REST API compatibility issues specific to the (client) Oracle pod, and UI retry reliability. On the REST API side, the (client) pod was identified as returning requestParameters=null on all GET requests and requiring jobDefinitionId as the primary submit format. The OSCS duplicate detection was broken — now duplicates is more accurate to Oracle qualifications, causing more accurate logging. The logging was also off: total_jobs undercounted, jobs still running on Oracle after a short poll window were logged as failures, and add_failed_job() was writing jobDefinitionName instead of Display Name. So ui_ess_jobs.py had an incorrect log, wasting time. On the UI side, the AFModalGlassPane overlay was blocking all clicks after a job submitted — the script would time out trying to click Schedule New Process or Submit while Oracle was still processing. The retry loop also had no recovery when a row failed, so a single ACL job failure would cascade and block all subsequent rows. All three files (main.py, fusion_api.py, ui_ess_jobs.py) have been updated. ACL jobs are now explicitly skipped in the UI retry with a printed manual action message, and failed job rows are matched by excel_row number from the JSON instead of by name — making retry matching reliable regardless of name format.

  ### Files Modified in v1.0.3

| File | Changes | 
|------|---------| 
| `ui_ess_jobs.py` |Improved error handling, and retry with smart system | 
| `main.py` |Corrected logs, and queue handling|
|`fusion_api.py`|Duplicate Check and parameter upgrade|
### New Features
1. OSCS Duplicate Detection Fix (fusion_api.py)
- ESS Jobs were handling duplicates in wrong way when being logged, now instead of checking say only name the code lets Oracle duplicate check
decide.

2. Accurate Job Status Logging (main.py)
- Now counts every attempted row correctly.
- Jobs still running on Oracle after poll window → skipped not failed (they are in-flight, not broken)
- Checks final status
- All add_failed_job() calls now write display_name so ui_ess_jobs.py retry matching works correctly
- ACL_JOB_NAMES expanded to include jobDefinitionNames so ACL detection fires regardless of name format in JSON

3. (client) Pod Compatibility (fusion_api.py)
- Now sends jobDefinitionId first on every submit
- WAIT / PAUSED / BLOCKED / RETRYING states treated as normal Oracle queuing (Postman confirmed PAUSED → SUCCEEDED naturally on this pod)
- Removed MAX_WAIT_STATE_TIME early-exit — only the overall 600s timeout applies

4. Glass Pane Fix — UI Retry (ui_ess_jobs.py)
- Added wait_for_glass_pane_gone() helper that waits for Oracle ADF's AFModalGlassPane overlay to clear before any click
- open_schedule_new_process() and submit_job_simple() both call it before clicking
- Submit, first OK, and second OK clicks now use timeout=90000 (90s) — Oracle can take ~60s to process
- On row failure, recovery presses Escape twice to dismiss any open LOV dialog before moving to next row

5. Reliable UI Retry Matching (ui_ess_jobs.py)
- Failed jobs now matched by excel_row number from JSON instead of by Display Name(more accurate, makes more sense to me, worked better)
- Eliminates all name-matching ambiguity (jobDefinitionName vs Display Name, trailing spaces, etc.)
- ACL jobs explicitly skipped in retry loop with a clear printed message
- Manual action warning printed at end of summary if ACL jobs failed in REST API

  ## Version 1.0.2 - Task 17, 22 and Data Access Update (End of March 2026)

  ### What Changed in v1.0.2
  Version 1.0.2 introduces small updates to a few tasks to better streamline the P2T automation process. Now data access in the pretask section does not fail through the flaky UI but instead hits a RESTAPI through new file pretask_data_access_api to update the user data access after UI role is added. Avoids the second row failure. Task 17 now clicks the same state as the pretask security console user tab and tries different methods to find the usertab and successfully click(avoids having to change the code from user to user user), task 22 now is broken into 4 pieces- 1) is beginning go to the setup/maintenance, cheklist templates. 2) Once Inside journy task check for redwood. 3) If redwood detected do perform the redwood version of task (dynamic text fields etc) Now uses a Find task dynamically system to ensure we get correct tasks and don't error out. 4) If in classic perform classic version. Also added more screenshots and corrected the screenshot folders.

### Files Modified in v1.0.2

| File | Changes | 
|------|---------| 
| `Ui_Automation.py` |Task 17, 22 and data access, more screenshots | 
| `pretask_data_access.py` | **NEW FILE**  - For data access api|
|`post_refresh_automation_helpers.py`| Added new screenshot name and fixed folder path bug|

### New Features
Task 22 — Redwood-Compatible Journey URL Updates
- Fully redesigned to support both Classic and Redwood UI
- Dynamic row detection replaces static “Edit Task” logic (handles Oracle UI changes)
- Multi-strategy locator approach improves reliability across environments
- Automatically falls back to Classic flow if Redwood fails

2. Task 17 — Improved Security Console Navigation
- Added multi-path navigation for Users page (tile, link, and fallback selectors)
- Handles inconsistent Oracle UI rendering (e.g., “Users” vs “Users Users”)

3. Data Access API Integration (Pretask Enhancement)
- Introduced REST API-based data access assignment
- Supports direct posting of:
   Procurement Catalog Administrator
    Recruiting Setup and Maintenance roles
- Automatically detects and skips duplicate assignments
- Eliminates need for manual data access configuration in UI/UI automation failure

4. Improved Screenshot & Debugging System
- Fixed issue where screenshots were saved to incorrect task folders
- Added new standardized debug screenshots:
- STUCK (captures where automation gets stuck before fail)
- Provides clearer visibility into task execution and failures


### Migration from v1.0.1

**Good news: No changes required!** 

- I will be providing the whole folder with update 1.0.2 and 1.0.3 together as v1.0.3

## File Inventory & Line Counts

*1.0.0:*
Component	File Name	                Line Count	      Status / Notes
UI        Core	ui_automation.py	      3,839	          Primary UI Driver. Tasks 14 & 20 have low success rates.
Helper	post_refresh_automation_helper.py	237	    Utilities.
UI Logger    terminal_logger.py             337      SQLite-based crash-proof logging. Fully documented
REST API	main.py	                        936      	Main API Orchestrator. Toggle DRY_MODE here.
REST API	fusion_api.py	                432	      Core API wrapper for authentication and POST/GET.
REST API	backfill_from_log.py	        401	        Recovery tool for failed API submissions.
REST API	job_audit_xlsx.py	            133	        Generates Excel reports of job statuses.
REST API	get_job_details.py	            121	        Fetches metadata for specific ESS jobs.
REST API	logger.py	                     32	        Standardized logging format.
REST API	job_config.py	                 35	    Environment-specific job mappings.
UI Backup	ui_ess_jobs.py	               1,344	UI fallback for jobs. Manual intervention at row 37, 40,41,42.
TOTAL		~7,847

---
# File Inventory & Line Counts
*1.0.1:*
| Component | File Name                     | Line Count        | Status / Notes |
|-----------|-----------                    |------------       |----------------|
| UI Core | `Ui_Automation.py`              | 3,928             | Primary UI Driver. **v1.0.1: Added REST API orchestration** |
| Helper| `post_refresh_automation_helper.py`| 237              | Utilities |
| UI Logger | `terminal_logger.py`           | 337              | SQLite-based crash-proof logging |
| REST API | `main.py`                      | 1,285             | Main API Orchestrator. **v1.0.1: Added bett timeout tracking** |
| REST API | `fusion_api.py`                | 432                | Core API wrapper for authentication |
| REST API | `backfill_from_log.py`         | 401                | Recovery tool for failed submissions |
| REST API | `job_audit_xlsx.py`            | 133               | Excel audit reports |
| REST API | `get_job_details.py`           | 121                | Job metadata inspector |
| REST API | `logger.py`                    | 32                | Standardized logging |
| REST API | `job_config.py`                | 35                | Environment-specific mappings |
| UI Backup | `ui_ess_jobs.py`              | 1,554                | UI fallback. **v1.0.1: Added smart retry integration** |
| **NEW** | `job_status_tracker.json`       | Auto-gen          | **v1.0.1: Status tracker file** |
| UI Export | `export_logs.py`              | 188            | **NEW v1.0.1:** SQLite → text converter |
| **TOTAL** | | **8683** | |
________________________________________

# File Inventory & Line Counts
*1.0.2:*
| Component | File Name                     | Line Count        | Status / Notes |
|-----------|-----------                    |------------       |----------------|
| UI Core | `Ui_Automation.py`              | 4,616             | Primary UI Driver. **v1.0.2: Upgraded task 17,22 and data access using api now, more screenshots** |
| Helper| `post_refresh_automation_helper.py`| 309              | Utilities **v1.0.2: added more screenshots and corrected folder paths**|
| UI Logger | `terminal_logger.py`           | 337              | SQLite-based crash-proof logging |
| REST API | `main.py`                      | 1,285             | Main API Orchestrator.  |
| REST API | `fusion_api.py`                | 432                | Core API wrapper for authentication |
| REST API | `backfill_from_log.py`         | 401                | Recovery tool for failed submissions |
| REST API | `job_audit_xlsx.py`            | 133               | Excel audit reports |
| REST API | `get_job_details.py`           | 121                | Job metadata inspector |
| REST API | `logger.py`                    | 32                | Standardized logging |
| REST API | `job_config.py`                | 35                | Environment-specific mappings |
| UI Backup | `ui_ess_jobs.py`              | 1,554                | UI fallback.  |
| *json tracker | `job_status_tracker.json`       | Auto-gen          |  Status tracker file |
| UI Export | `export_logs.py`              | 188                   |SQLite → text converter |
|**NEW**| `pretask_data_access.py` | 306|                |**New v1.0.2: Data access API**|
| **TOTAL** | | **9749** | |
________________________________________
# File Inventory & Line Counts
*1.0.3:*
| Component | File Name                     | Line Count        | Status / Notes |
|-----------|-----------                    |------------       |----------------|
| UI Core | `Ui_Automation.py`              | 4,616             | Primary UI Driver. **v1.0.2: Upgraded task 17,22 and data access using api now, more screenshots** |
| Helper| `post_refresh_automation_helper.py`| 310              | Utilities **v1.0.2: added more screenshots and corrected folder paths**|
| UI Logger | `terminal_logger.py`           | 338              | SQLite-based crash-proof logging |
| REST API | `main.py`                      | 1,339             | Main API Orchestrator. **v1.0.3: Improved logging** |
| REST API | `fusion_api.py`                | 524                | Core API wrapper for authentication **v1.0.3: Imporved queue handling**|
| REST API | `backfill_from_log.py`         | 401                | Recovery tool for failed submissions |
| REST API | `job_audit_xlsx.py`            | 133               | Excel audit reports |
| REST API | `get_job_details.py`           | 122                | Job metadata inspector |
| REST API | `logger.py`                    | 33                | Standardized logging |
| REST API | `job_config.py`                | 36                | Environment-specific mappings |
| UI Backup | `ui_ess_jobs.py`              | 1,682                | UI fallback. **v1.0.3: Improved Ui workflow, fail handling and status messages** |
| *json tracker | `job_status_tracker.json`       | Auto-gen          |  Status tracker file |
| UI Export | `export_logs.py`              | 190                   |SQLite → text converter |
|**NEW**| `pretask_data_access.py` | 307|                |**New v1.0.2: Data access API**|
| **TOTAL** | | **10,021** | |
________________________________________
*1.0.4:*
| Component | File Name                     | Line Count        | Status / Notes |
|-----------|-----------                    |------------       |----------------|
| UI Core | `Ui_Automation.py`              | 4,386             | Primary UI Driver. **1.0.4: task 22, 3 and 16 updated v1.0.2: Upgraded task 17,22 and data access using api now, more screenshots** |
| Helper| `post_refresh_automation_helper.py`| 310              | Utilities **v1.0.2: added more screenshots and corrected folder paths**|
| UI Logger | `terminal_logger.py`           | 338              | SQLite-based crash-proof logging |
| REST API | `main.py`                      | 1,339             | Main API Orchestrator. **v1.0.3: Improved logging** |
| REST API | `fusion_api.py`                | 524                | Core API wrapper for authentication **v1.0.3: Imporved queue handling**|
| REST API | `backfill_from_log.py`         | 401                | Recovery tool for failed submissions |
| REST API | `job_audit_xlsx.py`            | 133               | Excel audit reports |
| REST API | `get_job_details.py`           | 122                | Job metadata inspector |
| REST API | `logger.py`                    | 33                | Standardized logging |
| REST API | `job_config.py`                | 36                | Environment-specific mappings |
| UI Backup | `ui_ess_jobs.py`              | 1,682                | UI fallback. **v1.0.3: Improved Ui workflow, fail handling and status messages** |
| *json tracker | `job_status_tracker.json`       | Auto-gen          |  Status tracker file |
| UI Export | `export_logs.py`              | 190                   |SQLite → text converter |
|**NEW**| `pretask_data_access.py` | 307|                |**New v1.0.2: Data access API**|
| **TOTAL** | | **9791** | |

 
 ##  Version 1.0.1 - Smart Retry System (March 2026)

### What Changed in v1.0.1

Version 1.0.1 introduces an **intelligent retry system** that automatically handles job failures and timeouts. The system now coordinates between REST API and UI automation (for ESS jobs) to ensure all jobs complete successfully, eliminating the need for manual intervention when jobs timeout or fail, the choice between do I comment out restapi version or UI ESS version, and just overall confusion between restapi and UI_ESS now making UI_ESS a true backup system.

### New Features

#### 1. **Timeout-Aware REST API Polling**
The REST API now actively monitors job execution with configurable timeout thresholds:
- **Overall Timeout**: Jobs exceeding 10 minutes (default cna be changed, suggest change to faster time like 3-5min) are automatically marked as timed out
- **WAIT State Monitoring**: Jobs stuck in WAIT state for >5 minutes are detected and flagged
- **Configurable Settings**: Adjust via `MAX_POLL_TIME_SECONDS`, `POLL_INTERVAL_SECONDS`, and `MAX_WAIT_STATE_TIME` in `RESTAPI_ESS/main.py`

#### 2. **Job Status Tracking System**
New file: `RESTAPI_ESS/job_status_tracker.json`
- Automatically tracks which jobs succeeded, failed, or timed out
- Records job name, request ID, failure reason, and parameters
- Special tracking for critical ACL jobs (security-related)
- Used by UI automation to know exactly which jobs need retry

**Example Status File:**
```json
{
  "rest_api_completed": true,
  "timestamp": "2026-03-02T19:35:31+00:00",
  "total_jobs": 42,
  "successful": 38,
  "failed": 2,
  "timed_out": 2,
  "skipped": 0,
  "failed_jobs": [
    {
      "job_name": "ESS job to create index definition...",
      "request_id": "6354128",
      "reason": "TIMEOUT_OVERALL",
      "excel_row": 15,
      "parameters": {"Index Name to Reingest": "fa-hcm-acl"}
    }
  ],
  "acl_jobs_status": {
    "attempted": true,
    "completed": false,
    "failed_acl_jobs": ["Compute Users ACL"]
  }
}
```

#### 3. **Automatic UI Retry Logic**
`ui_ess_jobs.py` now integrates with the status tracker:
- Reads `job_status_tracker.json` to identify failed jobs
- **Skips jobs that succeeded** in REST API (saves 10-15 minutes!)
- **Only retries jobs that failed or timed out**
- Matches jobs by Display Name for accuracy
- Includes special handling for critical ACL jobs, makes sure to let you know it failed/skipped in restapi sinc ethey have to be run manually if restapi does not run them

#### 4. **Unified Excel Support**
REST API and UI now use the **same Excel file** (`(client)P2T.xlsx`):
- No more maintaining separate job lists
- Display Name column ensures accurate job matching
- Dynamic start date formulas (Excel formula-based, auto-calculates from SYSDATE) -- this is not new just forgot to mention here, so the start date in Excel will always be accurate every run and thus the end date will also be accurate
- Required columns: Display Name, Chart of Accounts, Accounting Calendar, Starting Period, Index Name to Reingest, icalstring, arguments 1-20 if applicable

#### 5. **SQLite Log Export Tool (`export_logs.py`)**
New utility converts crash-proof SQLite logs to searchable text files.
- One-command export: `python export_logs.py --all` exports all logs instantly
- Auto-finds logs in Desktop/project folders (no paths needed)
- Supports Ctrl+F search, grep (Linux/Mac), and PowerShell Select-String (Windows)
- grep = Globally search for a Regular Expression and Print 

#### 6. **Visual Flowchart Documentation (`flowchart/` folder)**
Interactive diagrams explain system architecture and workflows visually.
- Includes full flowchart for how to run and what to do's
- Faster onboarding and troubleshooting with visual guides
- Complements written documentation for presentations and knowledge transfer

### How It Works - The Smart Retry Flow
```
┌──────────────────────────────────────────────┐
│ 1. UI Configuration Tasks (Ui_Automation.py) │
│    • Setup procurement access                │
│    • Run 23 configuration tasks              │
└──────────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────────┐
│ 2. REST API Job Submission (main.py)         │
│    • Submit 42 jobs via Oracle REST API      │
│    • Monitor with timeout thresholds         │
│    • Track: Overall timeout + WAIT timeout   │
│    • Log failures → job_status_tracker.json  │
│    • Return code: 0=success, 1=failures      │
└──────────────────────────────────────────────┘
                    ↓
         ┌─────────┴─────────┐
         │  Return Code?     │
         └─────────┬─────────┘
                   │
         ┌─────────┴─────────┐
         │                   │
    ┌────▼────┐         ┌────▼────┐
    │ Code: 0 │         │ Code: 1 │
    │ Success │         │ Failures│
    └────┬────┘         └────┬────┘
         │                   │
         ▼                   ▼
┌─────────────────┐  ┌──────────────────────────┐
│ Skip UI Retry   │  │ 3. Smart Retry (ui_ess)  │
│ All jobs passed │  │    • Read status JSON     │
│                 │  │    • Match failed jobs    │
└─────────────────┘  │    • Retry via UI only    │
                     │    • Check ACL status     │
                     └──────────────────────────┘
                                ↓
                     ┌──────────────────────────┐
                     │ 4. Result                │
                     │    • Failed jobs retried │
                     │    • ACL jobs verified   │
                     │    • Full automation     |
                     |    • UI doesn't run ACL  │
                     └──────────────────────────┘
```

### Configuration - Timeout Settings

Edit `RESTAPI_ESS/main.py` (~line 150):
```python
# Default settings (production)
MAX_POLL_TIME_SECONDS = 600    # 10 minutes max per job
POLL_INTERVAL_SECONDS = 10     # Check status every 10 seconds
MAX_WAIT_STATE_TIME = 300      # 5 minutes max in WAIT state

# For testing (fast timeouts)
MAX_POLL_TIME_SECONDS = 30     # Jobs timeout after 30 seconds
POLL_INTERVAL_SECONDS = 10      # Check every 10 seconds
MAX_WAIT_STATE_TIME = 30       # 30 seconds in WAIT
```

### Benefits of v1.0.1

 **Full Automation**: No manual intervention needed when jobs timeout  
 **Time Savings**: Only retries failed jobs (saves 10-15 minutes per run)  
 **Visibility**: Clear logging of which jobs failed and why  
 **Resilience**: Handles network issues, Oracle slowness, and timeouts gracefully  
 **Safety**: Critical ACL jobs monitored separately with alerts  
 **Maintainability**: Single Excel file for both REST API and UI  

### Files Modified in v1.0.1

| File | Changes | 
|------|---------|
| `RESTAPI_ESS/main.py` | Timeout tracking, status logging, display name tracking | 
| `ui_ess_jobs.py` | JSON integration, smart retry matching | 
| `Ui_Automation.py` | REST API orchestration, return code handling | 
| `job_status_tracker.json` | **NEW FILE** - Auto-created during REST API run |
| `export_logs.py` | **NEW FILE**  - For exporting SQLite logs|

### Excel File Requirements ((client)P2T.xlsx)

The Excel file now includes:
- **Chart of Accounts, Accounting Calendar, Starting Period**: For Balance Cube jobs (rows 1-3) for the UI version of ESS Jobs


**Note**: The start date formula ensures the Excel file is always current - no manual date updates needed (this was in original version forgot to mention)
A document for how to create the Excel parameters manually will be sent as well. Another way is if you manually run or schedule a job and cop the request id if you run this command for
for example 
cd RESTAPI_ESS
python get_job_details.py 6354128
It should give you the correct parameters but I don't use this method it is basically still manual and I just never really expanded on it, plus I already have the Excel. I never used it except maybe one time.
Just giving some option files that's why I included everything, maybe some ideas can be imporved on not sure. I can't remeber if it does the extraction correctly.
### Testing the Smart Retry System

**Quick test with fast timeouts:**

1. Set fast timeouts in `RESTAPI_ESS/main.py`:
```python
   MAX_POLL_TIME_SECONDS = 30
   MAX_WAIT_STATE_TIME = 15
```

2. Run the full automation:
```powershell
   python Ui_Automation.py
   or press play button on Ui_Automation.py (make sure all tasks are commented out except task1 if you want to only test ESS)
```

3. Expected behavior:
   - UI tasks complete normally
   - REST API submits 43 jobs → some timeout after 30 seconds
   - Status tracker shows failures
   - UI automatically retries the timed-out jobs
   - Console logs show "RETRYING X FAILED JOBS VIA UI"

4. Check the results:
```powershell
   cat RESTAPI_ESS\job_status_tracker.json
```

### Migration from v1.0.0

**Good news: No changes required!** 

- I will be providing the whole folder with update as 1.0.1
- The system automatically creates `job_status_tracker.json`
- UI retry logic is triggered automatically by `Ui_Automation.py`
- All existing functionality preserved

### Known Limitations
- ACL jobs (rows 37, 40-42) may require manual verification due to Oracle UI ambiguity
- File lock: REST API must close Excel before UI can read it 

---

## File Inventory & Line Counts

*BEFORE:*
Component	File Name	                Line Count	      Status / Notes
UI        Core	ui_automation.py	      3,839	          Primary UI Driver. Tasks 14 & 20 have low success rates.
Helper	post_refresh_automation_helper.py	237	    Utilities.
UI Logger    terminal_logger.py             337      SQLite-based crash-proof logging. Fully documented
REST API	main.py	                        936      	Main API Orchestrator. Toggle DRY_MODE here.
REST API	fusion_api.py	                432	      Core API wrapper for authentication and POST/GET.
REST API	backfill_from_log.py	        401	        Recovery tool for failed API submissions.
REST API	job_audit_xlsx.py	            133	        Generates Excel reports of job statuses.
REST API	get_job_details.py	            121	        Fetches metadata for specific ESS jobs.
REST API	logger.py	                     32	        Standardized logging format.
REST API	job_config.py	                 35	    Environment-specific job mappings.
UI Backup	ui_ess_jobs.py	               1,344	UI fallback for jobs. Manual intervention at row 37, 40,41,42.
TOTAL		~7,847

---
# File Inventory & Line Counts
*AFTER:*
| Component | File Name                     | Line Count        | Status / Notes |
|-----------|-----------                    |------------       |----------------|
| UI Core | `Ui_Automation.py`              | 3,928             | Primary UI Driver. **v1.0.1: Added REST API orchestration** |
| Helper| `post_refresh_automation_helper.py`| 237              | Utilities |
| UI Logger | `terminal_logger.py`           | 337              | SQLite-based crash-proof logging |
| REST API | `main.py`                      | 1,285             | Main API Orchestrator. **v1.0.1: Added bett timeout tracking** |
| REST API | `fusion_api.py`                | 432                | Core API wrapper for authentication |
| REST API | `backfill_from_log.py`         | 401                | Recovery tool for failed submissions |
| REST API | `job_audit_xlsx.py`            | 133               | Excel audit reports |
| REST API | `get_job_details.py`           | 121                | Job metadata inspector |
| REST API | `logger.py`                    | 32                | Standardized logging |
| REST API | `job_config.py`                | 35                | Environment-specific mappings |
| UI Backup | `ui_ess_jobs.py`              | 1,554                | UI fallback. **v1.0.1: Added smart retry integration** |
| **NEW** | `job_status_tracker.json`       | Auto-gen          | **v1.0.1: Status tracker file** |
| UI Export | `export_logs.py`              | 188            | **NEW v1.0.1:** SQLite → text converter |
| **TOTAL** | | **8683** | |
________________________________________
# Phase 1: UI Automation (ui_automation.py)
This phase handles the tasks that do not have accessible REST APIs.
**v1.0.1 Enhancement**: Now orchestrates REST API job submission and triggers UI retry based on return codes.
***Known Issues & Manual Tasks
•	Data Access Section: Currently Commented Out. Roles and Data Access are assumed to be granted prior to execution.
•	Oracle UI Bug: In the Data access section When clicking the "(client) BU" after row selection, Oracle occasionally refreshes the DOM and removes the element.
•	Tasks 2.2, 14 & 20: Success rate is low due to Oracle's finicky UI response timing.
•	Task 16: Intermittent issue where only one row is deleted instead of the full set.
________________________________________
# Phase 2: REST API ESS (RESTAPI_ESS Folder)
The high-speed engine of the suite. It reads from scenarios/ and submits jobs directly to the Oracle Scheduler. Added one more ESS job.
**v1.0.1 Enhancement**: Added timeout-aware polling and automatic status tracking for smart retry coordination.
*** Critical Files
•	main.py : This is the entry point. You must manually set DRY_MODE = False inside this file to actually submit jobs to the server.
•	fusion_api.py: Handles the OAUTH/Basic Auth handshake. If you get a 503 error, the failure usually happens here during the session post.
________________________________________
# Phase 3: UI ESS Jobs Backup (ui_ess_jobs.py)
**v1.0.1 Enhancement**: Added one more ESS job
Used for ESS jobs if REST API is not working.
•	Manual Intervention Required (comment out in ui_automation the call to main.py at end and uncomment out the ui_ess_jobs call):
•	Rows 38 & 43: These specific rows tend to get stuck in the UI loop; keep an eye on the browser during these steps. Choose to just manually do 38,41,42,43
________________________________________
 Installation & Recovery
1.	Initialize VENV: python -m venv .venv
2.	Install Playwright: python -m playwright install chromium
3.	Environment: Ensure .env exists in both the root and RESTAPI_ESS folders.

=====================================================================================================================================================
 1. Installation & Environment Setup
To initialize this system on a new machine, follow these steps to ensure all dependencies are aligned.
Open your terminal (VS Code Terminal recommended), activate your virtual environment
# Create virtual environment
python -m venv .venv

# Activate (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Activate (Mac/Linux)
source .venv/bin/activate
, and run this combined command to install everything at once:
PowerShell
pip install playwright requests python-dotenv openpyxl pandas urllib3 python-dateutil && python -m playwright install chromium
Detailed Requirements
•	Python 3.10+: The base language.
•	Playwright: For Phase 1 (UI). It requires the chromium binary to be installed separately via the command above.
•	Requests & Urllib3: For Phase 2 (API) communication and retry logic.
•	Openpyxl & Pandas: For reading the Excel scenarios and writing audit logs.
•	Dotenv: For managing sensitive .env credentials.

# ----- Environment Files (.env)------ #
TWO locations:

# Project root (for UI automation)
RESTAPI_ESS folder (for REST API jobs)

# Root .env Example:
envTENANT_BASE_URL=https://(client)-(client)-dev10.fa.ocs.oraclecloud.com
FUSION_USERNAME=your.username@company.com
FUSION_PASSWORD=YourPassword123!

FUSION_BASEURL=https://(client)-(client)-dev10.fa.ocs.oraclecloud.com

# Multi-user setup (comma-separated aliases)
FUSION_USERS=SCHEDULER,USER1

# Credentials per alias
FUSION_SCHEDULER_LOGIN=scheduler@company.com
FUSION_SCHEDULER_PASSWORD=Password123!
FUSION_USER1_LOGIN=user1@company.com
FUSION_USER1_PASSWORD=AnotherPass456!

# Some Requirements
Package         Version      Purpose
Python           3.10+     Base language
Playwright      Latest     UI automation (requires chromium binary)
Requests        Latest     HTTP REST API calls
urllib3         Latest      Retry logic for API calls
openpyxl        Latest      Excel file reading/writing
pandas          Latest      Optional (data analysis)
python-dotenv   Latest     Environment variable management

________________________________________
2. # Phase 1: UI Automation (ui_automation.py)
 This script is a robust, logic-heavy driver designed to handle the "volatile" nature of the Oracle Fusion UI.
How it Works: Section by Section
1.	Authentication & Profile Setup: Uses browser_context to maintain a persistent session. It targets the TENANT_BASE_URL from the .env.
2.	Task Navigation Loop: The script doesn't just "click"; it verifies page state. It navigates to the required location and searches for specific task names.
3.	Refinement & Stability Features:
o	Soft Fail / Skip Logic: The script uses try-except blocks around individual tasks. If a non-critical task fails (like a finicky UI toggle), it logs the error, takes a screenshot, and skips to the next task instead of crashing the entire run.
o	DOM Resilience: Implements "Smart Waits." Instead of fixed timers, it uses page.wait_for_selector to react to Oracle's loading speeds.
o	Dynamic Regex Selectors: To handle Oracle’s changing ID tags (e.g., _FOpt1:_UISpageCust), the script uses Regex patterns to find buttons based on text or partial IDs.
o 	Dynamic Instance Detection: Automatically parses the URL (e.g., DEV2 vs TEST) to set the correct environment labels for logging
o Hand-off Logic: At the very end, it automatically triggers the REST API suite by "faking" a terminal command (sys.argv), ensuring a seamless transition from UI to API.
o Can add screenshot(page) wherever needed/wanted but wrapper also screenshots important part

# Task List (23 Tasks Total)
Task #	     Description	              Success Rate       Notes
1	         Disable Notifications	         ~100%       	Stable
2	         Update Banner Message	         ~100%       	Auto-generates refresh date
2.2	         Update Logo/Theme	             ~30%       	Oracle UI timing issues
3	         Disable ADP Deliveries	          ~95%       	Occasionally misses one row
4	         Add IPs to Whitelist	         ~100%	        Stable
7	         Turn Off PO Communication	     ~100%       	Three profile updates
9	         Disable AP Payment Transmission  ~95%       	Checkbox detection tricky
10	         Update Corp Card Program	     ~100%       	SFTP endpoint swap
11	         Disable GetThere Configuration	 ~100%       	Dummy credentials
12	         Remove Receivables Emails	     ~100%       	Clears 6 fields
14	         Setup Sandbox Integration	     ~20%       	Oracle UI very unstable
15	         Update HireRight Config	     ~100%	        Test credentials
16	         Prenote SFTP Update	          ~90%	        Second row sometimes missed
17	         Create ADMIN Users (OPKey)	     ~100%       	Two users with roles
18	         Create Tech User (GUID)	     ~100%	        Environment-specific
20	         Update Preferred Gender Links   ~25%       	Oracle UI timing
21	         Disable Remittance Emails	     ~100%	        Clears email field
22	         Update Checklist URLs	         ~100%	        11 URL updates
23	         Deploy Position Flexfields  	 ~100%	        EIT + Legislative


# Pre-Task Setup:
Setup Procurement Access for User:
    Why Commented: Some Roles/data access assumed pre-configured
    Known Oracle Bug: (client) BU DOM refresh issue (25% failure rate)
    **NEW V1.0.2** 

________________________________________
 3. # Phase 2: REST API  (RESTAPI_ESS Folder)
main.py 
•	The Brain: Orchestrates the flow. It determines which mode to run (Scenario vs. Folder).
•	Scenario Logic: It maps specific inputs (like P2T) to specific files (like (client)P2T.xlsx).
•	Dry Run Toggle: Contains the safety switch. When DRY_MODE = True, it validates Excel data without actually hitting the Oracle server.
• **NEW v1.0.1**: Timeout monitoring, status tracking, returns exit code for UI retry trigger
fusion_api.py. Added one more ESS job
•	The Connector: This is the only file that "talks" to Oracle.
•	Payload Construction: It takes Excel rows and transforms them into the complex JSON requestParameters array that Oracle's /ess/rest/scheduler/v1/requests endpoint requires.
•	Session Management: Handles the Basic Auth and keeps the connection alive for bulk submissions.
backfill_from_log.py 
•	The Safety Net: Specifically designed for "Half-Finished" runs. If your computer sleeps or the network drops, this script reads the text-based ess.log, extracts the Request IDs, and updates your Excel audit sheet so you don't submit duplicates.
job_audit_xlsx.py 
•	The Reporter: Manages job_runs.xlsx. It uses a "Check-Before-Write" logic to ensure that every Request ID is unique in the log, providing a clean history of the refresh.
get_job_details.py 
•	The Inspector: A utility to "Reverse Engineer" Oracle jobs. If a new job is added, you run this with a Request ID to see exactly how Oracle wants the arguments formatted.
logger.py 
•	The Standardizer: Ensures every component (UI and API) speaks the same language in the console. It enforces the ISO 8601 UTC timestamp format for all logs.
job_config.py 
•	The Template: Defines the "Blueprints" for jobs. It ensures that data passed from Excel matches the data structure required by the Python classes.
________________________________________
 4. # Phase 3: UI ESS Backup (ui_ess_jobs.py)
 **v1.0.1 Enhancement**: Transformed from manual backup to intelligent retry system integrated with REST API status tracker. Added one more ESS job.
•	The Fallback: This is a secondary UI script focused strictly on the "Scheduled Processes" screen.
•   It is fallback because 4 tasks should be ran manually as it makes sense for all 4 to be ran manual (although two work) 38,43 will not work, 42, 41 will work
•   This is idempotent Oracle will not let you submit duplicates
•	Complexity Handling: It is used for ESS jobs when the Rest API does not work, it is a backup file
•	Operational Note: It is triggered at the end of the UI automation if the user has uncommented the call.

o   Goes through the UI to select and schedule the required jobs, uses an Excel sheetwith job names and params. Thought it could be more dynamic that way if wanting to add new jobs.
o Definetly slower than restapi but will always work, sometimes restapi from Oracle Instance does not work, maybe overloaded etc.
### How It Works Now (v1.0.1)

1. **Reads Status Tracker**: Loads `job_status_tracker.json` from REST API run
2. **Identifies Failures**: Extracts list of failed/timed-out job names
3. **Smart Matching**: Matches failed jobs to Excel rows by Display Name
4. **Selective Retry**: Only retries jobs that actually failed (skips successes)
5. **ACL Monitoring**: Checks critical ACL job status with hardcoded fallback

### Manual Intervention Notes

- **Rows 37, 40-42** (ACL Jobs): Oracle UI bugs with clicking makes UI automation unreliable
- **Recommendation**: Run these 4 jobs manually and verify after automation completes
- **Idempotent Design**: Oracle prevents duplicate submissions, safe to retry

### Operational Flow

- **Automatic Trigger**: Called by `Ui_Automation.py` when REST API returns code `1` (failures detected)
- **Excel Source**: Reads from same file as REST API (`(client)P2T.xlsx`)
- **Slower but Reliable**: UI-based submission always works even when REST API doesn't

________________________________________
 5. # Helper Utilities (post_refresh_automation_helper.py)

•	Environment Validator: Before the browser even opens, this file checks your .env for the existence of UI_USER and FUSION_BASEURL.
•	FileSystem Management: Handles the creation of timestamped screenshot folders (e.g., ./screenshots/2026-02-03/).
•	Recovery Logic: The recover_to_home feature ensures that if a task gets lost in a sub-menu, the script "panic-navigates" back to the main dashboard  to keep the automation moving
•  Every time a new task begins (set_current_task), the script automatically scans the /screenshots directory. Any folder with a modification timestamp older than 7 days is permanently deleted. This is for storage management.
________________________________________________
6. # Logging help (terminal_logger.py)

• Designed to be a partner supporting the screenshot function. Screenshots are a log form but now with this file the code logs what was printed in terminal.
• Crash-proof SQLite logging that captures ALL stdout/stderr
•Why SQLite Instead of Text Files?
    OneDrive Interference (original problem):
        o Developing on new laptop in OneDrive folder
        o OneDrive aggressively deleted text log files on crashes
        o File buffer issue: crashes before flush = lost logs
•SQLite Solution:
    o isolation_level=None = autocommit mode (no buffering)
    o Every line writes to disk INSTANTLY
    o Database files more resistant to OneDrive cleanup
    o 100% crash-proof - even Ctrl+C preserves all logs
•How It Works:
    o Hijacks sys.stdout and sys.stderr
    o SQLiteTeeLogger class: Splits output to both terminal AND database
    o Every print() statement → logged automatically
•Database Location (Current):
    o python# In setup_terminal_logging():
    o logs_dir = Path.home() / "Desktop" / "ui_automation_logs"
•Why Desktop?
    o Desktop folder outside OneDrive sync
    o Survives crashes
    o Can be moved back to project after moving project out of OneDrive

•To Move Back to Project Folder:
    o python# Change this line in setup_terminal_logging():
    o logs_dir = Path("logs")  # Instead of Path.home() / "Desktop" / "ui_automation_logs"

    o #Also change in cleanup_old_logs():
    o logs_dir = Path("logs")  # Instead of Path.home() / "Desktop" 
________________________________________
7. # export_logs.py - Terminal Log Exporter

**NEW in v1.0.1** - Convert SQLite logs to searchable text files

### Why This Tool Exists

•The Problem:
    - Terminal logs saved in SQLite (crash-proof) but not human-readable
    - Can't open `.db` files in Notepad or search with Ctrl+F
    - Have command prompt method but felt inefficient or hard to rememeber

•The Solution:
    - Converts `.db` → `.txt` in seconds
    - Preserves all timestamps and formatting
    - Auto-finds logs in Desktop/project folders
    - Batch export all logs at once
    - Easy to run file reminds you what to do  to run and the different methods

• Quick Commands
In terminal can type 
```powershell
python export_logs.py --all
# Export most recent log only
python export_logs.py --recent
# Export specific log file
python export_logs.py ui_automation_2026-02-26_14-38-39.db
# Export with custom output name
python export_logs.py input.db my_export.txt
# Show all options
python export_logs.py --help
```

• Where Files Are Saved
    - Default behavior:** Text files save next to the `.db` files with same name
    - Example:
        ```
        Before:
        ~/Desktop/ui_automation_logs/ui_automation_2026-02-26_14-38-39.db
        After:
        ~/Desktop/ui_automation_logs/ui_automation_2026-02-26_14-38-39.db
        ~/Desktop/ui_automation_logs/ui_automation_2026-02-26_14-38-39.txt  ← NEW!
        ```
• Auto-Find Feature:
    - Script automatically searches for logs in:
        1. `~/Desktop/ui_automation_logs/` (current default)
        2. `./logs/` (project folder)
        3. Current directory (if `.db` files present)

=========================================================================================================================================================

## Conclusion

This system is capable of performing **18/23 UI tasks + 43 ESS jobs** with intelligent retry logic for full automation resilience.

### Key Characteristics
 **Idempotent Design**: Safe to run multiple times, Oracle prevents duplicates  
 **Crash-Proof Logging**: SQLite-based terminal capture survives all crashes  
 **Smart Retry System (v1.0.1)**: Automatic failure recovery without manual intervention  
 **Production Ready**: Currently in use for  P2T across multiple (client) instances  

### Developer Notes
I am self-learned python developer, hopefully it is good and understandable for people who understand python well.
I tested on multiple instances and even used for  P2T for (client) different instances.
It is ready for use as I currently use it.

**Developed by Alex Cacaras**  
**UPDATE Version 1.0.1 - March 2026**

## Support & Troubleshooting
Please check flowchart folder for flowchartreadme for more details.
### Check These First
1. **Console logs**: Detailed error messages and step-by-step execution
2. **job_status_tracker.json**: See exactly which jobs failed and why
3. **logs/job_runs.xlsx**: Complete audit trail of all job submissions
4. **Screenshots folder**: Visual evidence of UI state at failure points
5. **Manual validation**: check on Oracle

### Common Issues

**"Job names don't match"**
- REST API and UI using different Excel files
- **Fix**: Both now use same file (`(client)P2T.xlsx`)

**"UI skipped all jobs but REST API showed failures"**
- Display Name mismatch between JSON and Excel
- **Fix**: v1.0.1 ensures Display Name consistency

