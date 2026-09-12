#!/usr/bin/env python3
"""Browser-based ATS form auto-filler with anti-detection and humanized actions."""

import asyncio
import argparse
import json
import re
import os
import sys
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from urllib.parse import urlparse, urlunparse

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Fallback imports for Playwright ecosystem
try:
    from camoufox.async_api import AsyncCamoufox as BrowserImpl
    BROWSER_TYPE = 'camoufox'
except ImportError:
    try:
        from patchright.async_api import async_playwright
        BROWSER_TYPE = 'patchright'
    except ImportError:
        try:
            from playwright.async_api import async_playwright
            BROWSER_TYPE = 'playwright'
        except ImportError:
            BROWSER_TYPE = 'none'

try:
    from tools.humanizer import HumanBehavior
except ImportError:
    class HumanBehavior:
        def __init__(self, page=None):
            self.page = page
        async def type_text(self, element, text: str):
            try:
                await element.fill(text)
            except Exception:
                pass
        async def human_type(self, element, text: str):
            await self.type_text(element, text)
        async def human_click(self, element):
            await element.click()
        async def random_delay(self, min_ms: int = 100, max_ms: int = 500):
            await asyncio.sleep((min_ms + max_ms) / 2000.0)

try:
    from tools.error_tracker import record_error, record_warning, record_info
except Exception:
    def record_error(*args, **kwargs): pass
    def record_warning(*args, **kwargs): pass
    def record_info(*args, **kwargs): pass

def update_tracker_job_status(job_url: str, new_status: str, notes_append: str = ""):
    """Updates job status in job_search_tracker.csv to prevent infinite reprocessing."""
    tracker_path = Path(__file__).parent.parent / "job_search_tracker.csv"
    if not tracker_path.exists():
        return
    try:
        import csv
        rows = []
        updated = False
        with open(tracker_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or ["timestamp", "company", "title", "fitScore", "status", "missingSkill", "suggestedProject", "location", "url", "notes"]
            for row in reader:
                if row.get("url") == job_url:
                    row["status"] = new_status
                    if notes_append:
                        old_notes = row.get("notes", "")
                        row["notes"] = f"{old_notes} | {notes_append}".strip(" |")
                    updated = True
                rows.append(row)
        if updated:
            with open(tracker_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(rows)
            logger.info(f"Updated tracker status to '{new_status}' for {job_url[:60]}...")
    except Exception as e:
        logger.error(f"Failed to update tracker status for {job_url}: {e}")
        record_warning("browser_autoapply", f"Tracker update failed: {e}")

class ATSDetector:
    """Detects which ATS platform a URL belongs to using regex patterns and domain heuristics."""
    def __init__(self):
        self.patterns = []
        selectors_path = Path(__file__).parent / "ats_selectors.json"
        if selectors_path.exists():
            try:
                with open(selectors_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    for p in raw.get("platforms", []):
                        name = p.get("platform_name", "").lower().strip()
                        pat = p.get("url_pattern", "")
                        if pat:
                            self.patterns.append((name, re.compile(pat, re.IGNORECASE)))
            except Exception as e:
                logger.warning(f"Error loading patterns from ats_selectors.json: {e}")

    def detect(self, url: str) -> str:
        """Returns normalized platform name or 'generic'."""
        if not url:
            return "generic"
        for name, pattern in self.patterns:
            if pattern.search(url):
                if "easy apply" in name:
                    return "linkedin"
                return name
        url_lower = url.lower()
        if "greenhouse" in url_lower: return "greenhouse"
        if "lever.co" in url_lower: return "lever"
        if "ashbyhq" in url_lower: return "ashby"
        if "workday" in url_lower: return "workday"
        if "smartrecruiters" in url_lower: return "smartrecruiters"
        if "applytojob" in url_lower or "jazzhr" in url_lower: return "jazzhr"
        if "linkedin.com" in url_lower: return "linkedin"
        if "indeed.com" in url_lower: return "indeed"
        if "naukri.com" in url_lower: return "naukri"
        if "djinni.co" in url_lower: return "djinni"
        if "remoteok.com" in url_lower: return "remoteok"
        if "arbeitnow.com" in url_lower: return "arbeitnow"
        if "himalayas.app" in url_lower: return "himalayas"
        return "generic"

class CompanyFilter:
    """Filters out job postings from the user's current company."""
    def __init__(self, candidate_profile: dict):
        self.current_company = candidate_profile.get('current_company', '').lower()
    
    def should_skip(self, company_name: str) -> bool:
        """Returns True if this job is from the user's current company."""
        if not self.current_company or not company_name:
            return False
        clean_curr = self.current_company.strip().lower()
        clean_target = company_name.strip().lower()
        return clean_curr in clean_target or clean_target in clean_curr

class FormFiller:
    """Fills a form on any detected ATS platform with robust canonical selectors and fallbacks."""
    
    def __init__(self, page, platform: str, candidate: dict, humanizer: HumanBehavior):
        self.page = page
        self.platform = platform.lower().strip()
        self.candidate = candidate
        self.humanizer = humanizer
        self.selectors = self._load_selectors()
        
    def _load_selectors(self) -> dict:
        selectors_path = Path(__file__).parent / "ats_selectors.json"
        platforms_map = {}
        if selectors_path.exists():
            try:
                with open(selectors_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    for p in raw.get("platforms", []):
                        pname = p.get("platform_name", "").lower().strip()
                        platforms_map[pname] = p.get("selectors", {})
                    platforms_map["fallback_regex"] = raw.get("fallback_regex", {})
            except Exception as e:
                logger.warning(f"Error loading selectors from ats_selectors.json: {e}")

        # Aliases
        if "linkedin easy apply" in platforms_map and "linkedin" not in platforms_map:
            platforms_map["linkedin"] = platforms_map["linkedin easy apply"]

        # Default JazzHR / Resumator selectors if missing
        if "jazzhr" not in platforms_map:
            platforms_map["jazzhr"] = {
                "first_name": "#first_name, input[name='first_name']",
                "last_name": "#last_name, input[name='last_name']",
                "full_name": None,
                "email": "#email, input[name='email']",
                "phone": "#phone, input[name='phone']",
                "resume_upload": "input[type='file'][name*='resume'], #resumator-choose-resume",
                "cover_letter_upload": "input[type='file'][name*='cover']",
                "cover_letter_text": "textarea[name*='cover']",
                "linkedin_url": "input[id*='linkedin'], input[name*='linkedin']",
                "github_url": "input[id*='github'], input[name*='github']",
                "portfolio_url": "input[id*='portfolio'], input[name*='portfolio']",
                "current_company": "input[id*='company']",
                "current_title": "input[id*='title']",
                "location": "input[id*='location']",
                "submit_button": "#btn_submit, button[type='submit'], input[type='submit']",
                "next_button": None
            }

        return platforms_map

    async def _safe_fill(self, selector: str, value: str, field_name: str) -> bool:
        """Safely types value into selector with fallback query and human delay."""
        if not value or not selector:
            return False
        try:
            element = await self.page.query_selector(selector)
            if element:
                is_visible = await element.is_visible()
                if not is_visible:
                    return False
                current_val = await element.input_value() if hasattr(element, "input_value") else ""
                if current_val and current_val.strip() == str(value).strip():
                    return True  # Already filled
                await self.humanizer.type_text(element, str(value))
                logger.info(f"   ✓ Filled {field_name}: {value}")
                await self.humanizer.random_delay(150, 350)
                return True
        except Exception as e:
            logger.debug(f"Could not fill {field_name} using {selector}: {e}")
        return False

    async def _fill_standard_fields(self):
        """Fill first name, last name, email, phone, title, company, location."""
        plat_sel = self.selectors.get(self.platform, {})
        first = self.candidate.get("first_name", "")
        last = self.candidate.get("last_name", "")
        full = self.candidate.get("full_name") or f"{first} {last}".strip()
        email = self.candidate.get("email", "")
        phone = self.candidate.get("phone", "")
        company = self.candidate.get("current_company", "")
        title = self.candidate.get("current_title", "")
        location = self.candidate.get("location") or self.candidate.get("city", "")

        # Try Full Name first if platform prefers it (e.g. Lever)
        full_name_sel = plat_sel.get("full_name")
        if full_name_sel:
            await self._safe_fill(full_name_sel, full, "full_name")
        else:
            if not await self._safe_fill(plat_sel.get("first_name"), first, "first_name"):
                await self._safe_fill("input[name='name' i], input[id='name' i]", full, "full_name")

        if plat_sel.get("first_name"):
            await self._safe_fill(plat_sel.get("first_name"), first, "first_name")
        else:
            await self._safe_fill("input[name*='first' i], input[id*='first' i], [aria-label*='First Name' i]", first, "first_name")

        if plat_sel.get("last_name"):
            await self._safe_fill(plat_sel.get("last_name"), last, "last_name")
        else:
            await self._safe_fill("input[name*='last' i], input[id*='last' i], [aria-label*='Last Name' i]", last, "last_name")

        # Email
        email_sel = plat_sel.get("email") or "input[name*='email' i], input[type='email'], input[id*='email' i], [aria-label*='Email' i]"
        await self._safe_fill(email_sel, email, "email")

        # Phone
        phone_sel = plat_sel.get("phone") or "input[name*='phone' i], input[type='tel'], input[id*='phone' i], [aria-label*='Phone' i]"
        await self._safe_fill(phone_sel, phone, "phone")

        # Current Company
        comp_sel = plat_sel.get("current_company") or "input[name*='company' i], input[name*='org' i], input[id*='company' i]"
        await self._safe_fill(comp_sel, company, "current_company")

        # Current Title
        title_sel = plat_sel.get("current_title") or "input[name*='title' i], input[id*='title' i], input[name*='headline' i]"
        await self._safe_fill(title_sel, title, "current_title")

        # Location / City
        loc_sel = plat_sel.get("location") or "input[name*='location' i], input[id*='location' i], input[name*='city' i]"
        await self._safe_fill(loc_sel, location, "location")

    async def _fill_url_fields(self):
        """Fill LinkedIn, GitHub, portfolio URLs."""
        plat_sel = self.selectors.get(self.platform, {})
        linkedin = self.candidate.get("linkedin_url", "")
        github = self.candidate.get("github_url", "")
        portfolio = self.candidate.get("portfolio_url", "")

        linkedin_sel = plat_sel.get("linkedin_url") or plat_sel.get("linkedin") or "input[name*='linkedin' i], input[id*='linkedin' i], [aria-label*='LinkedIn' i]"
        await self._safe_fill(linkedin_sel, linkedin, "linkedin_url")

        github_sel = plat_sel.get("github_url") or plat_sel.get("github") or "input[name*='github' i], input[id*='github' i], [aria-label*='GitHub' i]"
        await self._safe_fill(github_sel, github, "github_url")

        portfolio_sel = plat_sel.get("portfolio_url") or plat_sel.get("portfolio") or "input[name*='portfolio' i], input[name*='website' i], input[id*='portfolio' i]"
        await self._safe_fill(portfolio_sel, portfolio, "portfolio_url")

    async def _upload_file(self, selector: str, file_path: str, field_name: str) -> bool:
        if not file_path:
            return False
        path = Path(file_path).resolve()
        if not path.exists():
            logger.warning(f"File for {field_name} does not exist at: {path}")
            return False

        try:
            file_input = await self.page.query_selector(selector)
            if file_input:
                await file_input.set_input_files(str(path))
                logger.info(f"   📎 Uploaded {field_name}: {path.name}")
                await self.humanizer.random_delay(400, 800)
                return True
            else:
                generic_input = await self.page.query_selector("input[type='file']")
                if generic_input:
                    await generic_input.set_input_files(str(path))
                    logger.info(f"   📎 Uploaded {field_name} via generic file input: {path.name}")
                    return True
        except Exception as e:
            logger.warning(f"Could not upload {field_name}: {e}")
        return False

    async def _upload_resume(self):
        """Upload resume PDF."""
        plat_sel = self.selectors.get(self.platform, {})
        selector = (
            plat_sel.get("resume_upload") or 
            plat_sel.get("resume") or 
            "input[type='file'][name*='resume' i], input[type='file'][id*='resume' i], input[type='file'][accept*='pdf' i], input[type='file']"
        )
        resume_path = self.candidate.get("resume_pdf_path", "cv/main_example.pdf")
        await self._upload_file(selector, resume_path, "resume")

    async def _upload_cover_letter(self):
        """Upload cover letter PDF or fill cover letter text if field exists."""
        plat_sel = self.selectors.get(self.platform, {})
        cover_path = self.candidate.get("cover_letter_pdf_path", "cover_letters/cover_example.pdf")
        file_sel = (
            plat_sel.get("cover_letter_upload") or 
            plat_sel.get("cover_letter") or 
            "input[type='file'][name*='cover' i], input[type='file'][id*='cover' i]"
        )
        uploaded = await self._upload_file(file_sel, cover_path, "cover_letter")

        if not uploaded:
            text_sel = (
                plat_sel.get("cover_letter_text") or 
                "textarea[name*='cover' i], textarea[id*='cover' i], textarea[name*='comment' i], textarea[placeholder*='cover letter' i]"
            )
            try:
                area = await self.page.query_selector(text_sel)
                if area and await area.is_visible():
                    pitch = f"Hello, I am {self.candidate.get('full_name')}, an {self.candidate.get('current_title', 'Engineer')} with 5+ YOE. Please review my attached credentials."
                    await self.humanizer.type_text(area, pitch)
                    logger.info("   ✓ Filled cover letter text note")
            except Exception:
                pass

    async def _handle_custom_questions(self):
        """Fill common screening questions (salary, sponsorship, authorization, gender, etc.)."""
        try:
            inputs = await self.page.query_selector_all("input[type='text'], textarea")
            for el in inputs:
                if not await el.is_visible():
                    continue
                current_val = await el.input_value()
                if current_val:
                    continue  # Already has a value

                name = (await el.get_attribute("name") or "").lower()
                id_ = (await el.get_attribute("id") or "").lower()
                aria = (await el.get_attribute("aria-label") or "").lower()
                combined = f"{name} {id_} {aria}"

                if any(w in combined for w in ["salary", "compensation", "rate", "expected_salary"]):
                    await self.humanizer.type_text(el, "Negotiable")
                    logger.info("   ✓ Filled compensation screening: 'Negotiable'")
                elif any(w in combined for w in ["sponsor", "visa"]):
                    val = "Yes" if self.candidate.get("work_authorization", {}).get("requires_sponsorship") else "No"
                    await self.humanizer.type_text(el, val)
                    logger.info(f"   ✓ Filled visa sponsorship question: '{val}'")
                elif any(w in combined for w in ["authorized", "authorization", "legally"]):
                    await self.humanizer.type_text(el, "Yes")
                    logger.info("   ✓ Filled work authorization question: 'Yes'")
                elif any(w in combined for w in ["experience", "years"]):
                    years = str(self.candidate.get("years_experience", 5))
                    await self.humanizer.type_text(el, years)
                    logger.info(f"   ✓ Filled years of experience: '{years}'")
        except Exception as e:
            logger.debug(f"Custom question handling note: {e}")

    async def fill_form(self) -> bool:
        """Main entry point. Detects all form fields and fills them."""
        logger.info(f"📋 Starting form fill for detected ATS: [{self.platform.upper()}]")
        await self._fill_standard_fields()
        await self._fill_url_fields()
        await self._upload_resume()
        await self._upload_cover_letter()
        await self._handle_custom_questions()
        return True

    async def advance_wizard_step(self) -> bool:
        """Clicks 'Next' / 'Continue' / 'Review' button in multi-step forms (e.g. Workday, Easy Apply)."""
        plat_sel = self.selectors.get(self.platform, {})
        next_sel = (
            plat_sel.get("next_button") or 
            "button:has-text('Next'), button:has-text('Continue'), button:has-text('Review'), button[aria-label*='Next' i], button[aria-label*='Continue' i]"
        )
        try:
            btn = await self.page.query_selector(next_sel)
            if btn and await btn.is_visible() and await btn.is_enabled():
                logger.info("   ⏩ Multi-step wizard: Advancing to next step...")
                await btn.click()
                await self.page.wait_for_load_state("domcontentloaded", timeout=7000)
                await asyncio.sleep(2)
                return True
        except Exception as e:
            logger.debug(f"No further wizard steps: {e}")
        return False

class AutoApplier:
    """Orchestrates anti-detect browser launching, ATS navigation, form-filling, and review lifecycle."""
    
    def __init__(self, mode='semi-auto', browser_type=BROWSER_TYPE, profile_dir='~/.job-autoapply-profile'):
        self.mode = mode
        self.browser_type = browser_type if browser_type in ['playwright', 'camoufox', 'patchright'] else 'playwright'
        self.profile_dir = Path(profile_dir).expanduser().resolve()
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.detector = ATSDetector()

    async def _resolve_application_page(self, page, initial_url: str) -> Tuple[Any, str]:
        """
        Unwraps portal & aggregator pages (LinkedIn, RemoteOK, Lever description, Djinni)
        to navigate into the actual application form.
        Returns (active_page, detected_platform).
        """
        logger.info(f"🌐 Navigating to: {initial_url}")
        try:
            await page.goto(initial_url, wait_until="domcontentloaded", timeout=25000)
        except Exception as e:
            logger.warning(f"Initial page navigation note: {e}. Retrying with load...")
            await asyncio.sleep(2)

        current_url = page.url
        
        # Cloudflare / Bot challenge detection
        try:
            cf_challenge = await page.query_selector("iframe[src*='challenges.cloudflare.com'], #challenge-stage, div:has-text('Performing security verification')")
            if cf_challenge:
                logger.warning("🛡️ Security verification challenge detected. Waiting up to 15s for verification...")
                for _ in range(15):
                    if page.is_closed(): break
                    still_cf = await page.query_selector("iframe[src*='challenges.cloudflare.com'], #challenge-stage")
                    if not still_cf:
                        logger.info("   ✅ Security challenge resolved!")
                        await asyncio.sleep(2)
                        break
                    await asyncio.sleep(1)
                current_url = page.url
        except Exception:
            pass

        platform = self.detector.detect(current_url)

        # 1. Lever Job Posting -> Click 'Apply for this job' or navigate to /apply
        if "lever.co" in current_url.lower() and "/apply" not in current_url.lower():
            try:
                apply_btn = await page.query_selector("a.postings-btn, a[href*='/apply'], a:has-text('APPLY FOR THIS JOB'), a:has-text('Apply for this job')")
                if apply_btn and await apply_btn.is_visible():
                    logger.info("   -> Lever description detected: Clicking 'Apply for this job'...")
                    await apply_btn.click()
                    await asyncio.sleep(3)
                else:
                    parsed = urlparse(current_url)
                    path = parsed.path.rstrip('/')
                    if not path.endswith('/apply'):
                        path = f"{path}/apply"
                    apply_url = urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment))
                    logger.info(f"   -> Lever navigating directly to: {apply_url}")
                    await page.goto(apply_url, wait_until="domcontentloaded", timeout=20000)
                platform = "lever"
            except Exception as e:
                logger.debug(f"Lever unwrap exception: {e}")

        # 2. LinkedIn Job Posting -> Check for Login Wall or Easy Apply or Offsite Apply
        elif "linkedin.com" in current_url.lower():
            login_form = await page.query_selector("input[name='session_key'], input[id='username'], form.login__form")
            sign_in_btn = await page.query_selector("button:has-text('Sign in to apply'), a:has-text('Sign in')")
            
            if login_form or sign_in_btn:
                logger.warning("🔒 [LINKEDIN LOGIN REQUIRED] LinkedIn requires an active session to apply.")
                if self.mode == 'semi-auto':
                    logger.info("   💡 Please log into LinkedIn in the browser window now.")
                    logger.info("   Your login session and cookies will be saved in ~/.job-autoapply-profile.")
                    logger.info("   Waiting up to 45s for sign-in...")
                    for _ in range(45):
                        if page.is_closed():
                            break
                        logged_in = await page.query_selector("nav.global-nav, img.global-nav__me-photo, button.jobs-apply-button")
                        if logged_in:
                            logger.info("   ✅ Logged in to LinkedIn successfully!")
                            break
                        await asyncio.sleep(1)

            # Check if external redirect apply button exists (e.g. "Apply on company website")
            try:
                ext_apply = await page.query_selector("a[data-tracking-control-name*='apply'], a.apply-button, a:has-text('Apply on company website')")
                if ext_apply:
                    href = await ext_apply.get_attribute("href")
                    if href and href.startswith("http") and "linkedin.com/login" not in href:
                        logger.info(f"   -> LinkedIn offsite application redirect found: {href[:60]}...")
                        await page.goto(href, wait_until="domcontentloaded", timeout=20000)
                        return page, self.detector.detect(page.url)
            except Exception as e:
                logger.debug(f"LinkedIn external apply check note: {e}")

            try:
                easy_apply_btn = await page.query_selector("button.jobs-apply-button, button.apply-button, button:has-text('Easy Apply')")
                if easy_apply_btn and await easy_apply_btn.is_visible():
                    logger.info("   -> LinkedIn Easy Apply button detected: Opening application modal...")
                    await easy_apply_btn.click()
                    await asyncio.sleep(2)
                    platform = "linkedin"
                elif login_form or sign_in_btn:
                    logger.warning("   ⚠️ LinkedIn session not active and no public form accessible.")
                    return page, "needs_login"
            except Exception as e:
                logger.debug(f"LinkedIn apply click note: {e}")

        # 3. Aggregators (RemoteOK, Arbeitnow, Djinni, Himalayas) -> Follow external apply link
        elif any(agg in current_url.lower() for agg in ["remoteok.com", "arbeitnow.com", "djinni.co", "himalayas.app"]):
            try:
                ext_btn = await page.query_selector("a.apply, a:has-text('Apply for this job'), a:has-text('Apply Now'), a:has-text('Apply on company website'), a[href*='utm_source']")
                if ext_btn:
                    href = await ext_btn.get_attribute("href")
                    if href and href.startswith("http") and not any(p in href for p in ["remoteok.com/l/", "arbeitnow.com/jobs"]):
                        logger.info(f"   -> Aggregator redirecting to direct application page: {href[:60]}...")
                        await page.goto(href, wait_until="domcontentloaded", timeout=20000)
                        platform = self.detector.detect(page.url)
            except Exception as e:
                logger.debug(f"Aggregator follow exception: {e}")

        logger.info(f"🎯 Resolved Application Target: [{platform.upper()}] at {page.url[:80]}")
        return page, platform

    async def _process_page(self, page, application_url: str, resume_path: str, cover_letter_path: Optional[str], dry_run: bool, candidate: dict) -> Dict[str, Any]:
        """Performs form resolution, data mapping, screenshot capture, and submission handling."""
        page, platform = await self._resolve_application_page(page, application_url)
        if platform == "needs_login":
            return {"status": "needs_login", "platform": "linkedin", "message": "Sign-in required to access application"}

        # Check if posting has expired or closed
        closed_keywords = [
            "position is no longer available",
            "job has expired",
            "job posting has expired",
            "no longer accepting applications",
            "job is closed",
            "posting is closed",
            "position has been filled"
        ]
        try:
            body_text = await page.inner_text("body")
            body_lower = body_text.lower()
            for kw in closed_keywords:
                if kw in body_lower:
                    logger.warning(f"🛑 Posting is closed: '{kw}' detected on page.")
                    screenshot_dir = Path("documents/applications/latest")
                    screenshot_dir.mkdir(parents=True, exist_ok=True)
                    try:
                        await page.screenshot(path=str(screenshot_dir / "screenshot.png"), full_page=False)
                    except Exception:
                        pass
                    return {"status": "closed", "platform": platform, "reason": f"Position closed: {kw}"}
        except Exception as e:
            logger.debug(f"Closed check note: {e}")

        candidate["resume_pdf_path"] = resume_path
        if cover_letter_path:
            candidate["cover_letter_pdf_path"] = cover_letter_path

        humanizer = HumanBehavior(page)
        filler = FormFiller(page, platform, candidate, humanizer)

        # Fill Step 1
        await filler.fill_form()

        # Handle multi-step wizard if present (e.g. Workday, Easy Apply)
        steps_navigated = 0
        while steps_navigated < 4:
            advanced = await filler.advance_wizard_step()
            if not advanced:
                break
            steps_navigated += 1
            await filler.fill_form()

        # Save Screenshot of pre-filled form
        screenshot_dir = Path("documents/applications/latest")
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = screenshot_dir / "screenshot.png"
        try:
            await page.screenshot(path=str(screenshot_path), full_page=False)
            logger.info(f"📸 Verification screenshot saved: {screenshot_path}")
        except Exception as e:
            logger.debug(f"Screenshot capture note: {e}")

        plat_sel = filler.selectors.get(platform, {})
        submit_selector = (
            plat_sel.get("submit_button") or 
            plat_sel.get("submit") or 
            "button[type='submit'], input[type='submit'], button:has-text('Submit Application'), button:has-text('Submit'), button:has-text('Apply Now')"
        )

        if dry_run:
            logger.info("🧪 [DRY RUN] Inspection mode: Form fields successfully filled.")
            logger.info("   Keeping browser window open for 30 seconds so you can inspect the filled fields...")
            try:
                for _ in range(30):
                    if page.is_closed(): break
                    await asyncio.sleep(1)
            except Exception: pass
            return {"status": "success", "mode": "dry-run", "platform": platform}

        if self.mode == 'semi-auto':
            logger.info("👀 [SEMI-AUTO REVIEW] Form successfully pre-filled with candidate data!")
            logger.info("   Browser window will stay open for 75 seconds for your verification.")
            logger.info("   You can review all fields on screen or manually click Submit at your discretion.")
            try:
                for _ in range(75):
                    if page.is_closed():
                        logger.info("Browser window closed by user.")
                        break
                    await asyncio.sleep(1)
            except Exception:
                pass
            return {"status": "success", "mode": "semi-auto", "platform": platform}

        elif self.mode == 'full-auto':
            logger.info("🤖 [FULL AUTO] Automated submission requested. Waiting 5s before submitting...")
            await asyncio.sleep(5)
            try:
                submit_btn = await page.query_selector(submit_selector)
                if submit_btn and await submit_btn.is_visible():
                    await submit_btn.click()
                    logger.info("✅ Application submit clicked!")
                    await asyncio.sleep(5)
                    return {"status": "success", "mode": "full-auto", "platform": platform}
                else:
                    logger.warning("Submit button not found or hidden. Flagged for review.")
                    return {"status": "review_needed", "platform": platform, "error": "Submit button not found"}
            except Exception as e:
                logger.error(f"Error submitting form: {e}")
                return {"status": "failed", "platform": platform, "error": str(e)}

        return {"status": "success", "platform": platform}

    async def apply(self, application_url: str, resume_path: str = "cv/main_example.pdf", cover_letter_path: str = None, dry_run: bool = False) -> Dict[str, Any]:
        """Executes application for a single URL with persistent profile context."""
        logger.info(f"🚀 Launching anti-detect browser application: {application_url}")

        profile_path = Path(__file__).parent / "candidate_profile.json"
        if not profile_path.exists():
            record_error("browser_autoapply", "Candidate profile candidate_profile.json not found!")
            return {"status": "failed", "error": "Profile missing"}

        with open(profile_path, "r", encoding="utf-8") as f:
            candidate = json.load(f)

        filter_obj = CompanyFilter(candidate)
        for word in application_url.split("/"):
            if filter_obj.should_skip(word):
                logger.warning(f"Skipping application: matches current company '{candidate.get('current_company')}'")
                return {"status": "skipped", "reason": "Current company exclusion"}

        if BROWSER_TYPE == 'none':
            platform = self.detector.detect(application_url)
            logger.warning("⚠️ Neither Camoufox nor Playwright installed. Running in simulation mode.")
            logger.info(f"   Install command: python3 -m pip install playwright && python3 -m playwright install chromium")
            return {"status": "simulated", "platform": platform}

        try:
            if self.browser_type == 'camoufox' and BROWSER_TYPE == 'camoufox':
                async with BrowserImpl(user_data_dir=str(self.profile_dir), headless=False) as browser:
                    page = await browser.new_page()
                    res = await self._process_page(page, application_url, resume_path, cover_letter_path, dry_run, candidate)
                    return res
            else:
                async with async_playwright() as p:
                    browser = await p.chromium.launch_persistent_context(
                        user_data_dir=str(self.profile_dir),
                        headless=False,
                        args=[
                            '--disable-blink-features=AutomationControlled',
                            '--start-maximized',
                            '--no-default-browser-check'
                        ]
                    )
                    page = browser.pages[0] if browser.pages else await browser.new_page()
                    try:
                        res = await self._process_page(page, application_url, resume_path, cover_letter_path, dry_run, candidate)
                        return res
                    finally:
                        try:
                            await browser.close()
                        except Exception:
                            pass
        except Exception as e:
            logger.error(f"Application flow exception: {e}", exc_info=True)
            record_error("browser_autoapply", f"Application exception on {application_url[:60]}: {e}", context={"url": application_url})
            return {"status": "failed", "error": str(e)}

async def run_autofill_daemon(mode='semi-auto', browser_type=None, profile_dir='~/.job-autoapply-profile', dry_run=False):
    """Continuous supervisor daemon that iterates over ready-to-submit opportunities in job_search_tracker.csv."""
    if browser_type is None:
        browser_type = BROWSER_TYPE if BROWSER_TYPE != 'none' else 'playwright'
    logger.info("🤖 Browser Auto-Apply Daemon started.")
    logger.info(f"   Mode: {mode} | Active Engine: {browser_type} | Profile: {profile_dir}")
    
    tracker_path = Path(__file__).parent.parent / "job_search_tracker.csv"
    applier = AutoApplier(mode=mode, browser_type=browser_type, profile_dir=profile_dir)

    while True:
        staged_job = None
        if tracker_path.exists():
            try:
                import csv
                with open(tracker_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        st = (row.get('status') or '').strip().lower()
                        url = (row.get('url') or '').strip()
                        # Strictly match jobs ready for automated processing (prevents infinite loop on reviewed/failed jobs)
                        if st in ['staged', 'staged - ready to submit'] and url.startswith('http') and not url.endswith('/jobs/test'):
                            staged_job = row
                            break
            except Exception as e:
                logger.error(f"Error reading tracker CSV: {e}")

        if staged_job:
            job_url = staged_job.get('url', '')
            company = staged_job.get('company', 'Unknown')
            title = staged_job.get('title', 'Unknown')
            logger.info(f"\n=======================================================")
            logger.info(f"🎯 Found staged opportunity: {company} — {title}")
            logger.info(f"   URL: {job_url}")
            logger.info(f"=======================================================")
            
            try:
                res = await applier.apply(job_url, 'cv/main_example.pdf', dry_run=dry_run)
                res_status = res.get("status") if isinstance(res, dict) else "unknown"

                if res_status == "success":
                    new_st = "Applied - Submitted" if mode == "full-auto" else "Applied - Semi-Auto Reviewed"
                    update_tracker_job_status(job_url, new_st, f"Auto-applied ({mode})")
                    record_info("browser_autoapply", f"Application completed for {company} ({new_st})")
                elif res_status == "simulated":
                    update_tracker_job_status(job_url, "Applied - Simulated", "Simulated form mapping completed")
                    record_info("browser_autoapply", f"Simulated form mapping for {company}")
                elif res_status == "needs_login":
                    update_tracker_job_status(job_url, "Needs Login - Manual Review", "Platform requires account sign-in")
                    record_warning("browser_autoapply", f"Login required for {company} on {res.get('platform')}", context={"url": job_url})
                elif res_status == "closed":
                    update_tracker_job_status(job_url, "Closed - Position Expired", res.get("reason", "Position closed by employer"))
                    record_info("browser_autoapply", f"Position expired/closed for {company}: {res.get('reason')}")
                else:
                    err_msg = res.get("error", "Check form manually") if isinstance(res, dict) else "Review needed"
                    update_tracker_job_status(job_url, "Manual Review Required", f"Review: {err_msg[:60]}")
                    record_warning("browser_autoapply", f"Application incomplete: {err_msg}", context={"url": job_url})
            except Exception as e:
                logger.error(f"Error during application cycle: {e}")
                record_error("browser_autoapply", f"Application exception: {e}", context={"url": job_url})
                update_tracker_job_status(job_url, "Application Failed", f"Exception: {str(e)[:60]}")

            logger.info("Application pass finished. Pausing 15s before inspecting next opportunity...")
            await asyncio.sleep(15)
        else:
            logger.info("Standing by: No pending opportunities with status 'Staged - Ready to Submit'. Checking again in 30s...")
            await asyncio.sleep(30)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Auto-fill job application forms')
    parser.add_argument('url', nargs='?', default=None, help='Application URL (if omitted, runs continuous auto-apply daemon)')
    parser.add_argument('--resume', default='cv/main_example.pdf', help='Path to resume PDF')
    parser.add_argument('--cover-letter', help='Path to cover letter PDF')
    parser.add_argument('--mode', choices=['semi-auto', 'full-auto'], default='semi-auto')
    default_b = BROWSER_TYPE if BROWSER_TYPE != 'none' else 'playwright'
    parser.add_argument('--browser', choices=['camoufox', 'patchright', 'playwright'], default=default_b)
    parser.add_argument('--dry-run', action='store_true', help='Fill form but never submit')
    parser.add_argument('--profile-dir', default='~/.job-autoapply-profile', help='Persistent browser profile dir')
    args = parser.parse_args()

    if args.url:
        applier = AutoApplier(mode=args.mode, browser_type=args.browser, profile_dir=args.profile_dir)
        asyncio.run(applier.apply(args.url, args.resume, args.cover_letter, args.dry_run))
    else:
        asyncio.run(run_autofill_daemon(mode=args.mode, browser_type=args.browser, profile_dir=args.profile_dir, dry_run=args.dry_run))
