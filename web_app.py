"""
Job Search Web App - Flask backend
דשבורד לחיפוש משרות והגשת מועמדות
"""

import csv
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from flask import Flask, Response, jsonify, request, send_from_directory

BASE_DIR = Path(__file__).parent

# DATA_DIR: on cloud set DATA_DIR=/data (persistent volume); locally defaults to project dir
_data_env = os.environ.get("DATA_DIR")
DATA_DIR   = Path(_data_env) if _data_env else BASE_DIR

RESULTS_DIR   = DATA_DIR / "results"
TRACKING_FILE = DATA_DIR / "job_tracking.json"
STATIC_DIR    = BASE_DIR / "static"   # static always next to the app

RESULTS_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

app = Flask(__name__, static_folder=str(STATIC_DIR))

# ─── Search state ───────────────────────────────────────────────────────────
search_state = {
    "running": False,
    "log": [],
    "started_at": None,
    "finished_at": None,
}
search_lock = threading.Lock()


# ─── Tracking helpers ────────────────────────────────────────────────────────

def load_tracking() -> dict:
    if TRACKING_FILE.exists():
        try:
            return json.loads(TRACKING_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_tracking(data: dict):
    TRACKING_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ─── CSV helpers ─────────────────────────────────────────────────────────────

def load_all_jobs() -> list[dict]:
    tracking = load_tracking()
    jobs = {}

    for csv_file in sorted(RESULTS_DIR.glob("jobs_*.csv"), reverse=True):
        try:
            with open(csv_file, encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    url = row.get("URL", "").strip()
                    if not url:
                        continue
                    job_id = url.replace("https://", "").replace("http://", "")[:80]
                    if job_id in jobs:
                        continue  # keep latest file's version
                    job = {
                        "id": job_id,
                        "title": row.get("Title", "").strip(),
                        "company": row.get("Company", "").strip(),
                        "location": row.get("Location", "").strip(),
                        "site": row.get("Site", "").strip(),
                        "url": url,
                        "score": _safe_int(row.get("Match_Score", "0")),
                        "requirements": row.get("Key_Requirements", "").strip(),
                        "notes": row.get("Notes", "").strip(),
                        "nir_match": row.get("Nir_Match", "").strip(),
                        "source_file": csv_file.name,
                    }
                    t = tracking.get(job_id, {})
                    job["status"] = t.get("status", "new")
                    job["user_notes"] = t.get("user_notes", "")
                    job["applied_at"] = t.get("applied_at", "")
                    jobs[job_id] = job
        except Exception as e:
            print(f"Error reading {csv_file}: {e}")

    return sorted(jobs.values(), key=lambda j: j["score"], reverse=True)


def _safe_int(val: str) -> int:
    try:
        return int(float(val))
    except Exception:
        return 0


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(str(STATIC_DIR), "index.html")


@app.route("/api/jobs")
def api_jobs():
    jobs = load_all_jobs()
    return jsonify({"jobs": jobs, "total": len(jobs)})


@app.route("/api/jobs/<path:job_id>", methods=["PATCH"])
def api_update_job(job_id):
    body = request.get_json(force=True)
    tracking = load_tracking()
    entry = tracking.get(job_id, {})
    if "status" in body:
        entry["status"] = body["status"]
        if body["status"] == "applied" and not entry.get("applied_at"):
            entry["applied_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    if "user_notes" in body:
        entry["user_notes"] = body["user_notes"]
    tracking[job_id] = entry
    save_tracking(tracking)
    return jsonify({"ok": True})


@app.route("/api/search/start", methods=["POST"])
def api_search_start():
    with search_lock:
        if search_state["running"]:
            return jsonify({"ok": False, "error": "חיפוש כבר פועל"}), 409
        search_state["running"] = True
        search_state["log"] = []
        search_state["started_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        search_state["finished_at"] = None

    threading.Thread(target=_run_agent, daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/search/status")
def api_search_status():
    with search_lock:
        return jsonify({
            "running": search_state["running"],
            "started_at": search_state["started_at"],
            "finished_at": search_state["finished_at"],
            "log_lines": len(search_state["log"]),
        })


@app.route("/api/search/log")
def api_search_log():
    """SSE stream of agent log lines."""
    offset = int(request.args.get("offset", 0))

    def generate():
        idx = offset
        while True:
            with search_lock:
                lines = search_state["log"][idx:]
                running = search_state["running"]
            for line in lines:
                yield f"data: {json.dumps(line, ensure_ascii=False)}\n\n"
                idx += 1
            if not running and idx >= len(search_state["log"]):
                yield "data: __DONE__\n\n"
                break
            time.sleep(0.5)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/stats")
def api_stats():
    jobs = load_all_jobs()
    by_status = {}
    by_site = {}
    by_score = {"8-10": 0, "5-7": 0, "1-4": 0}
    for j in jobs:
        by_status[j["status"]] = by_status.get(j["status"], 0) + 1
        by_site[j["site"]] = by_site.get(j["site"], 0) + 1
        s = j["score"]
        if s >= 8:
            by_score["8-10"] += 1
        elif s >= 5:
            by_score["5-7"] += 1
        else:
            by_score["1-4"] += 1
    return jsonify({"total": len(jobs), "by_status": by_status, "by_site": by_site, "by_score": by_score})


# ─── Agent runner ─────────────────────────────────────────────────────────────

def _run_agent():
    def log(line: str):
        with search_lock:
            search_state["log"].append(line)

    try:
        from agent_cloud import run_search
        run_search(log_callback=log, data_dir=RESULTS_DIR)
    except Exception as e:
        log(f"❌ שגיאה: {e}")
        import traceback
        log(traceback.format_exc())
    finally:
        with search_lock:
            search_state["running"] = False
            search_state["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys, io
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    else:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    port = int(os.environ.get("PORT", 5000))
    print(f"\n{'='*50}")
    print(f"  Job Search Dashboard")
    print(f"  http://localhost:{port}")
    print(f"{'='*50}\n")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
