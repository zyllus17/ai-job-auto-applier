---
framework_version: 1.1.0
---

# Universal Agent Guidelines: AI Job Search

This workspace powers an end-to-end, autonomous job search and application engine compatible with **ALL major AI coding assistants**:
- **Google Antigravity (AGY)**
- **Claude Code (Anthropic)**
- **Cursor / Windsurf / Copilot Workspace**
- **Gemini CLI / OpenAI Codex**

--------------------------------------------------------------------------------

## 🚀 ZERO-TOUCH AI ONBOARDING PROTOCOL (For Any AI Agent)

When a user clones this repository or points you (the AI) to it, **execute this protocol immediately**:

### Step 1: Detect User State
Check if `CLAUDE.md` or `cv/main_example.tex` contains default candidate data or needs to be set up for a new user.

### Step 2: Ask the User ONLY 3 Things
Do NOT ask the user to install packages, configure paths, or run complex commands. Ask only:
> "Welcome to AI Job Search! I will configure your autonomous job search engine on your system and handle all setup automatically. I only need 3 things from you:
> 
> 1. **Your Resume / CV**: Paste your resume text here, attach your CV file, or drop your PDF into `documents/cv/`.
> 2. **Target Roles & Location**: What roles do you want (e.g. AI Automation Engineer, Senior Flutter, Fullstack, ML Engineer) and what is your preference (Remote Worldwide, Remote India, US, Europe relocation)?
> 3. **Google Sheet Link (Optional)**: If you want live tracking with a fresh tab created every day (`YYYY-MM-DD`), paste your Apps Script Webhook URL (instructions in `tools/google_apps_script.js`). If skipped, I will track everything locally.
> 
> That's all I need! Once you reply, I will set up your profile, compile your tailored ModernCV PDF, verify your job search tools, and start finding jobs."

### Step 3: Automate Everything Behind the Scenes
Once the user provides the 3 items:
1. **Toolchain Check**: Ensure Bun and Python 3 (`pypdf`, `pyyaml`) are installed. Ensure TinyTeX is available in user space (`~/Library/TinyTeX` or in PATH).
2. **Profile Generation**: Ingest their CV and update:
   - `CLAUDE.md`
   - `.claude/skills/job-application-assistant/01-candidate-profile.md`
   - `.claude/skills/job-scraper/search-queries.md`
3. **Compile Master CV**: Compile `cv/main_example.tex` via `lualatex` and verify with `python3 tools/verify_pdf.py cv/main_example.pdf`.
4. **Google Sheets**: If webhook URL was provided, save with `python3 tools/google_sheets_sync.py --set-webhook "<URL>"`.
5. **Start Discovery**: Run `/run-jobs-search` or execute a search cycle!

--------------------------------------------------------------------------------

## 💡 SPECIAL RECRUITER HOOK RULE: 1–2 HOUR DEMO PROJECTS
Whenever evaluating a job posting where the candidate has a skill gap (e.g., LangGraph, Vector DBs, Model Context Protocol, AWS Bedrock):
1. **Identify the highest-demand missing skill**.
2. **Design a 1–2 hour proof-of-concept project** (exact minimal architecture, libraries, and deliverable).
3. **Provide a 45-second demo video recommendation** (what screen recording or GIF to create and attach to the application note to prove hands-on mastery to recruiters).

--------------------------------------------------------------------------------

## 🔄 CONTINUOUS AUTONOMOUS DAEMON
The script `tools/daemon_job_runner.py` (or `/run-jobs-search`) runs continuously on the user's laptop:
- Discovers jobs on LinkedIn & FreeHire on an hourly schedule.
- Deduplicates via `seen_jobs.json`.
- Compiles tailored 2-page ModernCV (`cv/main_<company>_<role>.pdf`) and 1-page Cover Letter (`cover_<company>_<role>.pdf`).
- Prepares application packages in `documents/applications/<company>_<role>/`.
- Logs each day's applications to a dedicated date tab in Google Sheets (`YYYY-MM-DD`).
- Handles rate limits and quota throttling with exponential backoff.
- Runs indefinitely until killed by user.
