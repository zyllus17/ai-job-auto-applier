---
framework_version: 1.0.0
---

# Antigravity Workspace Guidelines: AI Job Auto-Applier

This workspace powers an autonomous job evaluation, scraping, resume tailoring, and interview preparation assistant.

--------------------------------------------------------------------------------

## 🚀 ZERO-TOUCH ONBOARDING PROTOCOL (For New Users & Cloned Repos)

If you are an Antigravity agent running in this workspace on a NEW user's computer (or if `CLAUDE.md` has placeholders / needs reconfiguration):
**DO NOT overwhelm the user with manual setup steps or technical configuration.**
Do all technical work (installing Bun, Python packages, TinyTeX, LaTeX libraries) automatically behind the scenes.

Ask the user ONLY for these **3 Essential Items**:
> "Welcome to AI Job Auto-Applier! I will configure and run your autonomous job search engine on your machine. I only need 3 things from you:
> 
> 1. **Your Resume / CV**: Paste your resume text here, attach your CV file, or drop your PDF into `documents/cv/`.
> 2. **Target Roles & Location**: What roles do you want (e.g. AI Engineer, Senior Flutter, Fullstack) and what is your work preference (Remote Worldwide, specific country, relocation)?
> 3. **Google Sheet Webhook URL (Optional)**: If you want real-time tracking in Google Sheets with a new tab created each day, paste your Apps Script Webhook URL (instructions in `tools/google_apps_script.js`). If skipped, I will track everything in local CSV.
>
> That's all I need! Once you reply, I will generate your tailored 2-page ModernCV PDF, verify your portal search tools, and start finding jobs."

Once the user provides these 3 items:
1. Populate `CLAUDE.md`, `.claude/skills/job-application-assistant/01-candidate-profile.md`, and `.claude/skills/job-scraper/search-queries.md`.
2. Generate baseline `cv/main_example.tex` and compile `cv/main_example.pdf` via `lualatex`.
3. If Google Sheet URL provided, save it via `python3 tools/google_sheets_sync.py --set-webhook "<URL>"`.
4. Launch continuous discovery daemon or present first batch of matches!

--------------------------------------------------------------------------------

## 👤 ACTIVE CANDIDATE PROFILE: Maruf Hassan
- **Primary Roles:** AI Automation Engineer & Senior Flutter Developer
- **Target Locations:** Remote Worldwide, Remote India, Kolkata, and Open to Relocation (Europe, US, Middle East, APAC)
- **Core Strengths:** Google Gemini LLM API, Slack Bot Automation, Multi-API Orchestration, Flutter 3 (ELSA Speak 100M+ downloads, SuperBrains Golden Dutch Interactive Award), Riverpod, Dart, Python.
- **Profile Source of Truth:** `CLAUDE.md` and `.claude/skills/job-application-assistant/01-candidate-profile.md`.

--------------------------------------------------------------------------------

## ⚙️ CORE WORKFLOWS & SLASH COMMANDS

1. **/run-jobs-search**:
   - Launches the continuous background daemon (`tools/daemon_job_runner.py`).
   - Runs indefinitely until killed by user.
   - Discovers jobs via LinkedIn & FreeHire, deduplicates, scores fit, generates tailored CV & Cover Letter PDFs, and syncs daily to Google Sheets (tab `YYYY-MM-DD`).
   - Resilient against model limits with exponential backoff.
2. **/scrape**: Searches configured job portals on demand.
3. **/rank**: Batch-scores and shortlists scraped jobs.
4. **/apply <url or description>**:
   - Evaluates fit against candidate profile.
   - Highlights any missing high-demand skill + proposes a **1–2 hour proof-of-concept project** (with 45s demo video instructions).
   - Generates tailored ModernCV PDF (`cv/main_<company>_<role>.pdf`) via `lualatex`.
   - Generates tailored Cover Letter PDF (`cover_letters/cover_<company>_<role>.pdf`) via `xelatex`.
   - Prepares application form answers in `documents/applications/<company>_<role>/form_fields.txt`.
5. **/interview**: Stage-specific prep pack with real STAR stories.
6. **/upskill**: Deep skill gap heatmap and targeted learning resources.

--------------------------------------------------------------------------------

## 💡 SPECIAL RECRUITER HOOK RULE: 1–2 HOUR DEMO PROJECTS
Whenever evaluating a job where the candidate lacks a required skill (e.g. LangGraph, Vector DBs, AWS Bedrock):
1. State the exact high-demand gap.
2. Design a **minimal 1–2 hour working mini-project** (tech stack, exact architecture, deliverables).
3. Outline a **45-second screen recording / demo script** that the candidate can link in their application or share on LinkedIn to prove competence to the recruiter.

--------------------------------------------------------------------------------

## 📄 COMPILATION & TOOLPATHS
- TinyTeX / LuaLaTeX: `~/Library/TinyTeX/bin/universal-darwin/lualatex` (or in PATH)
- XeLaTeX: `~/Library/TinyTeX/bin/universal-darwin/xelatex` (or in PATH)
- Bun: `/opt/homebrew/bin/bun` (or in PATH)
- Python: Python 3.10+ with `pypdf`, `pyyaml`
