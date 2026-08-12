"""
P2T Post-Refresh Automation Dashboard — Backend API
====================================================
Flask server that serves the React dashboard and runs automation.

ENDPOINTS:
    GET  /              — Serves the React dashboard (static files from dashboard/dist/)
    GET  /api/config    — Returns current .env values for pre-filling the dashboard
    POST /api/run       — Starts Ui_Automation.py with selected tasks
    GET  /api/stream    — SSE endpoint for live log streaming to browser
    GET  /api/status    — Returns current run status (idle/running/done)

USAGE:
    pip install flask flask-cors
    python dashboard_api.py
    Open http://localhost:5000

DESIGN DECISIONS:
    - Subprocess isolation: Ui_Automation.py runs as a separate process so if
      it crashes, the dashboard stays up
    - SSE over WebSocket: Simpler, one-directional, no extra dependencies
    - Environment override: Dashboard fields override .env values per-run
      so you can switch environments without editing files
    - Static file serving: Built React app served by Flask so the (client)
      only needs Python (no Node.js)
"""
# Load .env from project root
from flask import Flask, request, Response, jsonify, send_from_directory
from flask_cors import CORS
import subprocess, threading, queue, os, json, time, sys
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

app = Flask(__name__, static_folder="dashboard/dist", static_url_path="")
CORS(app)# Allow React dev server to talk to Flask during development

# Global run state
run_state = {
    "active": False,
    "process": None,
    "log_queue": queue.Queue(),
    "exit_code": None,
    "started_at": None,
    "tasks": None,
}

# ----Task definition for the dashboard----
TASK_LIST = [
    {"num": 0, "name": "Pre-Task: Procurement Access Setup", "category": "setup", "default": True},
    {"num": 1, "name": "Disable Email Notifications", "category": "ui", "default": True},
    {"num": 2, "name": "Update Banner Message", "category": "ui", "default": True},
    {"num": 3, "name": "Disable ADP Extract Deliveries", "category": "ui", "default": True},
    {"num": 4, "name": "Add IPs to Location-Based Access", "category": "ui", "default": True},
    {"num": 7, "name": "Turn Off PO Communication", "category": "ui", "default": True},
    {"num": 9, "name": "Disable AP Payment Transmission", "category": "ui", "default": True},
    {"num": 10, "name": "Update Corp Card Program to Non-Prod SFTP", "category": "ui", "default": True},
    {"num": 11, "name": "Disable GetThere Configuration", "category": "ui", "default": True},
    {"num": 12, "name": "Remove Receivables Email 'From' Values", "category": "ui", "default": True},
    {"num": 15, "name": "Update/Remove HireRight Configuration", "category": "ui", "default": True},
    {"num": 16, "name": "Pre-Note: Update JPMC SFTP / Disable Delivery", "category": "ui", "default": True},
    {"num": 17, "name": "Create ADMIN User Accounts (OPKey)", "category": "ui", "default": True},
    {"num": 18, "name": "Create Admin Tech User (Integration)", "category": "ui", "default": True},
    {"num": 21, "name": "Disable Separate Remittance Advice Emails", "category": "ui", "default": True},
    {"num": 22, "name": "Update Checklist URLs (Medical/Leave)", "category": "ui", "default": True},
    {"num": 23, "name": "Workforce Structure - Positions E-Flexfields", "category": "ui", "default": True},
]


#=======================
#==ROUTES
#=======================

@app.route("/")
def index():
    """Serve the React dashboard."""
    dist = Path(app.static_folder)
    if (dist / "index.html").exists():
        return send_from_directory(dist, "index.html")
    return """
    <h2>Dashboard not built yet</h2>
    <p>Run <code>cd dashboard && npm run build</code> first.</p>
    <p>Or use the React dev server at <code>http://localhost:5173</code></p>
    """, 200

@app.route("/api/config")
def get_config():
    """Return current .env values for pre-filling dashboard fields."""
    return jsonify({
        "url": os.getenv("TENANT_BASE_URL", ""),
        "username": os.getenv("FUSION_USERNAME", ""),
        "password": os.getenv("FUSION_PASSWORD", ""),
        "tasks": TASK_LIST,
        "ai_healer_enabled": os.getenv("AI_HEALER_ENABLED", "false").lower() == "true", #might remove if they don't want
    })

@app.route("/api/run", methods=["POST"])
def start_run():
    """Start the automation with selected tasks and environment config."""
    if run_state["active"]:
        return jsonify({"status": "error", "message": "A run is already in progress"}), 409
    data = request.json or {}
    tasks = data.get("tasks", "all")
    url = data.get("url", "").strip()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    #validation
    if not url:
        return jsonify({"status": "error", "message": "Instance URL is required"}), 400
    if not username:
        return jsonify({"status": "error", "message": "Username is required"}), 400
    if not password:
        return jsonify({"status": "error", "message": "Password is required"}), 400
    # Clear the log queue from any previous run
    while not run_state["log_queue"].empty():
        try:
            run_state["log_queue"].get_nowait()
        except queue.Empty:
            break
    # Reset state
    run_state["exit_code"] = None
    run_state["tasks"] = tasks

    # Build environment with dashboard overrides
    env = os.environ.copy()
    env["TENANT_BASE_URL"] = url
    env["FUSION_BASEURL"] = url  # auto-wire for REST API
    env["FUSION_USERNAME"] = username
    env["FUSION_PASSWORD"] = password
    env["ESS_POLL_TIMEOUT"] = str(data.get("poll_timeout", 1800))
    # Auto-wire alias credentials too
    fusion_users = env.get("FUSION_USERS", "").strip()
    if fusion_users:
        for alias in fusion_users.split(","):
            alias = alias.strip()
            if alias:
                env[f"FUSION_{alias}_LOGIN"] = username
                env[f"FUSION_{alias}_PASSWORD"] = password
    env["P2T_DASHBOARD_MODE"] = "1"
    # Build command
    script_path = str(PROJECT_ROOT / "Ui_Automation.py")
    cmd = [sys.executable, "-u", script_path]
    if tasks != "all":
        cmd.extend(["--tasks", tasks])

    #Run in background thread
    def _run_subprocess():
        run_state["active"] = True
        run_state["started_at"] = time.time()

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
                cwd=str(PROJECT_ROOT),
            )
            run_state["process"] = proc

            # Stream stdout line by line into the queue
            for line in proc.stdout:
                line = line.rstrip("\n\r")
                if line:
                    run_state["log_queue"].put({"type": "log", "text": line})
            proc.wait()
            run_state["exit_code"] = proc.returncode

        except Exception as e:
            run_state["log_queue"].put({"type": "log", "text": f"DASHBOARD ERROR: {e}"})
            run_state["exit_code"] = 1

        finally:
            run_state["log_queue"].put({
                "type": "done",
                "code": run_state["exit_code"],
                "elapsed": int(time.time() - run_state["started_at"]) if run_state["started_at"] else 0,
            })
            run_state["active"] = False
            run_state["process"] = None

    thread = threading.Thread(target=_run_subprocess, daemon=True)
    thread.start()

    return jsonify({"status": "started", "tasks": tasks})

@app.route("/api/stream")
def stream():
    """SSE endpoint — streams log lines to the browser in real-time."""
    def event_stream():
        while True:
            try:
                msg = run_state["log_queue"].get(timeout=30)
                yield f"data: {json.dumps(msg)}\n\n"
                if msg.get("type") == "done":
                    break
            except queue.Empty:
                # Send keepalive to prevent connection timeout
                yield f"data: {json.dumps({'type': 'keepalive'})}\n\n"

    return Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering if behind proxy
        }
    )
@app.route("/api/stop", methods=["POST"])
def stop_run():
    """Stop the currently running automation."""
    if not run_state["active"] or not run_state["process"]:
        return jsonify({"status": "error", "message": "No run in progress"}), 400

    try:
        run_state["process"].terminate()
        run_state["log_queue"].put({"type": "log", "text": "⚠ Run stopped by user from dashboard"})
        return jsonify({"status": "stopped"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ══════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 55)
    print("  P2T Post-Refresh Automation Dashboard")
    print("=" * 55)
    print(f"  Dashboard:  http://localhost:5000")
    print(f"  API:        http://localhost:5000/api/config")
    print(f"  Environment: {os.getenv('TENANT_BASE_URL', 'not set')}")
    print("=" * 55)
    print()

    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)     
