<p align="center">
  <h1 align="center">🤖 AI Job Auto-Applier: Autonomous Career Engine</h1>
  <p align="center">
    <b>The continuous, self-driving job application framework that runs on your laptop.</b><br>
    <i>Automated Discovery • ATS Tailored 2-Page CVs • 1-Page Cover Letters • Continuous Hunting • Google Sheets Daily Tracking • 1–2 Hr Recruiter Hook Projects</i>
  </p>
</p>

---

## 🌟 Why This Exists

Most job searches are exhausting: hours spent browsing boards, rewriting resumes, drafting cover letters, and manually updating spreadsheets.

**AI Job Auto-Applier** turns your AI coding assistant (**Google Antigravity, Claude Code, Cursor, Windsurf, Copilot, or Gemini CLI**) into an autonomous job hunter that:
1. **Scrapes active postings** on LinkedIn and global tech aggregators (FreeHire, etc.) 24/7.
2. **Evaluates fit (0–100)** against your real work experience.
3. **Compiles tailored 2-page ModernCV PDFs** (`lualatex`) and **1-page Cover Letters** (`xelatex`) for every matching role.
4. **Identifies skill gaps & designs 1–2 hour demo projects** (with 45s video demo scripts) to prove hands-on competence to recruiters.
5. **Syncs applications into Google Sheets** with a **dedicated new tab created automatically for each day** (`YYYY-MM-DD`).
6. **Runs continuously in the background** on your laptop until you tell it to stop.

---

## 🚀 Feed This to Your AI (Zero-Friction Setup)

You don't need to manually install dependencies or configure complex environments. Any modern AI coding assistant can set this up for you automatically.

### Just copy and paste this prompt into your AI:

```text
Clone and set up this autonomous job search engine: https://github.com/zyllus17/ai-job-auto-applier
Follow the instructions in GEMINI.md and AGENTS.md. 
Ask me only the 3 essential things you need from me, and automate all other setup behind the scenes.
```

### What your AI will ask you (Only 3 Things!):
1. **Your Resume / CV**: Paste your resume text, upload a PDF, or drop it into `documents/cv/`.
2. **Your Target Roles & Location**: (e.g. *AI Automation Engineer, Senior Flutter Developer, Remote Worldwide, India, US, Europe*).
3. **Google Sheets Webhook URL (Optional)**: If you want real-time tracking with a new tab created each day (see setup below).

**That's it!** The AI installs Bun, Python libraries, and TinyTeX in user-space, compiles your master CV PDF, and launches discovery.

---

## 💻 Alternative: 1-Command Terminal Setup

If you prefer terminal installation:

```bash
git clone https://github.com/zyllus17/ai-job-auto-applier.git
cd ai-job-auto-applier
bash quickstart.sh
```

The script automatically detects your OS, installs Bun and TinyTeX, prompts for your profile details, registers the global Antigravity skill, and sets up your workspace.

---

## ⚡ The 4 Core Superpowers

### 1. 🔄 Continuous Background Daemon (`/run-jobs-search`)
Runs quietly on your laptop and searches for new roles on an automated schedule (e.g., hourly).
- **Deduplication**: Remembers every job in `seen_jobs.json` so you never process the same posting twice.
- **Application Staging**: For every job scoring $\ge 70\%$ fit, it automatically generates a tailored ModernCV PDF, a custom cover letter PDF, form answers, and a briefing in `documents/applications/<company>_<role>/`.
- **Model Limit Resilience**: Handles rate limits with exponential backoff and keeps going indefinitely until killed.

### 2. 📄 Automated ATS-Compliant PDF Generation
- **CV Engine**: Compiles a sleek 2-page ModernCV banking style in blue accents via `lualatex`.
- **Cover Letter Engine**: Compiles a 1-page letter with custom typography via `xelatex`.
- **ATS Validator**: Checks extracted text and layout readability using `pypdf`.

### 3. 💡 High-Demand Skill Gaps & 1–2 Hour Recruiter Hook Projects
When an otherwise perfect job requires a skill you don't list (e.g., *LangGraph, Vector DBs, Model Context Protocol, AWS Bedrock, Kotlin Multiplatform*):
- The assistant identifies the highest-demand missing skill.
- Designs a **minimal 1–2 hour working mini-project** (clean architecture, lightweight libraries).
- Suggests a **45-second screen recording / GIF demonstration** you can attach to your application note or share on LinkedIn to immediately prove competence to the recruiter.

### 4. 📊 Google Sheets Sync with Daily Tabs (`YYYY-MM-DD`)
Every evaluated and staged job is logged in real-time to Google Sheets:
- Creates a fresh tab for each day (e.g., `2026-09-08`, `2026-09-09`).
- Beautifully formatted headers: *Timestamp, Company, Job Title, Fit Score, Status, Missing High-Demand Skill, Suggested 1-2 Hr Project, Location, Job URL, Notes*.
- Always saves an offline local backup in `job_search_tracker.csv`.

---

## 📊 How to Connect Google Sheets (60 Seconds)

1. Open [Google Sheets](https://sheets.new) and create a new spreadsheet (e.g., `Job Search Tracker`).
2. In the top navigation menu, click **Extensions > Apps Script**.
3. Delete any code and paste the contents of [`tools/google_apps_script.js`](tools/google_apps_script.js).
4. Click **Deploy > New deployment** (top right blue button).
5. Select **Web app**, set **Execute as: Me**, and **Who has access: Anyone**.
6. Click **Deploy**, authorize permissions, and copy the **Web App URL**.
7. In your terminal or chat, run:
   ```bash
   python3 tools/google_sheets_sync.py --set-webhook "https://script.google.com/macros/s/..."
   ```

---

## 🎮 Command Cheatsheet

| Command | What It Does |
| :--- | :--- |
| **`/run-jobs-search`** | Starts the autonomous background daemon on your laptop. Runs continuously until stopped. |
| **`/scrape`** | Executes an on-demand scrape across LinkedIn and FreeHire portals. |
| **`/rank`** | Batch-scores and shortlists recently scraped postings against your profile. |
| **`/apply <url or text>`** | Evaluates a single job, identifies skill gaps + 1-2 hr demo project, drafts tailored CV & cover letter PDFs, and prepares portal form answers. |
| **`/interview`** | Generates stage-specific interview prep packs mapping your real STAR stories to the job. |
| **`/upskill`** | Produces a skill-gap heatmap and targeted learning roadmaps across target postings. |

---

## 📂 Repository Architecture

```text
ai-job-auto-applier/
├── .agents/skills/               # Universal Agent Skills (LinkedIn, FreeHire, Application, Upskill)
├── .claude/                      # Core workflow methodology, commands & prompt templates
│   ├── commands/                 # Slash commands (/run-jobs-search, /scrape, /apply, etc.)
│   └── skills/                   # Evaluator, writer, and reviewer pipelines
├── cv/                           # Master ModernCV LaTeX template and compiled master PDF
│   ├── main_example.tex          # Master 2-page ModernCV template
│   └── main_example.pdf          # Baseline compiled PDF
├── cover_letters/                # Master cover letter template and styling
│   ├── cover_example.tex         # Master 1-page XeLaTeX cover letter
│   └── cover.cls                 # Class definitions & fonts
├── documents/
│   ├── applications/             # Auto-generated application packages (CV PDF, Cover PDF, briefing)
│   └── cv/                       # Your raw resumes / PDFs
├── tools/                        # Python & JavaScript automation toolchain
│   ├── daemon_job_runner.py      # Continuous autonomous job search daemon
│   ├── google_sheets_sync.py     # Multi-tab Google Sheets sync utility
│   ├── google_apps_script.js     # 25-line Apps Script Webhook template
│   └── verify_pdf.py             # ATS text extraction validator (pypdf)
├── AGENTS.md                     # Universal instructions for all AI coding agents
├── GEMINI.md                     # Antigravity native configuration & zero-touch protocol
├── quickstart.sh                 # 1-command cross-platform bash installer
└── SHARE_GUIDE.md                # Step-by-step sharing instructions for other developers
```

---

## 📤 How to Push to Your Own GitHub

To push this framework to your personal GitHub account so you can share it with others:

```bash
# 1. Create a new repository on GitHub (e.g. ai-job-auto-applier)
# 2. Update your git remote
git remote set-url origin https://github.com/zyllus17/ai-job-auto-applier.git

# 3. Stage and commit all changes
git add .
git commit -m "feat: complete autonomous AI job search engine with continuous daemon, PDF automation, and Google Sheets sync"

# 4. Push to your repository
git push -u origin master
```

---

<p align="center">
  <i>Built with ❤️ for autonomous career development. Fork it, customize it, and land your next role on autopilot.</i>
</p>
