---
name: ai-job-search
description: >-
  Automate job searching, posting evaluation, CV tailoring, cover letter writing,
  interview preparation, and skill-gap upskilling with proof-of-concept project recommendations.
  Use when the user wants to search for jobs, scrape job postings, evaluate fit for a job URL or description,
  tailor their resume/cover letter, or identify missing skills and 1-2 hour demo projects.
---

# AI Job Search Automation

This skill automates the end-to-end job application and search lifecycle for **Maruf Hassan**.

## Candidate Single Source of Truth
- Baseline profile: `CLAUDE.md` and `.agents/skills/job-application-assistant/01-candidate-profile.md`
- Baseline CV: `cv/main_example.tex`
- Search queries: `.agents/skills/job-scraper/search-queries.md`

## Available Workflows

### 1. Scrape & Discover Jobs (`/scrape`)
Searches job portals (LinkedIn via `linkedin-search`, FreeHire via `freehire-search`, and web search fallback) using queries defined in `search-queries.md`.
- Filters by remote availability, locations (Worldwide, Remote India, Kolkata), and recency (last 14 days).
- Surfaces matches with a quick fit rating.

### 2. Rank Shortlist (`/rank`)
Batch-scores scraped jobs across the 5 evaluation dimensions:
- Technical Skills Match (0-100)
- Experience Match (0-100)
- Behavioral / Culture Fit (0-100)
- Location & Logistics (Pass/Fail)
- Career Alignment & Motivation (0-100)

### 3. Apply to a Role (`/apply <url or description>`)
Given a job URL or pasted posting text:
1. **Fit Evaluation**: Thoroughly score against Maruf's profile.
2. **Skill Gap & Project Hook**: If any high-demand skill is missing, highlight it and propose a **1–2 hour proof-of-concept project** (with video/screenshot demo instructions) to prove competence to the recruiter.
3. **Draft CV**: Create tailored 2-page ModernCV in `cv/main_<company>_<role>.tex`.
4. **Draft Cover Letter**: Create tailored 1-page cover letter in `cover_letters/cover_<company>_<role>.tex`.
5. **ATS Verification**: Run `python3 tools/verify_pdf.py` if PDFs are compiled, or check extracted text keyword alignment.

### 4. Skill Gap Upskilling (`/upskill`)
Analyzes target job postings to detect recurring missing skills and designs rapid 1-2 hour mini-projects that showcase hands-on mastery.

### 5. Interview Prep (`/interview`)
Generates role-specific questions and maps them to Maruf's real STAR stories:
- **Floor Boss**: Slack DM AI assistant, Gemini LLM, API consolidation, prompt caching, 70% reporting reduction.
- **ELSA Speak**: 100M+ scale, Flutter 3 migration, multi-provider auth, 30% retention increase.
- **SuperBrains / HLP**: Golden Dutch Interactive Award winner, healthcare UX, gamified flows.
- **Nyburs**: Hyperlocal Indian platform, Reels-style video feed, Riverpod, custom animations.
