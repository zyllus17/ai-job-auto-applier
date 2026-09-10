#!/usr/bin/env python3
"""Browser-based ATS form auto-filler with anti-detection."""

import asyncio
import argparse
import json
import re
import logging
from pathlib import Path
from typing import Optional, Dict, Any

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
    # Minimal mock if humanizer isn't available yet
    class HumanBehavior:
        async def type_text(self, element, text: str):
            await element.fill(text)
        async def random_delay(self, min_ms: int = 100, max_ms: int = 500):
            await asyncio.sleep((min_ms + max_ms) / 2000.0)

class ATSDetector:
    """Detects which ATS platform a URL belongs to using regex patterns."""
    def __init__(self):
        self.patterns = []
        selectors_path = Path(__file__).parent / "ats_selectors.json"
        if selectors_path.exists():
            try:
                with open(selectors_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    for p in raw.get("platforms", []):
                        name = p.get("platform_name", "").lower()
                        pat = p.get("url_pattern", "")
                        if pat:
                            self.patterns.append((name, re.compile(pat, re.IGNORECASE)))
            except Exception as e:
                logger.warning(f"Error loading patterns from ats_selectors.json: {e}")

    def detect(self, url: str) -> str:
        """Returns platform name or 'unknown'."""
        for name, pattern in self.patterns:
            if pattern.search(url):
                return name
        url_lower = url.lower()
        for known in ["greenhouse", "lever", "ashby", "workday", "smartrecruiters", "linkedin", "indeed", "naukri", "monster"]:
            if known in url_lower:
                return known
        return "unknown"

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
    """Fills a form on any detected ATS platform."""
    
    def __init__(self, page, platform: str, candidate: dict, humanizer: HumanBehavior):
        self.page = page
        self.platform = platform.lower()
        self.candidate = candidate
        self.humanizer = humanizer
        self.selectors = self._load_selectors()
        
    def _load_selectors(self) -> dict:
        selectors_path = Path(__file__).parent / "ats_selectors.json"
        if selectors_path.exists():
            try:
                with open(selectors_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    platforms_map = {}
                    for p in raw.get("platforms", []):
                        pname = p.get("platform_name", "").lower()
                        platforms_map[pname] = p.get("selectors", {})
                    platforms_map["fallback_regex"] = raw.get("fallback_regex", {})
                    return platforms_map
            except Exception as e:
                logger.warning(f"Error loading selectors from ats_selectors.json: {e}")
        logger.warning(f"ats_selectors.json not found at {selectors_path}. Using fallback selectors.")
        return {}
    
    async def fill_form(self):
        """Main entry point. Detects all form fields and fills them."""
        logger.info(f"Starting form fill for platform: {self.platform}")
        await self._fill_standard_fields()
        await self._fill_url_fields()
        await self._upload_resume()
        await self._upload_cover_letter()
        await self._handle_custom_questions()
        
    async def _safe_fill(self, selector: str, value: str, field_name: str):
        try:
            element = await self.page.query_selector(selector)
            if element:
                await self.humanizer.type_text(element, value)
                logger.info(f"Filled {field_name}")
            else:
                logger.debug(f"Field {field_name} not found using {selector}")
        except Exception as e:
            logger.warning(f"Error filling {field_name}: {e}")

    async def _fill_standard_fields(self):
        """Fill first name, last name, email, phone, etc."""
        platform_selectors = self.selectors.get(self.platform, {})
        
        mapping = {
            "first_name": self.candidate.get("first_name", ""),
            "last_name": self.candidate.get("last_name", ""),
            "email": self.candidate.get("email", ""),
            "phone": self.candidate.get("phone", ""),
        }
        
        for field, value in mapping.items():
            if not value:
                continue
            selector = platform_selectors.get(field)
            if selector:
                await self._safe_fill(selector, value, field)
            else:
                # Fallback heuristics
                await self._safe_fill(f"input[name*='{field}' i]", value, field)
    
    async def _fill_url_fields(self):
        """Fill LinkedIn, GitHub, portfolio URLs."""
        platform_selectors = self.selectors.get(self.platform, {})
        mapping = {
            "linkedin": self.candidate.get("linkedin_url", ""),
            "github": self.candidate.get("github_url", ""),
            "portfolio": self.candidate.get("portfolio_url", "")
        }
        for field, value in mapping.items():
            if not value:
                continue
            selector = platform_selectors.get(field) or f"input[name*='{field}' i]"
            await self._safe_fill(selector, value, field)
    
    async def _upload_file(self, selector: str, file_path: str, field_name: str):
        if not file_path:
            return
        path = Path(file_path).resolve()
        if not path.exists():
            logger.error(f"{field_name} not found at {path}")
            return
            
        try:
            file_input = await self.page.query_selector(selector)
            if file_input:
                await file_input.set_input_files(str(path))
                logger.info(f"Uploaded {field_name}")
            else:
                logger.debug(f"{field_name} upload field not found using {selector}")
        except Exception as e:
            logger.warning(f"Failed to upload {field_name}: {e}")
            
    async def _upload_resume(self):
        """Upload resume PDF."""
        platform_selectors = self.selectors.get(self.platform, {})
        selector = platform_selectors.get("resume") or "input[type='file'][name*='resume' i]"
        await self._upload_file(selector, self.candidate.get("resume_pdf_path", ""), "resume")
    
    async def _upload_cover_letter(self):
        """Upload cover letter PDF if field exists."""
        platform_selectors = self.selectors.get(self.platform, {})
        selector = platform_selectors.get("cover_letter") or "input[type='file'][name*='cover' i]"
        await self._upload_file(selector, self.candidate.get("cover_letter_pdf_path", ""), "cover_letter")
    
    async def _handle_custom_questions(self):
        """Use fallback regex to match and fill unknown form fields."""
        logger.info("Checking for custom questions...")
        # Basic heuristic: look for inputs that haven't been filled
        inputs = await self.page.query_selector_all("input[type='text'], textarea")
        for input_el in inputs:
            val = await input_el.input_value()
            if not val:
                name = await input_el.get_attribute("name") or ""
                id_ = await input_el.get_attribute("id") or ""
                combined = f"{name} {id_}".lower()
                
                if "salary" in combined or "compensation" in combined:
                    await self.humanizer.type_text(input_el, "Negotiable")
                    logger.info("Filled custom salary question with 'Negotiable'")

    async def _navigate_multi_step(self):
        """Handle multi-step forms (Workday wizard)."""
        pass # Implementation depends on specific ATS behavior

class AutoApplier:
    """Orchestrates the full auto-apply workflow."""
    
    def __init__(self, mode='semi-auto', browser_type=BROWSER_TYPE, profile_dir='~/.job-autoapply-profile'):
        self.mode = mode
        self.browser_type = browser_type
        self.profile_dir = Path(profile_dir).expanduser().resolve()
        self.detector = ATSDetector()
        
    async def _run_with_playwright(self, application_url: str, resume_path: str, cover_letter_path: Optional[str], dry_run: bool, candidate: dict):
        async with async_playwright() as p:
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=str(self.profile_dir),
                headless=False,
                args=['--disable-blink-features=AutomationControlled']
            )
            page = await browser.new_page()
            await self._process_page(page, application_url, resume_path, cover_letter_path, dry_run, candidate)
            await browser.close()
            
    async def _run_with_camoufox(self, application_url: str, resume_path: str, cover_letter_path: Optional[str], dry_run: bool, candidate: dict):
        async with BrowserImpl(user_data_dir=str(self.profile_dir), headless=False) as browser:
            page = await browser.new_page()
            await self._process_page(page, application_url, resume_path, cover_letter_path, dry_run, candidate)

    async def apply(self, application_url: str, resume_path: str, cover_letter_path: str = None, dry_run: bool = False):
        """Full application flow"""
        logger.info(f"Starting application for {application_url}")
        
        # Load candidate profile
        profile_path = Path(__file__).parent / "candidate_profile.json"
        if not profile_path.exists():
            logger.error("Candidate profile not found!")
            return {"status": "failed", "error": "Profile missing"}
            
        with open(profile_path, "r", encoding="utf-8") as f:
            candidate = json.load(f)
            
        # Check company filter (simplified check for demo)
        filter_obj = CompanyFilter(candidate)
        # Assuming company name is passed or parsed somehow; skipping detailed implementation for brevity here.
        
        try:
            if self.browser_type == 'camoufox' and BROWSER_TYPE == 'camoufox':
                await self._run_with_camoufox(application_url, resume_path, cover_letter_path, dry_run, candidate)
            elif self.browser_type in ['playwright', 'patchright'] and BROWSER_TYPE != 'none':
                await self._run_with_playwright(application_url, resume_path, cover_letter_path, dry_run, candidate)
            else:
                platform = self.detector.detect(application_url)
                logger.warning(f"⚠️ [BROWSER SIMULATION] No headless browser engine installed (Camoufox / Playwright).")
                logger.info(f"   Target URL: {application_url} (Platform detected: {platform.upper()})")
                logger.info(f"   Mapped candidate: {candidate.get('full_name')} ({candidate.get('email')})")
                logger.info("   To enable live anti-detect browser auto-submission, run:")
                logger.info("     pip install playwright && python3 -m playwright install chromium")
                return {"status": "simulated", "platform": platform}
                
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Application failed: {e}", exc_info=True)
            return {"status": "failed", "error": str(e)}

    async def _process_page(self, page, application_url, resume_path, cover_letter_path, dry_run, candidate):
        await page.goto(application_url)
        platform = self.detector.detect(application_url)
        logger.info(f"Detected platform: {platform}")
        
        # Update paths
        candidate["resume_pdf_path"] = resume_path
        if cover_letter_path:
            candidate["cover_letter_pdf_path"] = cover_letter_path
            
        humanizer = HumanBehavior(page)
        filler = FormFiller(page, platform, candidate, humanizer)
        await filler.fill_form()
        
        # Screenshot logic
        screenshot_dir = Path("documents/applications/latest")
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = screenshot_dir / "screenshot.png"
        await page.screenshot(path=str(screenshot_path), full_page=True)
        logger.info(f"Screenshot saved to {screenshot_path}")
        
        if dry_run:
            logger.info("Dry run complete. Skipping submission.")
            return

        if self.mode == 'semi-auto':
            logger.info("Semi-auto mode: Pausing for user review. Press Enter in terminal to continue or wait 60s...")
            await asyncio.sleep(60)
        elif self.mode == 'full-auto':
            logger.info("Full-auto mode: Waiting 10 seconds before submission...")
            await asyncio.sleep(10)
            
            # Try to submit
            platform_selectors = filler.selectors.get(platform, {})
            submit_selector = platform_selectors.get("submit") or "button[type='submit']"
            try:
                submit_btn = await page.query_selector(submit_selector)
                if submit_btn:
                    await submit_btn.click()
                    logger.info("Submitted application!")
                    await asyncio.sleep(5) # wait for confirmation
            except Exception as e:
                logger.error(f"Could not submit form: {e}")

async def run_autofill_daemon(mode='semi-auto', browser_type=None, profile_dir='~/.job-autoapply-profile', dry_run=False):
    if browser_type is None:
        browser_type = BROWSER_TYPE if BROWSER_TYPE != 'none' else 'playwright'
    logger.info("🤖 Browser Auto-Apply Daemon started.")
    logger.info(f"   Mode: {mode} | Active engine: {browser_type} | Profile: {profile_dir}")
    if BROWSER_TYPE == 'none':
        logger.warning("⚠️ [NOTICE] Neither Camoufox nor Playwright installed. Running in simulation mode.")
        logger.info("   Install command: python3 -m pip install playwright && python3 -m playwright install chromium")
    else:
        logger.info(f"✅ Browser automation engine detected: {BROWSER_TYPE}")
        
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
                        st = row.get('status', '')
                        url = row.get('url', '')
                        if 'staged' in st.lower() and url and url.startswith('http') and not url.endswith('/jobs/test'):
                            staged_job = row
                            break
            except Exception as e:
                logger.error(f"Error reading tracker: {e}")
                
        if staged_job:
            logger.info(f"🎯 Found staged application: {staged_job.get('company')} - {staged_job.get('title')}")
            logger.info(f"   URL: {staged_job.get('url')}")
            try:
                await applier.apply(staged_job.get('url'), 'cv/main_example.pdf', dry_run=dry_run)
            except Exception as e:
                logger.error(f"Error during application: {e}")
            logger.info("Application completed. Waiting 60s before processing next opportunity...")
            await asyncio.sleep(60)
        else:
            logger.info("Standing by: No staged applications pending submission. Checking every 30s...")
            await asyncio.sleep(30)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Auto-fill job application forms')
    parser.add_argument('url', nargs='?', default=None, help='Application URL (if omitted, runs as continuous auto-apply daemon)')
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
