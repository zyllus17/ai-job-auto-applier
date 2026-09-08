# /run-jobs-search - Autonomous Continuous Job Search Daemon

Starts the autonomous continuous background job search daemon.

## Usage
- `/run-jobs-search`: Starts the daemon with default 60-minute interval.
- `/run-jobs-search --interval-mins 30`: Run discovery every 30 minutes.
- `/run-jobs-search --once`: Execute a single discovery, ranking, and staging cycle.

## What it does
1. Continuously monitors LinkedIn, FreeHire, and target boards.
2. Deduplicates against `seen_jobs.json`.
3. Scores fit and flags missing high-demand skills + suggests 1-2 hr projects.
4. Auto-compiles tailored 2-page ModernCV and 1-page Cover Letter PDFs.
5. Syncs new applications into Google Sheets under today's tab (`YYYY-MM-DD`).
6. Handles model limits with exponential backoff.
7. Runs indefinitely until killed.
