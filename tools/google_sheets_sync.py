#!/usr/bin/env python3
"""
google_sheets_sync.py - Syncs job application and tracking entries to Google Sheets with daily tabs.

Usage:
  python3 tools/google_sheets_sync.py --set-webhook "https://script.google.com/macros/s/..."
  python3 tools/google_sheets_sync.py --test-row
  python3 tools/google_sheets_sync.py --file jobs.json
"""

import sys
import os
import json
import csv
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.resolve()
CONFIG_FILE = REPO_ROOT / "google_sheet_config.json"
LOCAL_TRACKER_CSV = REPO_ROOT / "job_search_tracker.csv"

def get_webhook_url() -> str:
    url = os.environ.get("GOOGLE_SHEET_WEBHOOK_URL", "").strip()
    if url:
        return url
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                return cfg.get("webhook_url", "").strip()
        except Exception:
            pass
    return ""

def set_webhook_url(url: str):
    cfg = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            pass
    cfg["webhook_url"] = url.strip()
    cfg["updated_at"] = datetime.now().isoformat()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    print(f"[OK] Saved Google Sheets Webhook URL to {CONFIG_FILE}")

def log_to_local_csv(rows: list):
    """Always writes to local CSV as offline backup and system of record."""
    file_exists = LOCAL_TRACKER_CSV.exists()
    fieldnames = [
        "timestamp", "company", "title", "fitScore", "status",
        "missingSkill", "suggestedProject", "location", "url", "notes"
    ]
    with open(LOCAL_TRACKER_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if not file_exists:
            writer.writeheader()
        for r in rows:
            writer.writerow(r)

def sync_jobs_to_sheet(rows: list, date_str: str = None) -> dict:
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
        
    # Always log locally first
    log_to_local_csv(rows)
    
    webhook_url = get_webhook_url()
    if not webhook_url:
        return {
            "status": "local_only",
            "message": "Google Sheets Webhook URL not set. Data saved to local job_search_tracker.csv.",
            "count": len(rows),
            "date": date_str
        }
        
    payload = {
        "date": date_str,
        "rows": rows
    }
    
    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=req_data,
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp_body = resp.read().decode("utf-8")
            try:
                res = json.loads(resp_body)
                print(f"[OK] Synced {len(rows)} row(s) to Google Sheet tab '{date_str}'.")
                return res
            except json.JSONDecodeError:
                print(f"[OK] Post succeeded: {resp_body}")
                return {"status": "success", "raw": resp_body}
    except Exception as e:
        print(f"[WARNING] Could not sync to Google Sheet: {e}. Data saved locally.", file=sys.stderr)
        return {"status": "error", "error": str(e), "saved_locally": True}

def run_sheets_daemon(interval_mins=5):
    import time
    print("📊 Google Sheets Sync Daemon started.")
    print("   Watching job_search_tracker.csv and syncing to Google Sheets...")
    
    tracker_csv = REPO_ROOT / "job_search_tracker.csv"
    last_synced_mtime = 0
    
    while True:
        webhook = get_webhook_url()
        if not webhook or "your_apps_script" in webhook or len(webhook) < 15:
            print("📊 [SHEETS] Notice: GOOGLE_SHEET_WEBHOOK_URL not configured yet.")
            print("   To enable: Deploy tools/google_apps_script.js and paste Webhook URL in the Settings tab.")
            print("   Standing by (checking every 30s)...")
            time.sleep(30)
            continue
            
        if tracker_csv.exists():
            current_mtime = tracker_csv.stat().st_mtime
            if current_mtime > last_synced_mtime:
                import csv
                try:
                    with open(tracker_csv, "r", encoding="utf-8") as f:
                        reader = list(csv.DictReader(f))
                    if reader:
                        print(f"🔄 [SHEETS] Syncing {len(reader)} rows from tracker to Google Sheet...")
                        sync_jobs_to_sheet(reader)
                        last_synced_mtime = current_mtime
                except Exception as e:
                    print(f"[SHEETS ERROR] {e}")
        time.sleep(interval_mins * 60)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--set-webhook":
        if len(sys.argv) > 2:
            set_webhook_url(sys.argv[2])
        else:
            print("Error: Provide the webhook URL. Example: --set-webhook https://script.google.com/...")
            sys.exit(1)
    elif len(sys.argv) > 1 and sys.argv[1] == "--test-row":
        test_data = [{
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "company": "Test Company Inc.",
            "title": "Senior AI Automation Engineer",
            "fitScore": 92,
            "status": "Staged - Ready to Submit",
            "missingSkill": "LangGraph (Demonstrated via mini-project)",
            "suggestedProject": "FastRAG-Agent: 2-node LangGraph Doc QA",
            "location": "Remote Worldwide",
            "url": "https://linkedin.com/jobs/test",
            "notes": "Test row from Antigravity system check"
        }]
        res = sync_jobs_to_sheet(test_data)
        print(json.dumps(res, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "--file":
        with open(sys.argv[2], "r", encoding="utf-8") as f:
            data = json.load(f)
            rows = data if isinstance(data, list) else [data]
            res = sync_jobs_to_sheet(rows)
            print(json.dumps(res, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "--once":
        import csv
        tracker_csv = REPO_ROOT / "job_search_tracker.csv"
        if tracker_csv.exists():
            with open(tracker_csv, "r", encoding="utf-8") as f:
                reader = list(csv.DictReader(f))
            sync_jobs_to_sheet(reader)
    else:
        run_sheets_daemon()
