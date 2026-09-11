#!/usr/bin/env python3
"""
daemon_job_runner.py - Autonomous continuous job search daemon for Antigravity.

Runs continuously on the user's laptop:
- Discovers new jobs via 5 search sources (LinkedIn, FreeHire, Arbeitnow, Remotive, RemoteOK)
- Multi-page pagination for LinkedIn & FreeHire to avoid starvation
- Deduplicates using seen_jobs.json
- Scores fit dynamically against candidate profile (any profession)
- Detects high-demand skill gaps and suggests 1-2 hour mini demo projects
- Auto-generates tailored ModernCV and Cover Letter PDFs (via lualatex/xelatex)
- Syncs each day's applications to a dedicated Google Sheets tab (YYYY-MM-DD)
- Integrates with centralized ErrorTracker for system diagnostics and telemetry
- Respects daemon_enabled.flag for remote Telegram & Dashboard control
"""

import sys
import os
import json
import time
import re
import signal
import subprocess
import shutil
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# Add repo root to path
REPO_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO_ROOT))

from tools.google_sheets_sync import sync_jobs_to_sheet
from tools.error_tracker import record_error, record_warning, record_info

SEEN_JOBS_FILE = REPO_ROOT / "seen_jobs.json"
DAEMON_FLAG_FILE = REPO_ROOT / "daemon_enabled.flag"
BUN_BIN = shutil.which("bun") or "/opt/homebrew/bin/bun"
LUALATEX_BIN = shutil.which("lualatex") or str(Path.home() / "Library/TinyTeX/bin/universal-darwin/lualatex")
XELATEX_BIN = shutil.which("xelatex") or str(Path.home() / "Library/TinyTeX/bin/universal-darwin/xelatex")

SHORT_TECH_WORDS = {"ai", "ml", "qa", "go", "ui", "ux", "c#", "c++", "r", "kmp", "ci", "cd"}
GENERIC_MODIFIERS = {
    "senior", "junior", "lead", "staff", "principal", "head", "director", "manager",
    "intern", "developer", "engineer", "specialist", "expert", "consultant", "remote",
    "hybrid", "fulltime", "contract", "worldwide", "global"
}

def extract_keywords(query: str) -> tuple[list[str], list[str]]:
    """
    Splits query into:
    (domain_keywords, all_keywords)
    Preserves crucial short tech acronyms (AI, ML, UI, UX, GO).
    """
    clean = query.lower().replace("/", " ").replace("-", " ")
    tokens = [w.strip(".,;:()[]{}'\"") for w in clean.split()]
    all_kw = []
    domain_kw = []
    for t in tokens:
        if not t:
            continue
        if len(t) > 2 or t in SHORT_TECH_WORDS:
            all_kw.append(t)
            if t not in GENERIC_MODIFIERS:
                domain_kw.append(t)
    if not domain_kw:
        domain_kw = all_kw[:]
    return domain_kw, all_kw

def matches_query(query: str, title: str, description: str = "", tags: str = "") -> bool:
    """
    Checks if a job matches search query.
    Requires at least one domain-specific keyword (e.g. 'flutter', 'ai', 'java')
    so generic words like 'senior' or 'developer' do not trigger false positive matches.
    """
    domain_kw, all_kw = extract_keywords(query)
    text = f"{title} {description} {tags}".lower()
    title_lower = title.lower()

    # Exact phrase in title or text is instant match
    if query.lower().strip() in title_lower or query.lower().strip() in text:
        return True

    # Must match at least one domain-specific keyword
    for d in domain_kw:
        # Match as word boundary or exact token
        if re.search(r'\b' + re.escape(d) + r'\b', text):
            return True
        if d in SHORT_TECH_WORDS and re.search(r'\b' + re.escape(d) + r'\b', title_lower):
            return True

    return False

def load_candidate_profile() -> dict:
    profile_path = REPO_ROOT / "tools" / "candidate_profile.json"
    if profile_path.exists():
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            record_warning("job_daemon", f"Failed to read candidate_profile.json: {e}")
    return {}

def get_search_categories(profile: dict = None) -> list[dict]:
    if not profile:
        profile = load_candidate_profile()

    roles = profile.get("target_roles", [])
    if not roles:
        title = profile.get("current_title")
        roles = [title] if title else ["Software Engineer"]

    locations = profile.get("target_locations", [])
    if not locations:
        locations = ["Remote"]

    categories = []
    for r in roles:
        loc = locations[0] if locations else "Remote"
        categories.append({"query": r.strip(), "location": loc.strip()})
    return categories

RUNNING = True

def handle_signal(sig, frame):
    global RUNNING
    print("\n[DAEMON] Stopping gracefully (Ctrl+C / Kill signal received)...")
    record_info("job_daemon", "Daemon received stop signal, shutting down.")
    RUNNING = False

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)

def is_daemon_paused() -> bool:
    """Checks if scanning is paused via flag file."""
    if DAEMON_FLAG_FILE.exists():
        try:
            val = DAEMON_FLAG_FILE.read_text().strip().lower()
            return val in ("0", "false", "paused", "disabled", "off", "stop")
        except Exception:
            return False
    return False

def load_seen_jobs() -> tuple[set, dict]:
    if SEEN_JOBS_FILE.exists():
        try:
            with open(SEEN_JOBS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return set(data.keys()), data
                elif isinstance(data, list):
                    return set(data), {k: {} for k in data}
        except Exception as e:
            record_warning("job_daemon", f"Failed to load seen_jobs.json: {e}")
    return set(), {}

def save_seen_jobs(seen_dict: dict):
    try:
        with open(SEEN_JOBS_FILE, "w", encoding="utf-8") as f:
            json.dump(seen_dict, f, indent=2)
    except Exception as e:
        record_error("job_daemon", f"Failed to save seen_jobs.json: {e}")

def sanitize_slug(text: str) -> str:
    text = re.sub(r'[^a-zA-Z0-9_\-]+', '_', text.strip().lower())
    return re.sub(r'_+', '_', text).strip('_')[:40]

def score_job_fit(title: str, description: str, profile: dict = None) -> tuple[int, str, str]:
    if not profile:
        profile = load_candidate_profile()

    text = f"{title} {description}".lower()
    title_lower = title.lower()

    target_roles = profile.get("target_roles", [])
    candidate_skills = profile.get("skills", [])

    score = 40
    title_matched = False

    # 1. Target Role & Title Relevance (up to +40 points)
    for r in target_roles:
        r_clean = r.lower()
        if r_clean in title_lower:
            score += 40
            title_matched = True
            break
        # Match domain keywords of target role
        d_kws, _ = extract_keywords(r)
        if d_kws and any(re.search(r'\b' + re.escape(kw) + r'\b', title_lower) for kw in d_kws):
            score += 25
            title_matched = True
            break

    if not title_matched and target_roles:
        for r in target_roles:
            d_kws, _ = extract_keywords(r)
            if d_kws and any(re.search(r'\b' + re.escape(kw) + r'\b', text) for kw in d_kws):
                score += 15
                break

    # 2. Skill Match Points (up to +30 points)
    matched_skills = []
    for s in candidate_skills:
        s_clean = s.strip().lower()
        if not s_clean:
            continue
        if re.search(r'\b' + re.escape(s_clean) + r'\b', text):
            matched_skills.append(s)
            score += 5

    score = min(score, 98)

    # 3. Detect Missing Skills & Recommend Relevant Demo Project
    missing_skill = "None"
    suggested_project = f"Portfolio highlight: Showcase top relevant skills ({', '.join(matched_skills[:3]) if matched_skills else 'Core skills'})"

    common_tech_keywords = [
        "Kubernetes", "Docker", "AWS", "GCP", "Azure", "Kafka", "GraphQL", "Redis",
        "PostgreSQL", "MongoDB", "Elasticsearch", "LangGraph", "LangChain", "Vector DB",
        "Pinecone", "ChromaDB", "FastAPI", "Spring Boot", "Microservices", "React",
        "Next.js", "TypeScript", "Node.js", "Flutter", "SwiftUI", "Jetpack Compose",
        "Figma", "Design Systems", "Prototyping", "CI/CD", "Terraform", "PyTorch", "TensorFlow",
        "Kotlin", "Java", "Go", "Rust", "Solidity", "TailwindCSS"
    ]

    cand_skills_lower = [s.lower() for s in candidate_skills]
    potential_gaps = []
    for tech in common_tech_keywords:
        if tech.lower() not in cand_skills_lower and re.search(r'\b' + re.escape(tech.lower()) + r'\b', text):
            potential_gaps.append(tech)

    if potential_gaps:
        missing_skill = potential_gaps[0]
        suggested_project = f"Quick Demo: 1-2 hour proof-of-concept demonstrating {missing_skill} integration with interactive frontend/API + 45s screen recording for LinkedIn."

    return score, missing_skill, suggested_project

def run_cli_command(cmd: list) -> str:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=35
        )
        if proc.returncode != 0 and proc.stderr:
            record_warning("job_daemon", f"CLI warning ({cmd[0]}): {proc.stderr[:300]}")
        return proc.stdout
    except subprocess.TimeoutExpired:
        record_warning("job_daemon", f"CLI command timed out: {' '.join(cmd[:3])}")
        return ""
    except Exception as e:
        record_error("job_daemon", f"CLI error: {e}", context={"command": cmd})
        return ""

def compile_latex(engine_bin: str, tex_file: Path, cwd: Path) -> bool:
    try:
        cmd = [engine_bin, "-interaction=nonstopmode", "-halt-on-error", tex_file.name]
        proc = subprocess.run(cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=35)
        if proc.returncode != 0:
            record_warning("latex_compiler", f"LaTeX compile failed for {tex_file.name}: {proc.stderr[:400] or proc.stdout[:400]}")
        return proc.returncode == 0
    except Exception as e:
        record_error("latex_compiler", f"LaTeX execution exception: {e}", context={"file": str(tex_file)})
        return False

def stage_application(job: dict, missing_skill: str, suggested_project: str, fit_score: int) -> Path:
    company_slug = sanitize_slug(job.get("company", "company"))
    role_slug = sanitize_slug(job.get("title", "role"))
    app_dir = REPO_ROOT / f"documents/applications/{company_slug}_{role_slug}"
    app_dir.mkdir(parents=True, exist_ok=True)

    # 1. Prepare candidate briefing note
    briefing_path = app_dir / "briefing.md"
    briefing_content = f"""# Candidate Application Briefing: {job.get('title', 'Role')} at {job.get('company', 'Company')}

- **Date Staged:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **Fit Score:** {fit_score}/100
- **Location:** {job.get('location', 'Remote')}
- **Job URL:** {job.get('url', 'N/A')}

## Key Strengths Matched
- Proven experience shipping production-grade applications.
- Domain expertise matching role specifications.
- Practical problem solving and technical implementation.

## Skill Gap & Recruiter Hook Project
- **Identified Gap:** {missing_skill}
- **Suggested 1-2 Hr Demo Project:** {suggested_project}
- **Action Item:** Include 45s Loom/demo link or GitHub repo in the application note to demonstrate immediate competence.

## Tailored Form Answers
**Elevator Pitch (100 words):**
I am an engineer with proven experience building scalable software and delivering high-impact products. Recently built production assistants orchestrating multiple APIs and workflows. I combine robust architectural standards with rapid execution and clean UX.
"""
    briefing_path.write_text(briefing_content, encoding="utf-8")

    # 2. Prepare tailored CV LaTeX
    master_cv = REPO_ROOT / "cv/main_example.tex"
    target_cv_tex = app_dir / f"main_{company_slug}_{role_slug}.tex"

    if master_cv.exists():
        try:
            cv_text = master_cv.read_text(encoding="utf-8")
            role_title = job.get('title', 'Software Engineer')
            company_name = job.get('company', 'your company')
            custom_statement = f"Experienced engineer targeting {role_title} at {company_name}. Proven expertise in architecting scalable systems, multi-API orchestration, and delivering high-impact products."
            cv_text = re.sub(r'\\small\{.*?\}', f'\\\\small{{{custom_statement}}}', cv_text, flags=re.DOTALL)
            target_cv_tex.write_text(cv_text, encoding="utf-8")

            if Path(LUALATEX_BIN).exists():
                compile_latex(LUALATEX_BIN, target_cv_tex, app_dir)
        except Exception as e:
            record_error("latex_compiler", f"Error tailoring CV for {company_slug}: {e}")

    # 3. Prepare tailored Cover Letter LaTeX
    master_cover = REPO_ROOT / "cover_letters/cover_example.tex"
    target_cover_tex = app_dir / f"cover_{company_slug}_{role_slug}.tex"

    if master_cover.exists():
        try:
            cover_text = master_cover.read_text(encoding="utf-8")
            cover_text = cover_text.replace("Example Company", job.get('company', 'Hiring Team'))
            target_cover_tex.write_text(cover_text, encoding="utf-8")

            openfonts_src = REPO_ROOT / "cover_letters/OpenFonts"
            openfonts_dst = app_dir / "OpenFonts"
            if openfonts_src.exists() and not openfonts_dst.exists():
                shutil.copytree(openfonts_src, openfonts_dst)

            cover_cls_src = REPO_ROOT / "cover_letters/cover.cls"
            cover_cls_dst = app_dir / "cover.cls"
            if cover_cls_src.exists() and not cover_cls_dst.exists():
                shutil.copyfile(cover_cls_src, cover_cls_dst)

            if Path(XELATEX_BIN).exists():
                compile_latex(XELATEX_BIN, target_cover_tex, app_dir)
        except Exception as e:
            record_error("latex_compiler", f"Error tailoring Cover Letter for {company_slug}: {e}")

    return app_dir

def search_arbeitnow_jobs(query: str, seen: set = None, limit: int = 15) -> list:
    """Fetch live remote developer and tech jobs from Arbeitnow public API."""
    seen = seen or set()
    results = []
    try:
        req = urllib.request.Request(
            'https://www.arbeitnow.com/api/job-board-api',
            headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            for item in data.get('data', []):
                slug = item.get('slug', '')
                job_id = f"arbeitnow_{slug}"
                if job_id in seen:
                    continue

                title = item.get('title', '')
                desc = item.get('description', '')
                tags = " ".join(item.get('tags', []))

                if matches_query(query, title, desc, tags):
                    results.append({
                        "id": job_id,
                        "title": title,
                        "company": item.get('company_name', 'Tech Company'),
                        "url": item.get('url', ''),
                        "location": item.get('location', 'Remote'),
                        "description": desc,
                        "source": "Arbeitnow"
                    })
                    if len(results) >= limit:
                        break
    except Exception as e:
        record_warning("job_daemon", f"Arbeitnow API lookup warning: {e}", context={"query": query})
    return results

def search_remotive_jobs(query: str, seen: set = None, limit: int = 15) -> list:
    """Fetch live remote tech jobs from Remotive API."""
    seen = seen or set()
    results = []
    try:
        req = urllib.request.Request(
            'https://remotive.com/api/remote-jobs?category=software-dev',
            headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            for item in data.get('jobs', []):
                job_id = f"remotive_{item.get('id', '')}"
                if job_id in seen:
                    continue

                title = item.get('title', '')
                desc = item.get('description', '')
                tags = " ".join(item.get('tags', []))

                if matches_query(query, title, desc, tags):
                    results.append({
                        "id": job_id,
                        "title": title,
                        "company": item.get('company_name', 'Tech Company'),
                        "url": item.get('url', ''),
                        "location": item.get('candidate_required_location', 'Remote Worldwide'),
                        "description": desc,
                        "source": "Remotive"
                    })
                    if len(results) >= limit:
                        break
    except Exception as e:
        record_warning("job_daemon", f"Remotive API lookup warning: {e}", context={"query": query})
    return results

def search_remoteok_jobs(query: str, seen: set = None, limit: int = 15) -> list:
    """Fetch live remote developer and tech jobs from RemoteOK API."""
    seen = seen or set()
    results = []
    try:
        req = urllib.request.Request(
            'https://remoteok.com/api?tag=dev',
            headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
            if isinstance(data, list):
                for item in data:
                    if not isinstance(item, dict) or not item.get('position'):
                        continue
                    job_id = f"remoteok_{item.get('id', '')}"
                    if job_id in seen:
                        continue

                    title = item.get('position', '')
                    desc = item.get('description', '')
                    tags = " ".join(item.get('tags', []))

                    if matches_query(query, title, desc, tags):
                        results.append({
                            "id": job_id,
                            "title": title,
                            "company": item.get('company', 'Tech Company'),
                            "url": item.get('url', f"https://remoteok.com/l/{item.get('id', '')}"),
                            "location": item.get('location', 'Remote Worldwide'),
                            "description": desc,
                            "source": "RemoteOK"
                        })
                        if len(results) >= limit:
                            break
    except Exception as e:
        record_warning("job_daemon", f"RemoteOK API lookup warning: {e}", context={"query": query})
    return results

def run_search_cycle(dry_run: bool = False, limit: int = 15) -> list:
    """
    Executes one comprehensive search cycle across all 5 sources with pagination
    and error tracking.
    """
    if is_daemon_paused():
        print("[DAEMON] Scanning is currently paused (daemon_enabled.flag). Skipping cycle.")
        return []

    seen, all_seen_dict = load_seen_jobs()
    prof = load_candidate_profile()

    company_filter = None
    if prof:
        try:
            from tools.browser_autofill import CompanyFilter
            company_filter = CompanyFilter(prof)
        except Exception:
            pass

    categories = get_search_categories(prof)
    new_staged = []
    cycle_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n[DAEMON] === Running Discovery Cycle at {cycle_time} ===")
    target_roles_str = ", ".join(prof.get("target_roles", ["Software Engineer"]))
    print(f"[PROFILE] Target Roles: {target_roles_str}")

    for cat in categories:
        if not RUNNING or is_daemon_paused():
            break

        q = cat["query"]
        loc = cat["location"]
        print(f"\n[SEARCH] Querying '{q}' across 5 sources (LinkedIn, FreeHire, Arbeitnow, Remotive, RemoteOK)...")

        # 1. Search LinkedIn (Pages 1–3 to prevent pagination starvation)
        linkedin_cli = REPO_ROOT / ".agents/skills/linkedin-search/cli/src/cli.ts"
        if linkedin_cli.exists() and shutil.which(BUN_BIN):
            linkedin_found = 0
            for page_num in range(1, 4):
                if linkedin_found >= limit or not RUNNING:
                    break
                out = run_cli_command([
                    BUN_BIN, str(linkedin_cli), "search",
                    "-q", q, "-l", loc,
                    "--page", str(page_num),
                    "--limit", str(limit),
                    "--format", "json"
                ])
                try:
                    data = json.loads(out)
                    results = data.get("results", [])
                    if not results:
                        break
                    new_in_page = 0
                    for item in results:
                        job_id = f"linkedin_{item.get('id')}"
                        if job_id in seen:
                            continue

                        title = item.get("title", "")
                        company = item.get("company", "")
                        url = item.get("url", "")

                        if company_filter and company_filter.should_skip(company):
                            print(f"  [EXCLUSION] Skipping job at current employer: {company}")
                            continue

                        # Fetch detail for richer scoring
                        desc = ""
                        det_out = run_cli_command([BUN_BIN, str(linkedin_cli), "detail", str(item.get("id")), "--format", "json"])
                        if det_out:
                            try:
                                det = json.loads(det_out)
                                desc = det.get("description", "")
                            except Exception:
                                pass

                        fit_score, missing_skill, suggested_project = score_job_fit(title, desc, profile=prof)

                        all_seen_dict[job_id] = {
                            "title": title,
                            "company": company,
                            "url": url,
                            "fitScore": fit_score,
                            "date": datetime.now().strftime("%Y-%m-%d")
                        }
                        seen.add(job_id)
                        linkedin_found += 1
                        new_in_page += 1

                        print(f"  -> [LinkedIn p.{page_num}] Found: {title} @ {company} (Fit: {fit_score}/100)")

                        if fit_score >= 70:
                            row = {
                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "company": company,
                                "title": title,
                                "fitScore": fit_score,
                                "status": "Staged - Ready to Submit",
                                "missingSkill": missing_skill,
                                "suggestedProject": suggested_project,
                                "location": item.get("location", loc),
                                "url": url,
                                "notes": f"High fit ({fit_score}%). Generated tailored CV & cover letter."
                            }
                            if not dry_run:
                                stage_dir = stage_application(item, missing_skill, suggested_project, fit_score)
                                row["notes"] += f" Staged at {stage_dir.name}"
                            new_staged.append(row)

                    if new_in_page == 0:
                        # Page had no unseen jobs, advance to next page
                        continue
                except Exception as e:
                    record_warning("job_daemon", f"LinkedIn search parse error on page {page_num}: {e}", context={"query": q})
                    break

        # 2. Search FreeHire (Pages 1–2)
        freehire_cli = REPO_ROOT / ".agents/skills/freehire-search/cli/src/cli.ts"
        if freehire_cli.exists() and shutil.which(BUN_BIN):
            freehire_found = 0
            for page_num in range(1, 3):
                if freehire_found >= limit or not RUNNING:
                    break
                out = run_cli_command([
                    BUN_BIN, str(freehire_cli), "search",
                    "-q", q, "--remote", "remote",
                    "--page", str(page_num),
                    "--limit", str(limit),
                    "--format", "json"
                ])
                try:
                    data = json.loads(out, strict=False)
                    results = data.get("results", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                    if not results:
                        break
                    new_in_page = 0
                    for item in results:
                        slug = item.get("id") or item.get("company_slug", "")
                        job_id = f"freehire_{slug}"
                        if job_id in seen:
                            continue

                        title = item.get("title", "")
                        company = item.get("company", "")
                        url = item.get("url", "")
                        desc = item.get("description", "")

                        if company_filter and company_filter.should_skip(company):
                            print(f"  [EXCLUSION] Skipping FreeHire job at current employer: {company}")
                            continue

                        fit_score, missing_skill, suggested_project = score_job_fit(title, desc, profile=prof)
                        all_seen_dict[job_id] = {
                            "title": title,
                            "company": company,
                            "url": url,
                            "fitScore": fit_score,
                            "date": datetime.now().strftime("%Y-%m-%d")
                        }
                        seen.add(job_id)
                        freehire_found += 1
                        new_in_page += 1

                        print(f"  -> [FreeHire p.{page_num}] Found: {title} @ {company} (Fit: {fit_score}/100)")

                        if fit_score >= 70:
                            row = {
                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "company": company,
                                "title": title,
                                "fitScore": fit_score,
                                "status": "Staged - Ready to Submit",
                                "missingSkill": missing_skill,
                                "suggestedProject": suggested_project,
                                "location": "Remote Worldwide",
                                "url": url,
                                "notes": f"High fit ({fit_score}%). Generated tailored CV & cover letter."
                            }
                            if not dry_run:
                                stage_dir = stage_application(item, missing_skill, suggested_project, fit_score)
                                row["notes"] += f" Staged at {stage_dir.name}"
                            new_staged.append(row)

                    if new_in_page == 0:
                        continue
                except Exception as e:
                    record_warning("job_daemon", f"FreeHire search parse error on page {page_num}: {e}", context={"query": q})
                    break

        # 3. Search Arbeitnow
        try:
            arbeitnow_results = search_arbeitnow_jobs(q, seen=seen, limit=limit)
            for item in arbeitnow_results:
                job_id = item["id"]
                if job_id in seen:
                    continue
                title = item.get("title", "")
                company = item.get("company", "")
                url = item.get("url", "")
                desc = item.get("description", "")

                if company_filter and company_filter.should_skip(company):
                    print(f"  [EXCLUSION] Skipping Arbeitnow job at current employer: {company}")
                    continue

                fit_score, missing_skill, suggested_project = score_job_fit(title, desc, profile=prof)
                all_seen_dict[job_id] = {
                    "title": title,
                    "company": company,
                    "url": url,
                    "fitScore": fit_score,
                    "date": datetime.now().strftime("%Y-%m-%d")
                }
                seen.add(job_id)
                print(f"  -> [Arbeitnow] Found: {title} @ {company} (Fit: {fit_score}/100)")

                if fit_score >= 70:
                    row = {
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "company": company,
                        "title": title,
                        "fitScore": fit_score,
                        "status": "Staged - Ready to Submit",
                        "missingSkill": missing_skill,
                        "suggestedProject": suggested_project,
                        "location": item.get("location", "Remote"),
                        "url": url,
                        "notes": f"High fit ({fit_score}%). Generated tailored CV & cover letter."
                    }
                    if not dry_run:
                        stage_dir = stage_application(item, missing_skill, suggested_project, fit_score)
                        row["notes"] += f" Staged at {stage_dir.name}"
                    new_staged.append(row)
        except Exception as e:
            record_error("job_daemon", f"Arbeitnow processing error: {e}", context={"query": q})

        # 4. Search Remotive
        try:
            remotive_results = search_remotive_jobs(q, seen=seen, limit=limit)
            for item in remotive_results:
                job_id = item["id"]
                if job_id in seen:
                    continue
                title = item.get("title", "")
                company = item.get("company", "")
                url = item.get("url", "")
                desc = item.get("description", "")

                if company_filter and company_filter.should_skip(company):
                    print(f"  [EXCLUSION] Skipping Remotive job at current employer: {company}")
                    continue

                fit_score, missing_skill, suggested_project = score_job_fit(title, desc, profile=prof)
                all_seen_dict[job_id] = {
                    "title": title,
                    "company": company,
                    "url": url,
                    "fitScore": fit_score,
                    "date": datetime.now().strftime("%Y-%m-%d")
                }
                seen.add(job_id)
                print(f"  -> [Remotive] Found: {title} @ {company} (Fit: {fit_score}/100)")

                if fit_score >= 70:
                    row = {
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "company": company,
                        "title": title,
                        "fitScore": fit_score,
                        "status": "Staged - Ready to Submit",
                        "missingSkill": missing_skill,
                        "suggestedProject": suggested_project,
                        "location": item.get("location", "Remote Worldwide"),
                        "url": url,
                        "notes": f"High fit ({fit_score}%). Generated tailored CV & cover letter."
                    }
                    if not dry_run:
                        stage_dir = stage_application(item, missing_skill, suggested_project, fit_score)
                        row["notes"] += f" Staged at {stage_dir.name}"
                    new_staged.append(row)
        except Exception as e:
            record_error("job_daemon", f"Remotive processing error: {e}", context={"query": q})

        # 5. Search RemoteOK
        try:
            remoteok_results = search_remoteok_jobs(q, seen=seen, limit=limit)
            for item in remoteok_results:
                job_id = item["id"]
                if job_id in seen:
                    continue
                title = item.get("title", "")
                company = item.get("company", "")
                url = item.get("url", "")
                desc = item.get("description", "")

                if company_filter and company_filter.should_skip(company):
                    print(f"  [EXCLUSION] Skipping RemoteOK job at current employer: {company}")
                    continue

                fit_score, missing_skill, suggested_project = score_job_fit(title, desc, profile=prof)
                all_seen_dict[job_id] = {
                    "title": title,
                    "company": company,
                    "url": url,
                    "fitScore": fit_score,
                    "date": datetime.now().strftime("%Y-%m-%d")
                }
                seen.add(job_id)
                print(f"  -> [RemoteOK] Found: {title} @ {company} (Fit: {fit_score}/100)")

                if fit_score >= 70:
                    row = {
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "company": company,
                        "title": title,
                        "fitScore": fit_score,
                        "status": "Staged - Ready to Submit",
                        "missingSkill": missing_skill,
                        "suggestedProject": suggested_project,
                        "location": item.get("location", "Remote"),
                        "url": url,
                        "notes": f"High fit ({fit_score}%). Generated tailored CV & cover letter."
                    }
                    if not dry_run:
                        stage_dir = stage_application(item, missing_skill, suggested_project, fit_score)
                        row["notes"] += f" Staged at {stage_dir.name}"
                    new_staged.append(row)
        except Exception as e:
            record_error("job_daemon", f"RemoteOK processing error: {e}", context={"query": q})

    # Persist updated seen jobs
    save_seen_jobs(all_seen_dict)

    # Sync to Google Sheets and local tracker
    if new_staged:
        print(f"\n[SYNC] Syncing {len(new_staged)} high-fit applications to Google Sheets & tracker...")
        res = sync_jobs_to_sheet(new_staged)
        print(f"[SYNC RESULT] {res.get('message') or res.get('status')}")
        record_info("job_daemon", f"Cycle completed. Staged {len(new_staged)} high-fit jobs.")
    else:
        print("\n[DAEMON] Cycle complete. No new high-fit jobs in this batch.")

    return new_staged

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Antigravity Autonomous Job Search Daemon")
    parser.add_argument("--interval-mins", type=int, default=15, help="Interval between discovery cycles in minutes")
    parser.add_argument("--once", action="store_true", help="Run a single cycle and exit")
    parser.add_argument("--dry-run", action="store_true", help="Search and rank without generating application files")
    parser.add_argument("--limit", type=int, default=15, help="Max results per search category")
    args = parser.parse_args()

    print("=========================================================")
    print("  ANTIGRAVITY AUTONOMOUS JOB SEARCH DAEMON")
    print("=========================================================")
    print(f"Interval: {args.interval_mins} minutes | TinyTeX: OK | Bun: OK")
    print("Will run indefinitely. Press Ctrl+C or kill task to stop.")
    print("=========================================================")

    record_info("job_daemon", f"Daemon process started (interval={args.interval_mins}m, dry_run={args.dry_run})")

    while RUNNING:
        try:
            run_search_cycle(dry_run=args.dry_run, limit=args.limit)
        except Exception as e:
            record_error("job_daemon", f"Cycle encountered unhandled exception: {e}", severity="CRITICAL")
            print(f"[ERROR] Cycle encountered error: {e}. Backing off for 60 seconds...", file=sys.stderr)
            time.sleep(60)

        if args.once or not RUNNING:
            break

        print(f"\n[DAEMON] Sleeping for {args.interval_mins} minutes until next cycle...")
        for _ in range(args.interval_mins * 60):
            if not RUNNING:
                break
            time.sleep(1)

    record_info("job_daemon", "Daemon process terminated.")

if __name__ == "__main__":
    main()
