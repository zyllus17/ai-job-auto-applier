#!/usr/bin/env python3
"""
error_tracker.py - Centralized Error Tracker and Diagnostics System

Tracks, logs, and categorizes system errors, warnings, and tracebacks across
all autonomous services (Daemon, Browser Auto-Apply, Telegram Bot, Scaffolder,
Recruiter Outreach, Google Sheets Sync, and Web Dashboard).

Provides:
- Persistent logging to logs/errors.jsonl and logs/system.log
- In-memory ring buffer for real-time dashboard API querying
- Full traceback and context capture
- Component health diagnostics and error aggregation
"""

import os
import sys
import json
import time
import traceback
import threading
from datetime import datetime, timezone
from collections import deque, Counter
from pathlib import Path
from typing import Dict, List, Any, Optional

REPO_ROOT = Path(__file__).parent.parent.resolve()
LOGS_DIR = REPO_ROOT / "logs"
ERRORS_JSONL = LOGS_DIR / "errors.jsonl"
SYSTEM_LOG = LOGS_DIR / "system.log"

class ErrorTracker:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ErrorTracker, cls).__new__(cls)
                cls._instance._init_tracker()
            return cls._instance

    def _init_tracker(self):
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        self.error_buffer = deque(maxlen=500)
        self.max_file_size = 10 * 1024 * 1024  # 10 MB rotate
        self._load_recent_persisted()

    def _load_recent_persisted(self):
        """Preload last 100 errors from errors.jsonl if available."""
        if ERRORS_JSONL.exists():
            try:
                lines = []
                with open(ERRORS_JSONL, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            lines.append(line)
                for line in lines[-100:]:
                    try:
                        self.error_buffer.append(json.loads(line))
                    except Exception:
                        pass
            except Exception:
                pass

    def record_error(
        self,
        service: str,
        error: Any,
        context: Optional[Dict[str, Any]] = None,
        severity: str = "ERROR",
        error_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Record a structured error or exception with traceback.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Extract message, type, and traceback
        if isinstance(error, Exception):
            err_type = error_type or type(error).__name__
            msg = str(error) or repr(error)
            tb = traceback.format_exc()
            if tb.strip() == "NoneType: None":
                # If called outside active exception handler, capture caller stack
                tb = "".join(traceback.format_stack()[:-1])
        else:
            err_type = error_type or "ApplicationError"
            msg = str(error)
            tb = "".join(traceback.format_stack()[:-1])

        entry = {
            "id": f"err_{int(time.time() * 1000)}_{len(self.error_buffer)}",
            "timestamp": timestamp,
            "service": service,
            "error_type": err_type,
            "message": msg,
            "severity": severity.upper(),
            "traceback": tb,
            "context": context or {}
        }

        with self._lock:
            self.error_buffer.append(entry)
            self._persist_entry(entry)

        return entry

    def record_warning(self, service: str, message: str, context: Optional[Dict[str, Any]] = None):
        return self.record_error(service, message, context=context, severity="WARNING", error_type="Warning")

    def record_info(self, service: str, message: str, context: Optional[Dict[str, Any]] = None):
        return self.record_error(service, message, context=context, severity="INFO", error_type="Info")

    def _persist_entry(self, entry: Dict[str, Any]):
        """Append to logs/errors.jsonl and logs/system.log with rotation."""
        try:
            # JSONL log
            with open(ERRORS_JSONL, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")

            # Human-readable log
            time_str = entry["timestamp"][:19].replace("T", " ")
            sev = entry["severity"]
            svc = entry["service"]
            msg = entry["message"]
            log_line = f"[{time_str}] [{sev}] [{svc}] {msg}\n"
            
            with open(SYSTEM_LOG, "a", encoding="utf-8") as f:
                f.write(log_line)
                if entry["severity"] in ("ERROR", "CRITICAL") and entry["traceback"]:
                    # Indent traceback
                    indented_tb = "\n".join("    " + line for line in entry["traceback"].strip().splitlines())
                    f.write(f"{indented_tb}\n")

            # Rotate if too large
            if ERRORS_JSONL.exists() and ERRORS_JSONL.stat().st_size > self.max_file_size:
                old_file = LOGS_DIR / f"errors_{int(time.time())}.jsonl"
                ERRORS_JSONL.rename(old_file)
        except Exception as e:
            print(f"[ErrorTracker Write Error] {e}", file=sys.stderr)

    def get_errors(
        self,
        limit: int = 100,
        service: Optional[str] = None,
        severity: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve filtered errors from buffer."""
        with self._lock:
            items = list(self.error_buffer)

        if service:
            items = [e for e in items if e.get("service") == service]
        if severity:
            items = [e for e in items if e.get("severity") == severity.upper()]
        if search:
            search_low = search.lower()
            items = [
                e for e in items
                if search_low in e.get("message", "").lower()
                or search_low in e.get("error_type", "").lower()
                or search_low in e.get("service", "").lower()
                or search_low in e.get("traceback", "").lower()
            ]

        items.reverse()  # Newest first
        return items[:limit]

    def clear_errors(self) -> int:
        """Clears the in-memory error buffer and archives the JSONL file."""
        with self._lock:
            count = len(self.error_buffer)
            self.error_buffer.clear()
            if ERRORS_JSONL.exists():
                try:
                    archive_path = LOGS_DIR / f"errors_archived_{int(time.time())}.jsonl"
                    ERRORS_JSONL.rename(archive_path)
                except Exception:
                    pass
            return count

    def get_summary(self) -> Dict[str, Any]:
        """Returns error aggregation metrics across services."""
        with self._lock:
            items = list(self.error_buffer)

        total = len(items)
        by_service = Counter(e.get("service", "unknown") for e in items)
        by_severity = Counter(e.get("severity", "ERROR") for e in items)
        by_type = Counter(e.get("error_type", "Unknown") for e in items)
        
        recent_criticals = [
            e for e in reversed(items)
            if e.get("severity") in ("ERROR", "CRITICAL")
        ][:5]

        return {
            "total_events": total,
            "errors_count": by_severity.get("ERROR", 0) + by_severity.get("CRITICAL", 0),
            "warnings_count": by_severity.get("WARNING", 0),
            "info_count": by_severity.get("INFO", 0),
            "by_service": dict(by_service),
            "by_severity": dict(by_severity),
            "top_error_types": dict(by_type.most_common(5)),
            "recent_criticals": recent_criticals,
            "logs_file": str(SYSTEM_LOG),
            "jsonl_file": str(ERRORS_JSONL)
        }

# Global singleton instance
_tracker = ErrorTracker()

def record_error(service: str, error: Any, context: Optional[Dict[str, Any]] = None, severity: str = "ERROR", error_type: Optional[str] = None):
    return _tracker.record_error(service, error, context=context, severity=severity, error_type=error_type)

def record_warning(service: str, message: str, context: Optional[Dict[str, Any]] = None):
    return _tracker.record_warning(service, message, context=context)

def record_info(service: str, message: str, context: Optional[Dict[str, Any]] = None):
    return _tracker.record_info(service, message, context=context)

def get_errors(limit: int = 100, service: Optional[str] = None, severity: Optional[str] = None, search: Optional[str] = None):
    return _tracker.get_errors(limit=limit, service=service, severity=severity, search=search)

def clear_errors():
    return _tracker.clear_errors()

def get_error_summary():
    return _tracker.get_summary()

if __name__ == "__main__":
    print("Testing ErrorTracker...")
    try:
        1 / 0
    except Exception as ex:
        err = record_error("test_service", ex, context={"operation": "unit_test_math"})
        print("Logged error:", err["id"], err["error_type"])

    summary = get_error_summary()
    print("Summary:", json.dumps(summary, indent=2))
    print("✅ ErrorTracker test passed!")
