# How to Share & Run AI Job Search on Any Computer

This framework is completely portable and built for **Google Antigravity**. Any developer can clone this repository and have a fully autonomous job application and tracking system running on their machine in under 2 minutes with **zero manual configuration**.

---

## 🚀 Option 1: Give Antigravity the GitHub Link (Zero Friction)

If the person already uses Google Antigravity, they don't even need to touch the terminal!

1. Clone or open this repository in Google Antigravity:
   ```text
   Set up this job search repository for me: https://github.com/<your-username>/ai-job-search
   ```
2. Antigravity immediately reads the built-in `GEMINI.md` protocol and will automatically ask them **only 3 things**:
   - **Their CV**: Paste resume text or drop their PDF into `documents/cv/`.
   - **Target Roles & Location**: (e.g. AI Engineer, Mobile Lead, Remote, India, Europe).
   - **Google Sheet Link (Optional)**: If they want live daily tracking.
3. Antigravity does **all technical work automatically**:
   - Installs Bun and Python dependencies.
   - Sets up TinyTeX for compiling 2-page ModernCV and cover letter PDFs.
   - Ingests their CV and builds their customized profile.
   - Activates the search engines and launches discovery!

---

## 💻 Option 2: 1-Command Terminal Quickstart

If they prefer running from the command line:

```bash
git clone https://github.com/<your-username>/ai-job-search.git
cd ai-job-search
bash quickstart.sh
```

The script automatically detects their OS, installs Bun and TinyTeX, prompts for their profile details, registers the global Antigravity skill, and sets up the workspace.

---

## 📊 How to Connect Google Sheets (Daily Tabs in 60 Seconds)

To have your applied jobs automatically logged into Google Sheets with a **separate tab for each day** (`YYYY-MM-DD`):

1. Open [Google Sheets](https://sheets.new) and create a new spreadsheet (e.g. `My Job Search Tracker`).
2. Click **Extensions > Apps Script** in the top menu.
3. Replace any code with the contents of [`tools/google_apps_script.js`](tools/google_apps_script.js).
4. Click **Deploy > New deployment** (top right blue button).
5. Select **Web app**, set **Execute as: Me**, and **Who has access: Anyone**.
6. Click **Deploy**, authorize permissions, and copy the **Web App URL**.
7. In your terminal or chat, run:
   ```bash
   python3 tools/google_sheets_sync.py --set-webhook "https://script.google.com/macros/s/..."
   ```
From then on, every job evaluated and applied to will automatically appear in a dedicated tab named after today's date!

---

## ⚡ Daily Usage Commands in Antigravity

- **`/run-jobs-search`**: Starts the autonomous background daemon. It runs continuously on your laptop, monitors LinkedIn and FreeHire, scores fit, compiles tailored PDFs, and syncs daily tabs to Google Sheets.
- **`/scrape`**: Search target portals on demand.
- **`/rank`**: Batch-score and rank all recently scraped jobs.
- **`/apply <URL or text>`**: Tailor your 2-page ModernCV PDF, write a custom cover letter PDF, generate application form answers, and suggest a 1-2 hr demo project for any missing skill.
- **`/interview`**: Generate mock questions and interview talking points using your real STAR examples.
- **`/upskill`**: Analyze skill gaps and get targeted learning roadmaps.
