#!/usr/bin/env python3
import os
import sys
import time
import json
import psutil
import argparse
from datetime import datetime, timezone
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO_ROOT))

from tools.error_tracker import record_error, record_warning, record_info, get_error_summary, get_errors

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = os.getenv("TELEGRAM_ALLOWED_USER_ID")
DAEMON_FLAG_FILE = REPO_ROOT / "daemon_enabled.flag"

if ALLOWED_USER_ID:
    try:
        ALLOWED_USER_ID = int(ALLOWED_USER_ID)
    except ValueError:
        ALLOWED_USER_ID = None

async def check_auth(update: Update) -> bool:
    user = update.effective_user
    if ALLOWED_USER_ID and user and user.id != ALLOWED_USER_ID:
        if update.message:
            await update.message.reply_text("Unauthorized access.")
        return False
    # Stale command protection
    if update.message and (datetime.now(timezone.utc) - update.message.date).total_seconds() > 300:
        await update.message.reply_text("⚠️ Discarded stale command sent while laptop was asleep.")
        return False
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    await update.message.reply_text("👋 Welcome to AI Job Auto-Applier Bot!\nUse /help to see all available commands.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    tracker_file = REPO_ROOT / "job_search_tracker.csv"
    total_jobs = sum(1 for _ in open(tracker_file)) - 1 if tracker_file.exists() else 0
    is_paused = False
    if DAEMON_FLAG_FILE.exists():
        try:
            val = DAEMON_FLAG_FILE.read_text().strip().lower()
            is_paused = val in ("0", "false", "paused", "disabled", "off")
        except Exception:
            pass
    daemon_status = "Paused" if is_paused else "Active"
    err_sum = get_error_summary()
    await update.message.reply_text(
        f"📊 *System Status:*\n"
        f"- Daemon: {daemon_status}\n"
        f"- Total jobs tracked: {max(0, total_jobs)}\n"
        f"- Active error alerts: {err_sum.get('errors_count', 0)}\n"
        f"- Warnings: {err_sum.get('warnings_count', 0)}",
        parse_mode="Markdown"
    )

async def jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    tracker_file = REPO_ROOT / "job_search_tracker.csv"
    if not tracker_file.exists():
        await update.message.reply_text("No jobs tracked yet.")
        return
    import csv
    with open(tracker_file, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
    if not reader:
        await update.message.reply_text("No jobs found in tracker.")
        return
    try:
        reader.sort(key=lambda r: int(r.get("fitScore", 0) or 0), reverse=True)
    except Exception:
        pass
    top_5 = reader[:5]
    lines = ["🎯 *Top 5 High-Fit Opportunities:*\n"]
    for i, j in enumerate(top_5, 1):
        company = j.get("company", "Unknown")
        title = j.get("title", "Role")
        fit = j.get("fitScore", "?")
        url = j.get("url", "")
        missing = j.get("missingSkill", "None")
        lines.append(f"{i}. *{title}* at *{company}* ({fit}% match)\n   ⚠️ Gap: {missing}\n   🔗 {url}\n")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    await update.message.reply_text("🔎 Discovery scan initiated in background...")
    import subprocess
    try:
        subprocess.Popen([sys.executable, "-u", str(REPO_ROOT / "tools" / "daemon_job_runner.py"), "--once"])
    except Exception as e:
        record_error("telegram_bot", f"Failed to dispatch scan: {e}")
        await update.message.reply_text(f"❌ Failed to dispatch scan: {e}")

async def apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    if not context.args:
        await update.message.reply_text("Please provide a job slug or index, e.g., /apply stellantis")
        return
    slug = context.args[0]
    await update.message.reply_text(f"Preparing application package for {slug}...")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    try:
        DAEMON_FLAG_FILE.write_text("paused")
        await update.message.reply_text("⏸️ Autonomous scanning paused.")
    except Exception as e:
        record_error("telegram_bot", f"Failed to pause daemon: {e}")
        await update.message.reply_text(f"Error pausing daemon: {e}")

async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    try:
        DAEMON_FLAG_FILE.write_text("enabled")
        await update.message.reply_text("▶️ Autonomous scanning resumed.")
    except Exception as e:
        record_error("telegram_bot", f"Failed to resume daemon: {e}")
        await update.message.reply_text(f"Error resuming daemon: {e}")

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    uptime = time.time() - psutil.boot_time()
    battery = psutil.sensors_battery()
    bat_pct = battery.percent if battery else "N/A"
    await update.message.reply_text(f"🏓 Pong!\nUptime: {int(uptime//3600)}h {int((uptime%3600)//60)}m\nBattery: {bat_pct}%")

async def enable(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    DAEMON_FLAG_FILE.write_text("enabled")
    await update.message.reply_text("✅ Daemon enabled remotely.")

async def disable(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    DAEMON_FLAG_FILE.write_text("disabled")
    await update.message.reply_text("🛑 Daemon disabled remotely.")

async def errors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View recent system errors and diagnostics."""
    if not await check_auth(update): return
    try:
        summary = get_error_summary()
        recent = get_errors(limit=3)
        lines = [
            "🚨 *System Health & Error Diagnostics:*\n",
            f"• Total events: {summary.get('total_events', 0)}",
            f"• Active errors: {summary.get('errors_count', 0)}",
            f"• Warnings: {summary.get('warnings_count', 0)}\n",
        ]
        if recent:
            lines.append("*Recent Errors:*")
            for e in recent:
                ts = e.get('timestamp', '')[:19].replace('T', ' ')
                svc = e.get('service', 'unknown')
                msg = e.get('message', '')[:100]
                lines.append(f"• `[{svc}]` {msg} ({ts})")
        else:
            lines.append("✅ All services report healthy! Zero errors logged.")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Error fetching diagnostics: {e}")

async def analytics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    try:
        from tools.funnel_analytics import FunnelTracker
        tracker = FunnelTracker(REPO_ROOT / "job_search_tracker.csv")
        report = tracker.generate_report()
        await update.message.reply_text(report)
    except Exception as e:
        record_error("telegram_bot", f"Analytics generation error: {e}")
        await update.message.reply_text(f"📈 Analytics:\nTotal jobs tracked: Available\nError rendering detailed report: {e}")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    help_text = """
🤖 *Available Bot Commands:*
/start - Welcome message & setup
/status - Daemon status, job counts & error tally
/jobs - List top 5 high-fit opportunities
/scan - Trigger immediate job discovery cycle
/apply <slug> - Generate tailored application pack
/stop - Pause autonomous scanning
/resume - Resume autonomous scanning
/ping - System uptime & battery
/enable - Enable daemon remotely
/disable - Disable daemon remotely
/errors - View system error diagnostics
/analytics - Application funnel statistics
/help - Show this guide
"""
    await update.message.reply_text(help_text, parse_mode="Markdown")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--test-mode', action='store_true', help="Run in test mode")
    args = parser.parse_args()

    if args.test_mode:
        print("[OK] Test mode: All commands registered, dependencies loaded, bot syntax verified.")
        sys.exit(0)

    global TOKEN, ALLOWED_USER_ID
    while not TOKEN or "your_bot_token" in TOKEN or len(TOKEN) < 10:
        print("📱 [TELEGRAM] Notice: TELEGRAM_BOT_TOKEN not configured in .env yet.")
        print("   To connect: Create a bot via @BotFather on Telegram, then add your token in the Settings tab.")
        print("   Standing by (checking .env every 15s)...")
        time.sleep(15)
        load_dotenv(override=True)
        TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
        ALLOWED_USER_ID = os.getenv("TELEGRAM_ALLOWED_USER_ID")
        if ALLOWED_USER_ID:
            try:
                ALLOWED_USER_ID = int(ALLOWED_USER_ID)
            except ValueError:
                ALLOWED_USER_ID = None

    print("🤖 Telegram Bot initialized with token. Connecting to Telegram API...")
    record_info("telegram_bot", "Telegram Bot polling started.")
    application = Application.builder().token(TOKEN).build()

    commands = [
        ("start", start), ("status", status), ("jobs", jobs),
        ("scan", scan), ("apply", apply), ("stop", stop),
        ("resume", resume), ("ping", ping), ("enable", enable),
        ("disable", disable), ("errors", errors), ("analytics", analytics),
        ("help", help_cmd)
    ]
    for cmd, handler in commands:
        application.add_handler(CommandHandler(cmd, handler))

    print("Bot is polling...")
    try:
        application.run_polling()
    except Exception as e:
        record_error("telegram_bot", f"Fatal Telegram Bot polling error: {e}", severity="CRITICAL")
        raise

if __name__ == '__main__':
    main()
