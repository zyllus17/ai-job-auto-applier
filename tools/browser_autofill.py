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
from datetime import datetime
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

    def _sanitize_selector(self, sel: str) -> str:
        """Sanitizes selector strings, converting any raw 'aria-label=...' into valid CSS attribute queries."""
        if not sel:
            return ""
        parts = [p.strip() for p in sel.split(",") if p.strip()]
        sanitized = []
        for p in parts:
            if p.startswith("aria-label="):
                val = p[len("aria-label="):].strip("\"'")
                sanitized.append(f"[aria-label*='{val}' i]")
            else:
                sanitized.append(p)
        return ", ".join(sanitized)

    async def _highlight_element(self, element, color="#22c55e"):
        """Visually highlights a form field with a green outline and subtle glow."""
        try:
            if element:
                await element.evaluate(
                    """(el, col) => {
                        el.style.outline = `2px solid ${col}`;
                        el.style.boxShadow = `0 0 10px ${col}`;
                        el.style.transition = 'outline 0.2s, box-shadow 0.2s';
                    }""",
                    color
                )
        except Exception:
            pass

    async def _get_scope(self):
        """Returns the active execution scope (Playwright Frame or Page). Detects Indeed Apply iframes."""
        if self.platform == "indeed":
            try:
                iframe_el = await self.page.query_selector(
                    "iframe[src*='indeedapply'], iframe[title*='application' i], iframe[id*='indeedapply' i], iframe[name*='indeedapply' i]"
                )
                if iframe_el:
                    frame = await iframe_el.content_frame()
                    if frame:
                        return frame
            except Exception:
                pass
        return self.page

    async def _safe_fill(self, selector: str, value: str, field_name: str) -> bool:
        """Safely types value into selector with fallback query and human delay."""
        if not value or not selector:
            return False
        selector = self._sanitize_selector(selector)
        scope = await self._get_scope()
        try:
            element = await scope.query_selector(selector)
            if not element and "," in selector:
                for sub in selector.split(","):
                    sub = sub.strip()
                    if not sub:
                        continue
                    try:
                        element = await scope.query_selector(sub)
                        if element and await element.is_visible():
                            break
                    except Exception:
                        continue
            if not element and scope != self.page:
                try:
                    element = await self.page.query_selector(selector)
                except Exception:
                    pass
            if element:
                is_visible = await element.is_visible()
                if not is_visible:
                    return False
                current_val = await element.input_value() if hasattr(element, "input_value") else ""
                if current_val and current_val.strip() == str(value).strip():
                    await self._highlight_element(element)
                    return True  # Already filled
                await self._highlight_element(element)
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
        elif not full_name_sel:
            await self._safe_fill("input[name*='first' i], input[id*='first' i], [aria-label*='First Name' i]", first, "first_name")

        if plat_sel.get("last_name"):
            await self._safe_fill(plat_sel.get("last_name"), last, "last_name")
        elif not full_name_sel:
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
            target = file_input or await self.page.query_selector("input[type='file']")
            if target:
                await target.set_input_files(str(path))
                await self._highlight_element(target)
                logger.info(f"   📎 Uploaded {field_name}: {path.name}")
                try:
                    await target.dispatch_event("change")
                except Exception:
                    pass
                await self.humanizer.random_delay(400, 800)
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
                    await self._highlight_element(area)
                    await self.humanizer.type_text(area, pitch)
                    logger.info("   ✓ Filled cover letter text note")
            except Exception:
                pass

    async def _handle_location_autocomplete(self):
        """Handle dynamic location search and autocomplete dropdowns (e.g. Ashby)."""
        try:
            loc_inputs = await self.page.query_selector_all("input[placeholder*='Start typing' i]")
            candidate_city = self.candidate.get("city", "Kolkata")
            candidate_loc = self.candidate.get("location", "Kolkata, West Bengal, India")
            for inp in loc_inputs:
                if not await inp.is_visible():
                    continue
                curr = await inp.input_value()
                if curr:
                    continue
                await self._highlight_element(inp)
                await self.humanizer.type_text(inp, candidate_city)
                await asyncio.sleep(1.5)
                # Find matching candidate option in DOM and click it
                clicked = await self.page.evaluate(f"""() => {{
                    const target = "{candidate_loc.lower()}";
                    const cityTarget = "{candidate_city.lower()}";
                    const els = Array.from(document.querySelectorAll('*')).filter(el => {{
                        const txt = (el.innerText || '').trim().toLowerCase();
                        return el.children.length === 0 && (txt.includes(target) || txt.includes(cityTarget));
                    }});
                    if (els.length > 0) {{
                        els[0].click();
                        return true;
                    }}
                    return false;
                }}""")
                if clicked:
                    logger.info(f"   ✓ Selected location autocomplete option for: '{candidate_loc}'")
                else:
                    await inp.evaluate("el => el.blur()")
        except Exception as e:
            logger.debug(f"Location autocomplete note: {e}")

    async def _handle_custom_questions(self):
        """Fill common screening questions (salary, sponsorship, authorization, preferred name, URLs, open responses)."""
        try:
            inputs = await self.page.query_selector_all("input[type='text'], input[type='search'], input[type='url'], input[type='number'], textarea")
            for el in inputs:
                if not await el.is_visible():
                    continue
                current_val = await el.input_value()
                if current_val:
                    continue  # Already has a value

                name = (await el.get_attribute("name") or "").lower()
                id_ = (await el.get_attribute("id") or "").lower()
                aria = (await el.get_attribute("aria-label") or "").lower()
                placeholder = (await el.get_attribute("placeholder") or "").lower()
                inp_type = (await el.get_attribute("type") or "text").lower()
                inp_tag = (await el.evaluate("el => el.tagName") or "").lower()

                # Extract label text associated with this field
                try:
                    label_text = await el.evaluate("""el => {
                        let lbl = '';
                        if (el.id) {
                            const l = document.querySelector('label[for="' + el.id + '"]');
                            if (l) lbl = l.innerText;
                        }
                        if (!lbl) {
                            const parentLbl = el.closest('label');
                            if (parentLbl) lbl = parentLbl.innerText;
                        }
                        if (!lbl) {
                            const container = el.closest('div[class*="field"], div[class*="question"], div[class*="Field"], div[class*="Container"], fieldset') || el.parentElement;
                            if (container) {
                                const l = container.querySelector('label, [class*="label"], [class*="title"], h3, h4, p');
                                if (l) lbl = l.innerText;
                            }
                        }
                        return (lbl || '').trim();
                    }""")
                except Exception:
                    label_text = ""

                combined = f"{name} {id_} {aria} {placeholder} {label_text.lower()}"

                val = None
                field_desc = ""
                if any(w in combined for w in ["prefer us to use", "preferred name"]):
                    val = self.candidate.get("full_name") or self.candidate.get("first_name", "")
                    field_desc = "preferred name"
                elif any(w in combined for w in ["salary", "compensation", "rate", "expected_salary", "desired salary"]):
                    val = str(self.candidate.get("expected_salary", 100000)) if inp_type == "number" else "Negotiable"
                    field_desc = "compensation"
                elif any(w in combined for w in ["sponsor", "visa"]):
                    val = "Yes" if self.candidate.get("work_authorization", {}).get("requires_sponsorship") else "No"
                    field_desc = "visa sponsorship"
                elif any(w in combined for w in ["authorized", "authorization", "legally"]):
                    val = "Yes"
                    field_desc = "work authorization"
                elif (any(w in combined for w in ["years of experience", "years of", "how many years"]) or ("experience" in combined and any(w in combined for w in ["total", "yoe", "number"]))) and inp_tag != "textarea":
                    val = str(self.candidate.get("years_experience", 5))
                    field_desc = "years of experience"
                elif "linkedin" in combined and not current_val:
                    val = self.candidate.get("linkedin_url", "")
                    field_desc = "LinkedIn"
                elif "github" in combined and not current_val:
                    val = self.candidate.get("github_url", "")
                    field_desc = "GitHub"
                elif any(w in combined for w in ["portfolio", "website", "personal site"]) and not current_val:
                    val = self.candidate.get("portfolio_url") or self.candidate.get("github_url", "")
                    field_desc = "Portfolio/Website"
                elif any(w in combined for w in ["notice", "start date", "availability"]):
                    val = "2 weeks"
                    field_desc = "notice/availability"
                elif any(w in combined for w in ["phone", "contact number", "mobile"]) and not current_val:
                    val = self.candidate.get("phone", "")
                    field_desc = "phone"
                elif inp_tag == "textarea" or any(w in combined for w in ["why are you interested", "describe a recent project", "accomplishment", "what excites you", "tell us about", "additional information", "anything else", "spot fraudsters", "project"]):
                    val = "Recent project: Autonomous Multi-Agent Workflow Engine at Floor Boss (AI Automation Engineer with 5+ years of software and AI experience, 2023-Present). Built resilient Playwright browser automations and LLM tool-calling pipelines achieving 99.4% task completion across diverse ATS and web workflows. Verified by Engineering Leadership at Floor Boss."
                    field_desc = f"open-ended question ({label_text[:25]})"

                if val is not None:
                    try:
                        await self._highlight_element(el)
                        try:
                            await self.humanizer.type_text(el, val)
                        except Exception:
                            pass
                        curr_after = await el.input_value()
                        if not curr_after:
                            await el.fill(val)
                        logger.info(f"   ✓ Filled {field_desc}: '{val[:40]}...'")
                    except Exception as e:
                        logger.debug(f"Error filling {field_desc}: {e}")
        except Exception as e:
            logger.debug(f"Custom question handling note: {e}")

    def _determine_dropdown_target(self, label_text: str) -> Optional[str]:
        """Maps question label/prompt to candidate profile response for dropdowns."""
        lt = label_text.lower().strip()
        
        # EEO / Diversity questions
        if "gender" in lt or "sex" in lt:
            return self.candidate.get("eeo_responses", {}).get("gender", "Male")
        if "hispanic" in lt or "latino" in lt:
            return "No"
        if "veteran" in lt:
            return self.candidate.get("eeo_responses", {}).get("veteran_status", "I am not a protected veteran")
        if "disability" in lt:
            return self.candidate.get("eeo_responses", {}).get("disability_status", "I do not wish to answer")
        if "race" in lt or "ethnicity" in lt:
            return self.candidate.get("eeo_responses", {}).get("race_ethnicity", "Decline to self-identify")
            
        # Sponsorship / Visa (evaluated before geographic queries to avoid false positives on 'work from your country of residence')
        if "sponsorship" in lt or "visa" in lt or "sponsor" in lt:
            if any(k in lt for k in ["remain in your current location", "remain in your home country", "work from your country of residence"]):
                return "No"
            requires = self.candidate.get("work_authorization", {}).get("requires_sponsorship", False)
            return "Yes" if requires else "No"

        # Geographic / Location questions
        if any(k in lt for k in ["country in which you are located", "country of residence", "current country", "residence country", "legally registered to work in", "authorized to work in"]):
            return self.candidate.get("country", "India")
        if lt == "country" or "phone country" in lt or "country code" in lt:
            return self.candidate.get("country", "India")
            
        # City/specific location queries (e.g. "located in Bangalore", "located in US")
        if "located in" in lt or "live in" in lt or "based in" in lt:
            cand_loc = (self.candidate.get("location", "") + " " + self.candidate.get("city", "")).lower()
            words = [w for w in lt.split() if len(w) > 3 and w not in ["located", "currently", "live", "based", "are", "you", "city"]]
            if any(w in cand_loc for w in words):
                return "Yes"
            return "No"

        # Work authorization
        if any(k in lt for k in ["authorized to work", "legally authorized", "work authorization", "legal right", "authorization"]):
            return "Yes"

        # Notice period
        if any(k in lt for k in ["notice period", "notice to begin", "notice time", "availability to start", "how soon can you start"]):
            return "1-2 weeks"

        # Restrictions & prior affiliation
        if any(k in lt for k in ["employment agreement", "post-employment", "restriction", "non-compete", "non-disclosure"]):
            return "No"
        if any(k in lt for k in ["previously worked", "prior employee", "former employee", "consulted for", "worked at"]):
            return "No"

        # Experience & Technical proficiencies
        if any(k in lt for k in ["proficiency", "fluency", "hands-on", "scripting", "programming", "python", "llm", "api", "ai"]):
            return "Yes"

        # General boolean fallback
        if lt.endswith("?*") or lt.endswith("?"):
            if any(lt.startswith(prefix) for prefix in ["are you authorized", "do you have experience", "do you have 5+", "are you comfortable"]):
                return "Yes"

        return None

    async def _handle_dropdown_questions(self):
        """Fills both modern React-Select and classic HTML select dropdown questions."""
        # 1. Modern React-Select dropdowns (used in modern Greenhouse, Remix, React apps)
        try:
            containers = await self.page.query_selector_all(".select__container, [class*='select__container']")
            for c in containers:
                if not await c.is_visible():
                    continue

                # Check if already has a selected value
                val_el = await c.query_selector(".select__single-value")
                if val_el and (await val_el.inner_text()).strip():
                    continue

                label_text = ""
                label_el = await c.query_selector("label")
                if label_el:
                    label_text = (await label_el.inner_text()).strip()
                if not label_text:
                    inp = await c.query_selector("input")
                    if inp:
                        label_text = await inp.get_attribute("aria-label") or await inp.get_attribute("placeholder") or ""

                if not label_text:
                    continue

                target = self._determine_dropdown_target(label_text)
                if not target:
                    continue

                control = await c.query_selector(".select__control")
                if not control:
                    continue

                await self._highlight_element(c)
                await control.click()
                await self.humanizer.random_delay(150, 300)

                inp = await c.query_selector("input")
                if inp and len(target) > 2 and target.lower() not in ["yes", "no"]:
                    await inp.fill(target[:4])
                    await self.humanizer.random_delay(150, 250)

                options = await self.page.query_selector_all(".select__option, [role='option'], div[id*='-option-']")
                best_opt = None
                best_score = 0

                for opt in options:
                    txt = (await opt.inner_text()).strip()
                    tl = txt.lower()
                    target_l = target.lower()

                    score = 0
                    if tl == target_l:
                        score = 100
                    elif tl.startswith(target_l) or target_l.startswith(tl):
                        score = 90
                    elif target_l in tl or tl in target_l:
                        score = 80
                    elif target_l in ["decline", "decline to self-identify", "i do not wish to answer"] and any(d in tl for d in ["decline", "not want", "not wish", "do not answer"]):
                        score = 85
                    elif target_l == "no" and (tl == "no" or tl.startswith("no,") or tl.startswith("no ")):
                        score = 95
                    elif target_l == "yes" and (tl == "yes" or tl.startswith("yes,") or tl.startswith("yes ")):
                        score = 95
                    elif "veteran" in target_l and "not a protected veteran" in tl:
                        score = 95

                    if score > best_score:
                        best_score = score
                        best_opt = (opt, txt)

                if best_opt and best_score >= 80:
                    await best_opt[0].click()
                    logger.info(f"   ✓ Selected dropdown for '{label_text[:40]}': {best_opt[1]}")
                    await self.humanizer.random_delay(150, 300)
                else:
                    await self.page.keyboard.press("Escape")
                    await self.humanizer.random_delay(100, 200)
        except Exception as e:
            logger.debug(f"React-Select handling note: {e}")

        # 2. Classic HTML <select> elements
        try:
            selects = await self.page.query_selector_all("select")
            for sel in selects:
                if not await sel.is_visible():
                    continue

                curr = await sel.input_value()
                if curr and curr != "":
                    continue

                sel_id = await sel.get_attribute("id") or ""
                label_text = ""
                if sel_id:
                    lbl = await self.page.query_selector(f"label[for='{sel_id}']")
                    if lbl:
                        label_text = (await lbl.inner_text()).strip()
                if not label_text:
                    # Check parent question container (Lever, Ashby, Workday)
                    try:
                        label_text = (await sel.evaluate(
                            "el => { const q = el.closest('.application-question, .custom-question, [class*=\"question\"]') || el.parentElement; if (q) { const l = q.querySelector('.text, .application-label, label, legend'); return l ? l.innerText.trim() : ''; } return ''; }"
                        )) or ""
                    except Exception:
                        label_text = ""
                if not label_text:
                    label_text = await sel.get_attribute("aria-label") or await sel.get_attribute("name") or ""

                if not label_text:
                    continue

                target = self._determine_dropdown_target(label_text)
                if not target:
                    continue

                options = await sel.query_selector_all("option")
                best_val = None
                best_score = 0
                for opt in options:
                    txt = (await opt.inner_text()).strip()
                    val = await opt.get_attribute("value") or txt
                    if not val or val.lower().startswith("select"):
                        continue
                    tl = txt.lower()
                    target_l = target.lower()

                    score = 0
                    if tl == target_l:
                        score = 100
                    elif tl.startswith(target_l) or target_l.startswith(tl):
                        score = 90
                    elif target_l in tl or tl in target_l:
                        score = 80
                    elif target_l in ["decline", "decline to self-identify", "i do not wish to answer"] and any(d in tl for d in ["decline", "not want", "not wish", "do not answer", "do not care"]):
                        score = 85
                    elif target_l == "no" and (tl == "no" or tl.startswith("no,") or tl.startswith("no ")):
                        score = 95
                    elif target_l == "yes" and (tl == "yes" or tl.startswith("yes,") or tl.startswith("yes ")):
                        score = 95
                    elif "veteran" in target_l and "not a protected veteran" in tl:
                        score = 95
                    elif "1-2 weeks" in target_l and any(w in tl for w in ["1-2", "available", "2 weeks", "immediate"]):
                        score = 95
                    elif target_l == "yes" and any(w in tl for w in ["authorized", "eligible", "citizen", "nationality"]):
                        score = 85

                    if score > best_score:
                        best_score = score
                        best_val = val

                if best_val and best_score >= 80:
                    await sel.select_option(value=best_val)
                    await self._highlight_element(sel)
                    logger.info(f"   ✓ Selected HTML select for '{label_text[:40]}': {best_val}")
                    await self.humanizer.random_delay(150, 300)
        except Exception as e:
            logger.debug(f"HTML select handling note: {e}")

    async def _handle_custom_cards_and_radios(self):
        """
        Fills custom application question cards (used prominently in Lever and other modern ATS),
        handling checkboxes (referrals, prior employment, privacy consent), radio button groups
        (EEO race/ethnicity), text inputs (signature, date, salary, legal country).
        """
        try:
            questions = await self.page.query_selector_all(".application-question, .custom-question, div[class*='question'], .ashby-application-form-field-entry, div[class*='fieldEntry'], fieldset")
            for q in questions:
                if not await q.is_visible():
                    continue

                lbl_el = await q.query_selector(".ashby-application-form-question-title, .text, .application-label, label, legend")
                ltxt = (await lbl_el.inner_text()).strip() if lbl_el else ""
                lt = ltxt.lower()

                # 0. Yes/No button toggle widgets (Ashby)
                yesno = await q.query_selector(".ashby-application-form-input-yesno, div[class*='yesno']")
                if yesno:
                    target = "Yes"
                    if any(w in lt for w in ["relocate", "based in", "authorized", "authorization", "legally"]):
                        target = "Yes"
                    elif any(w in lt for w in ["sponsorship", "visa"]):
                        target = "Yes" if self.candidate.get("work_authorization", {}).get("requires_sponsorship") else "No"
                    btn = await yesno.query_selector(f"button:has-text('{target}')")
                    if btn:
                        await btn.click()
                        await self._highlight_element(btn)
                        logger.info(f"   ✓ Toggled Yes/No '{target}' for: '{ltxt[:35]}'")
                    continue

                # 1. Checkboxes
                checkboxes = await q.query_selector_all("input[type='checkbox']")
                if checkboxes:
                    if "hear about us" in lt or "how did you" in lt:
                        for cb in checkboxes:
                            val = (await cb.get_attribute("value") or "").lower()
                            if "linkedin" in val or "other" in val or "career site" in val:
                                await cb.evaluate("el => { el.checked = true; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); }")
                                await self._highlight_element(cb)
                                logger.info(f"   ✓ Checked '{val}' for: '{ltxt[:35]}'")
                                break
                    elif "previously been employed" in lt or "worked here" in lt or "former employee" in lt:
                        for cb in checkboxes:
                            val = (await cb.get_attribute("value") or "").lower()
                            if val == "no":
                                await cb.evaluate("el => { el.checked = true; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); }")
                                await self._highlight_element(cb)
                                logger.info(f"   ✓ Checked 'No' for: '{ltxt[:35]}'")
                                break
                    elif any(k in lt for k in ["privacy", "terms", "agree", "acknowledge", "consent", "notice", "understand how my personal"]):
                        for cb in checkboxes:
                            await cb.evaluate("el => { el.checked = true; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); }")
                            await self._highlight_element(cb)
                            logger.info(f"   ✓ Checked agreement for: '{ltxt[:35]}'")

                # 2. Radio buttons
                radios = await q.query_selector_all("input[type='radio']")
                if radios:
                    target_val = None
                    if "race" in lt or "ethnicity" in lt:
                        target_val = self.candidate.get("eeo_responses", {}).get("race_ethnicity", "Decline to self-identify")
                    elif "gender" in lt:
                        target_val = self.candidate.get("eeo_responses", {}).get("gender", "Male")
                    elif "veteran" in lt:
                        target_val = self.candidate.get("eeo_responses", {}).get("veteran_status", "I am not a protected veteran")
                    elif "disability" in lt:
                        target_val = self.candidate.get("eeo_responses", {}).get("disability_status", "I do not wish to answer")
                    elif "authorized" in lt or "authorization" in lt:
                        target_val = "Yes"
                    elif "sponsorship" in lt:
                        target_val = "No" if not self.candidate.get("work_authorization", {}).get("requires_sponsorship") else "Yes"
                    elif "salary" in lt and any(w in lt for w in ["format", "cadence", "period"]):
                        target_val = "Annual"
                    elif any(w in lt for w in ["work type", "employment type", "preference"]):
                        target_val = "Full-time"
                    elif any(w in lt for w in ["overlap", "working hours", "timezone"]):
                        target_val = "US business hours"
                    elif "english" in lt:
                        target_val = "Native / Fluent"
                    elif any(w in lt for w in ["hear about", "how did you hear", "source"]):
                        target_val = "LinkedIn"
                    elif any(w in lt for w in ["year", "years of experience"]):
                        target_val = "3-5"

                    if target_val:
                        best_radio = None
                        best_score = 0
                        for r in radios:
                            r_val = (await r.get_attribute("value") or "").lower()
                            try:
                                r_lbl = await r.evaluate("""el => {
                                    if (el.id) {
                                        const l = document.querySelector('label[for="' + el.id + '"]');
                                        if (l) return l.innerText;
                                    }
                                    const optParent = el.closest('.ashby-application-form-input-radio-group-option, div[class*="option"], label');
                                    return optParent ? optParent.innerText : '';
                                }""")
                            except Exception:
                                r_lbl = ""
                            combined_r = f"{r_val} {r_lbl.lower()}".strip()
                            tl = target_val.lower()

                            score = 0
                            if r_val and tl == r_val:
                                score = 100
                            elif r_lbl and tl == r_lbl.lower().strip():
                                score = 100
                            elif tl in combined_r or (r_val and r_val in tl):
                                score = 90
                            elif "decline" in tl and "decline" in combined_r:
                                score = 95
                            elif tl == "no" and (r_val == "no" or combined_r.startswith("no")):
                                score = 95
                            elif tl == "yes" and (r_val == "yes" or combined_r.startswith("yes")):
                                score = 95
                            elif "annual" in tl and "annual" in combined_r:
                                score = 95
                            elif "full-time" in tl and "full-time" in combined_r:
                                score = 95
                            elif "us business hours" in tl and "us business hours" in combined_r:
                                score = 95
                            elif "native" in tl and "native" in combined_r:
                                score = 95
                            elif "linkedin" in tl and "linkedin" in combined_r:
                                score = 95
                            elif "3-5" in tl and "3-5" in combined_r:
                                score = 95

                            if score > best_score:
                                best_score = score
                                best_radio = (r, r_lbl.strip() or r_val or "option")

                        if best_radio and best_score >= 80:
                            await best_radio[0].evaluate("""el => {
                                const lbl = el.id ? document.querySelector('label[for="' + el.id + '"]') : null;
                                if (lbl) {
                                    lbl.click();
                                } else {
                                    const parentOpt = el.closest('.ashby-application-form-input-radio-group-option, label, div[class*="option"]');
                                    if (parentOpt) {
                                        parentOpt.click();
                                    } else {
                                        el.checked = true;
                                        el.dispatchEvent(new Event('input', { bubbles: true }));
                                        el.dispatchEvent(new Event('change', { bubbles: true }));
                                    }
                                }
                            }""")
                            await self._highlight_element(best_radio[0])
                            logger.info(f"   ✓ Checked radio '{best_radio[1]}' for: '{ltxt[:35]}'")

                # 3. Custom text inputs inside cards (signature, date, country, salary)
                text_inputs = await q.query_selector_all("input[type='text']:not([name='name']):not([name='phone']):not([name='location']), input[type='number'], input[type='url']")
                for ti in text_inputs:
                    curr = await ti.input_value()
                    if curr:
                        continue
                    name_attr = await ti.get_attribute("name") or ""
                    ti_type = (await ti.get_attribute("type") or "text").lower()
                    
                    val = None
                    desc = ""
                    if "disabilitysignaturedate" in name_attr.lower() or "date" in lt:
                        val = datetime.now().strftime("%m/%d/%Y")
                        desc = f"signature date '{val}'"
                    elif "disabilitysignature" in name_attr.lower() or "signature" in lt or lt == "name":
                        val = self.candidate.get("full_name", "")
                        desc = f"legal signature '{val}'"
                    elif "country" in lt and any(w in lt for w in ["work in", "registered", "residence"]):
                        val = self.candidate.get("country", "India")
                        desc = f"registered country '{val}'"
                    elif any(k in lt for k in ["salary", "compensation", "ote", "rate", "expectations"]):
                        val = str(self.candidate.get("expected_salary", 100000)) if ti_type == "number" else "Negotiable"
                        desc = f"compensation '{val}'"

                    if val:
                        await self._highlight_element(ti)
                        try:
                            await self.humanizer.type_text(ti, val)
                        except Exception:
                            pass
                        curr_after = await ti.input_value()
                        if not curr_after:
                            await ti.fill(val)
                        logger.info(f"   ✓ Filled {desc} for: '{name_attr or ltxt[:25]}'")
        except Exception as e:
            logger.error(f"Custom cards and radios error: {e}", exc_info=True)

    # -------------------------------------------------------------
    # Workday Specialized Multi-Step Handlers
    # -------------------------------------------------------------
    async def _handle_workday_auth_step(self):
        """Handles Workday Step 1: Sign in or Create Account with beecatcher honeypot evasion."""
        email_btn = await self.page.query_selector("[data-automation-id='SignInWithEmailButton']")
        if email_btn and await email_btn.is_visible():
            logger.info("   🔐 Workday: Clicking 'Sign in with email'...")
            try:
                await email_btn.click(force=True)
            except Exception:
                await email_btn.evaluate("el => el.click()")
            await asyncio.sleep(2)

        email_val = self.candidate.get("email", "")
        password_val = self.candidate.get("workday_password", "WorkdayApplier2026!#")

        email_input = await self.page.query_selector("input[data-automation-id='email']")
        pwd_input = await self.page.query_selector("input[data-automation-id='password']")
        verify_inp = await self.page.query_selector("input[data-automation-id='verifyPassword']")

        if verify_inp:
            # We are on Create Account screen
            logger.info(f"   📝 Workday: Creating candidate account for {email_val}...")
            cb = await self.page.query_selector("input[data-automation-id='createAccountCheckbox']")
            if email_input:
                await email_input.fill("")
                await email_input.type(email_val, delay=10)
            if pwd_input:
                await pwd_input.fill("")
                await pwd_input.type(password_val, delay=10)
            if verify_inp:
                await verify_inp.fill("")
                await verify_inp.type(password_val, delay=10)
            if cb:
                try:
                    await cb.check(force=True)
                except Exception:
                    pass

            # CRITICAL: Never touch beecatcher honeypot!
            ca_filter = await self.page.query_selector(
                "div[data-automation-id='click_filter'][aria-label*='Create Account' i], button[data-automation-id='createAccountSubmitButton']"
            )
            if ca_filter:
                try:
                    await ca_filter.click(force=True)
                except Exception:
                    await ca_filter.evaluate("el => el.click()")
                await asyncio.sleep(4)

        # If redirected to /login or on sign-in screen
        email_input = await self.page.query_selector("input[data-automation-id='email']")
        pwd_input = await self.page.query_selector("input[data-automation-id='password']")
        si_filter = await self.page.query_selector(
            "div[data-automation-id='click_filter'][aria-label*='Sign In' i], button[data-automation-id='signInSubmitButton']"
        )
        if si_filter and email_input and pwd_input:
            logger.info(f"   🔑 Workday: Attempting Sign In with {email_val}...")
            await email_input.fill("")
            await email_input.type(email_val, delay=10)
            await pwd_input.fill("")
            await pwd_input.type(password_val, delay=10)
            try:
                await si_filter.click(force=True)
            except Exception:
                await si_filter.evaluate("el => el.click()")
            await asyncio.sleep(4)

        # Check if auth passed or requires email verification / manual sign in
        active_step = await self.page.query_selector("[data-automation-id='progressBarActiveStep']")
        st = (await active_step.inner_text()).lower() if active_step else ""
        if "sign in" in st or "create account" in st or "/login" in self.page.url.lower():
            err_el = await self.page.query_selector("[role='alert'], .errorMessage, [data-automation-id*='error' i]")
            err_txt = (await err_el.inner_text()).strip() if err_el else "Sign-in required"
            logger.warning(f"🔒 [WORKDAY AUTH REQUIRED] {err_txt}")
            logger.info("   💡 Please complete Workday verification/sign-in in the browser window.")
            logger.info("   Waiting up to 45s for step 2 (My Information)...")
            for _ in range(45):
                if self.page.is_closed():
                    break
                curr_step = await self.page.query_selector("[data-automation-id='progressBarActiveStep']")
                curr_txt = (await curr_step.inner_text()).lower() if curr_step else ""
                if "my information" in curr_txt or await self.page.query_selector("[data-automation-id='applyFlowMyInfoPage']"):
                    logger.info("   ✅ Workday authenticated! Advanced to My Information.")
                    break
                await asyncio.sleep(1)

        logger.info("   ✅ Workday: Authentication step handled.")

    async def _handle_workday_my_info_step(self):
        """Fills Workday Step 2: Personal information, contact, address, state, source."""
        logger.info("   📋 Workday: Populating 'My Information'...")
        await asyncio.sleep(2)

        # 1. Source (How Did You Hear About Us?)
        source_field = await self.page.query_selector("[data-automation-id='formField-source']")
        if source_field:
            curr_text = await source_field.inner_text()
            if "0 items selected" in curr_text or "Expanded" in curr_text or not curr_text.strip():
                icon = await source_field.query_selector("[data-automation-id='promptIcon'], [data-automation-id='multiselectInputContainer'], input")
                if icon:
                    try:
                        await icon.click()
                        await asyncio.sleep(1)
                        jb = await self.page.query_selector("[data-automation-id='menuItem']:has-text('Job Board'), [data-automation-id='menuItem']:has-text('Career')")
                        if jb:
                            await jb.click()
                            await asyncio.sleep(1)
                            sub = await self.page.query_selector(
                                "[data-automation-id='menuItem']:has-text('Careers'), "
                                "[data-automation-id='menuItem']:has-text('LinkedIn'), "
                                "[data-automation-id='menuItem']:has-text('Indeed')"
                            )
                            if not sub:
                                sub_items = await self.page.query_selector_all("[data-automation-id='menuItem']")
                                if sub_items:
                                    sub = sub_items[0]
                            if sub:
                                await sub.click()
                                logger.info("      ✓ Selected Source: Career / Job Board")
                        else:
                            opts = await self.page.query_selector_all("[data-automation-id='menuItem'], [data-automation-id='promptOption']")
                            for o in opts:
                                lbl = (await o.inner_text()).strip()
                                if lbl and "india" not in lbl.lower() and "select" not in lbl.lower():
                                    await o.click()
                                    logger.info(f"      ✓ Selected Source: {lbl}")
                                    break
                    except Exception as e:
                        logger.debug(f"Workday source selection note: {e}")
                    finally:
                        await self.page.keyboard.press("Escape")
                        await asyncio.sleep(0.4)

        # 2. Previous Worker (Have you previously worked for...?) -> No
        pw_field = await self.page.query_selector("[data-automation-id='formField-candidateIsPreviousWorker'], fieldset:has-text('previously worked')")
        if pw_field:
            no_lbl = await pw_field.query_selector("label:has-text('No'), input[value*='n' i] + label")
            if no_lbl:
                try:
                    await no_lbl.click(force=True)
                    logger.info("      ✓ Selected Previous Worker: No")
                except Exception:
                    pass

        # 3. Legal Name
        fn_input = await self.page.query_selector("[data-automation-id='formField-legalName--firstName'] input, [data-automation-id='legalNameSection_firstName'], [data-automation-id='legalName--firstName'] input")
        if fn_input and not await fn_input.input_value():
            first_name = self.candidate.get("first_name", "Maruf")
            await fn_input.fill(first_name)
            logger.info(f"      ✓ Filled First Name: {first_name}")

        ln_input = await self.page.query_selector("[data-automation-id='formField-legalName--lastName'] input, [data-automation-id='legalNameSection_lastName'], [data-automation-id='legalName--lastName'] input")
        if ln_input and not await ln_input.input_value():
            last_name = self.candidate.get("last_name", "Hassan")
            await ln_input.fill(last_name)
            logger.info(f"      ✓ Filled Last Name: {last_name}")

        # 4. Address & Location
        addr_input = await self.page.query_selector("[data-automation-id='formField-addressLine1'] input")
        if addr_input and not await addr_input.input_value():
            addr = self.candidate.get("location", "Park Street").split(",")[0].strip()
            await addr_input.fill(addr)
            logger.info(f"      ✓ Filled Address: {addr}")

        city_input = await self.page.query_selector("[data-automation-id='formField-city'] input, [data-automation-id='addressSection_city']")
        if city_input and not await city_input.input_value():
            city = self.candidate.get("city", "Kolkata")
            await city_input.fill(city)
            logger.info(f"      ✓ Filled City: {city}")

        postal_input = await self.page.query_selector("[data-automation-id='formField-postalCode'] input")
        if postal_input and not await postal_input.input_value():
            await postal_input.fill("700016")
            logger.info("      ✓ Filled Postal Code: 700016")

        # 5. State / Region
        state_btn = await self.page.query_selector("button#address--countryRegion, button[name='countryRegion'], [data-automation-id='formField-countryRegion'] button")
        if state_btn:
            st_text = await state_btn.inner_text()
            if "select one" in st_text.lower():
                try:
                    await state_btn.click(force=True)
                    await asyncio.sleep(1)
                    st_opt = await self.page.query_selector("li[role='option']:has-text('West Bengal'), [data-automation-label*='West Bengal' i]")
                    if not st_opt:
                        opts = await self.page.query_selector_all("li[role='option'], [data-automation-id='promptOption']")
                        for o in opts:
                            t = (await o.inner_text()).strip()
                            if t and "select one" not in t.lower():
                                st_opt = o
                                break
                    if st_opt:
                        logger.info(f"      ✓ Selected State: {(await st_opt.inner_text()).strip()}")
                        await st_opt.click()
                except Exception as e:
                    logger.debug(f"Workday state selection note: {e}")
                finally:
                    await self.page.keyboard.press("Escape")
                    await asyncio.sleep(0.4)

        # 6. Phone Device Type
        pt_btn = await self.page.query_selector("button#phoneNumber--phoneType, button[name='phoneType'], [data-automation-id='formField-phoneType'] button")
        if pt_btn:
            pt_text = await pt_btn.inner_text()
            if "select one" in pt_text.lower():
                try:
                    await pt_btn.click(force=True)
                    await asyncio.sleep(1)
                    mobile_opt = await self.page.query_selector("li[role='option']:has-text('Mobile'), [data-automation-label*='Mobile' i]")
                    if mobile_opt:
                        await mobile_opt.click()
                        logger.info("      ✓ Selected Phone Type: Mobile")
                except Exception as e:
                    logger.debug(f"Workday phone type selection note: {e}")
                finally:
                    await self.page.keyboard.press("Escape")
                    await asyncio.sleep(0.4)

        # 7. Phone Number
        phone_input = await self.page.query_selector("[data-automation-id='formField-phoneNumber'] input, input#phoneNumber--phoneNumber, [data-automation-id='phone-number']")
        if phone_input and not await phone_input.input_value():
            raw_phone = self.candidate.get("phone", "7980356852")
            cleaned_phone = re.sub(r"[^\d]", "", raw_phone)[-10:]
            await phone_input.fill(cleaned_phone)
            logger.info(f"      ✓ Filled Phone: {cleaned_phone}")

    async def _handle_workday_experience_step(self):
        """Fills Workday Step 3: Resume upload and Websites."""
        logger.info("   💼 Workday: Populating 'My Experience'...")
        await asyncio.sleep(2)

        resume_path = self.candidate.get("resume_pdf_path")
        if resume_path:
            p = Path(resume_path).expanduser().resolve()
            if p.exists():
                file_input = await self.page.query_selector("input[type='file']")
                if file_input:
                    logger.info(f"      📎 Uploading resume to Workday: {p.name}")
                    await file_input.set_input_files(str(p))
                    await asyncio.sleep(3)

        linkedin_url = self.candidate.get("linkedin_url", "")
        if linkedin_url:
            web_input = await self.page.query_selector("[data-automation-id='formField-website'] input, input[aria-label*='website' i], input[placeholder*='website' i]")
            if web_input and not await web_input.input_value():
                await web_input.fill(linkedin_url)
                logger.info(f"      ✓ Filled Website: {linkedin_url}")

    async def _handle_workday_questions_step(self):
        """Fills Workday Step 4: Screening questions, notice period, legal/authorization."""
        logger.info("   ❓ Workday: Populating 'Application Questions'...")
        await self._handle_custom_questions()
        await self._handle_dropdown_questions()
        await self._handle_custom_cards_and_radios()

    async def _handle_workday_disclosures_step(self):
        """Fills Workday Step 5: EEO demographics, veteran status, disability, acknowledgment."""
        logger.info("   🏛️ Workday: Populating 'Voluntary Disclosures'...")
        await asyncio.sleep(1)
        await self._handle_dropdown_questions()
        await self._handle_custom_cards_and_radios()

        ack_cb = await self.page.query_selector(
            "input[type='checkbox'][data-automation-id*='agree' i], "
            "input[type='checkbox'][data-automation-id*='terms' i], "
            "label:has-text('I agree'), label:has-text('I acknowledge')"
        )
        if ack_cb:
            try:
                await ack_cb.click(force=True)
                logger.info("      ✓ Checked Voluntary Disclosure Acknowledgment")
            except Exception:
                pass

    async def _fill_workday_flow(self) -> bool:
        """Detects current Workday step and executes appropriate step logic."""
        active_step_el = await self.page.query_selector("[data-automation-id='progressBarActiveStep']")
        active_text = (await active_step_el.inner_text()).lower() if active_step_el else ""

        # Step 1: Authentication
        if "create account" in active_text or "sign in" in active_text or await self.page.query_selector("button[data-automation-id='createAccountSubmitButton'], button[data-automation-id='SignInWithEmailButton']"):
            await self._handle_workday_auth_step()
            new_active_el = await self.page.query_selector("[data-automation-id='progressBarActiveStep']")
            new_text = (await new_active_el.inner_text()).lower() if new_active_el else ""
            if "my information" in new_text or await self.page.query_selector("[data-automation-id='applyFlowMyInfoPage']"):
                await self._handle_workday_my_info_step()
            return True

        # Step 2: My Information
        if "my information" in active_text or await self.page.query_selector("[data-automation-id='applyFlowMyInfoPage']"):
            await self._handle_workday_my_info_step()
            return True

        # Step 3: My Experience
        if "my experience" in active_text or await self.page.query_selector("h3:has-text('Work Experience'), h2:has-text('My Experience'), input[type='file']"):
            await self._handle_workday_experience_step()
            return True

        # Step 4: Application Questions
        if "application questions" in active_text or "questions" in active_text:
            await self._handle_workday_questions_step()
            return True

        # Step 5: Voluntary Disclosures
        if "voluntary disclosures" in active_text or "disclosures" in active_text:
            await self._handle_workday_disclosures_step()
            return True

        # Step 6: Review
        if "review" in active_text:
            logger.info("   🔍 Workday: Review page reached.")
            return True

        # Fallback to standard fill
        await self._fill_standard_fields()
        await self._fill_url_fields()
        await self._upload_resume()
        await self._handle_custom_questions()
        await self._handle_dropdown_questions()
        await self._handle_custom_cards_and_radios()
        return True

    async def _fill_indeed_flow(self) -> bool:
        """Executes Indeed Apply flow (Contact Info, Resume, Screening Questions, Review)."""
        scope = await self._get_scope()
        first_name = self.candidate.get("first_name", "")
        last_name = self.candidate.get("last_name", "")
        full_name = self.candidate.get("full_name") or f"{first_name} {last_name}".strip()
        email = self.candidate.get("email", "")
        phone = self.candidate.get("phone", "")
        city = self.candidate.get("city", "") or self.candidate.get("location", "")

        # 1. Contact Information
        fn_input = await scope.query_selector("input#input-firstName, input[name='firstName'], [data-testid*='firstName' i]")
        if fn_input and not await fn_input.input_value():
            await fn_input.fill(first_name)
            logger.info(f"   ✓ Filled first_name: {first_name}")

        ln_input = await scope.query_selector("input#input-lastName, input[name='lastName'], [data-testid*='lastName' i]")
        if ln_input and not await ln_input.input_value():
            await ln_input.fill(last_name)
            logger.info(f"   ✓ Filled last_name: {last_name}")

        name_input = await scope.query_selector("input#input-name, input[name='name'], [data-testid*='ContactInfo-Name' i]")
        if name_input and not await name_input.input_value():
            await name_input.fill(full_name)
            logger.info(f"   ✓ Filled full_name: {full_name}")

        email_input = await scope.query_selector("input#input-email, input[name='email'], input[type='email'], [data-testid*='ContactInfo-Email' i]")
        if email_input and not await email_input.input_value():
            await email_input.fill(email)
            logger.info(f"   ✓ Filled email: {email}")

        phone_input = await scope.query_selector("input#input-phoneNumber, input[name='phoneNumber'], input[type='tel'], [data-testid*='ContactInfo-PhoneNumber' i]")
        if phone_input and not await phone_input.input_value():
            raw_phone = re.sub(r"[^\d]", "", phone)[-10:]
            await phone_input.fill(raw_phone)
            logger.info(f"   ✓ Filled phone: {raw_phone}")

        loc_input = await scope.query_selector("input#input-location, input#input-applicant\\.location\\.city, input[name*='location' i], [data-testid*='Location' i]")
        if loc_input and not await loc_input.input_value():
            await loc_input.fill(city)
            logger.info(f"   ✓ Filled location: {city}")

        # 2. Resume Upload
        resume_path = self.candidate.get("resume_pdf_path")
        if resume_path:
            p = Path(resume_path).expanduser().resolve()
            if p.exists():
                file_input = await scope.query_selector("input[type='file'], input[data-testid*='resume' i]")
                if file_input:
                    try:
                        logger.info(f"   📎 Uploading resume to Indeed: {p.name}")
                        await file_input.set_input_files(str(p))
                        await asyncio.sleep(2)
                    except Exception as e:
                        logger.debug(f"Indeed resume upload note: {e}")

        # 3. Screening Questions & Experience
        num_inputs = await scope.query_selector_all("input[type='number'], input[id*='experience' i]")
        for ni in num_inputs:
            if await ni.is_visible() and not await ni.input_value():
                years = str(self.candidate.get("years_experience", 5))
                await ni.fill(years)
                logger.info(f"   ✓ Filled years of experience question: {years}")

        try:
            radios = await scope.query_selector_all("input[type='radio']")
            handled_groups = set()
            for r in radios:
                r_name = await r.get_attribute("name")
                if r_name and r_name in handled_groups:
                    continue
                parent = await r.evaluate_handle("el => el.closest('fieldset, .ia-Question, div[role=\"radiogroup\"]') || el.parentElement")
                p_text = (await parent.as_element().inner_text()).lower() if parent.as_element() else ""
                
                if "sponsorship" in p_text or "visa" in p_text:
                    req_sponsorship = self.candidate.get("work_authorization", {}).get("requires_sponsorship", True)
                    val_target = "yes" if req_sponsorship else "no"
                elif "authorized" in p_text or "legally" in p_text:
                    val_target = "yes"
                elif "driver" in p_text or "license" in p_text:
                    val_target = "yes"
                elif "background" in p_text or "drug" in p_text:
                    val_target = "yes"
                elif any(q in p_text for q in ["comfortable", "willing", "commute", "relocate", "experience"]):
                    val_target = "yes"
                else:
                    val_target = "yes"

                group_radios = await parent.as_element().query_selector_all("input[type='radio']") if parent.as_element() else [r]
                for gr in group_radios:
                    gr_lbl = (await gr.evaluate("el => (el.labels && el.labels[0] ? el.labels[0].innerText : '') || el.value || el.parentElement.innerText")).lower()
                    if val_target in gr_lbl:
                        await gr.click(force=True)
                        logger.info(f"   ✓ Selected Indeed radio ({val_target}): '{p_text[:35]}...'")
                        break
                if r_name:
                    handled_groups.add(r_name)
        except Exception as e:
            logger.debug(f"Indeed radio note: {e}")

        await self._handle_custom_questions()
        await self._handle_dropdown_questions()

        # 4. Review Page Detection
        review_heading = await scope.query_selector(
            "h1:has-text('Review your application'), h2:has-text('Review your application'), [data-testid='review-page']"
        )
        if review_heading:
            logger.info("   🔍 Indeed: Review page reached.")

        return True

    async def fill_form(self) -> bool:
        """Main entry point. Detects all form fields and fills them."""
        logger.info(f"📋 Starting form fill for detected ATS: [{self.platform.upper()}]")
        if self.platform == "workday":
            return await self._fill_workday_flow()
        if self.platform == "indeed":
            return await self._fill_indeed_flow()
        await self._fill_standard_fields()
        await self._fill_url_fields()
        await self._handle_location_autocomplete()
        await self._upload_resume()
        await self._upload_cover_letter()
        await self._handle_custom_questions()
        await self._handle_dropdown_questions()
        await self._handle_custom_cards_and_radios()
        return True

    async def advance_wizard_step(self) -> bool:
        """Clicks 'Next' / 'Save and Continue' / 'Review' button in multi-step forms (e.g. Workday, Indeed, Easy Apply)."""
        scope = await self._get_scope()
        plat_sel = self.selectors.get(self.platform, {})
        next_sel = (
            plat_sel.get("next_button") or 
            "button:has-text('Continue'), button:has-text('Review your application'), [data-testid='continue-button'], button.ia-continueButton, "
            "div[data-automation-id='click_filter'][aria-label*='Save and Continue' i], "
            "div[data-automation-id='click_filter'][aria-label*='Next' i], "
            "div[data-automation-id='click_filter'][aria-label*='Review' i], "
            "button[data-automation-id='pageFooterNextButton'], "
            "button[data-automation-id='bottom-navigation-next-button'], "
            "button:has-text('Save and Continue'), button:has-text('Next'), "
            "button:has-text('Continue'), button:has-text('Review'), "
            "button[aria-label*='Next' i], button[aria-label*='Continue' i]"
        )
        try:
            btn = await scope.query_selector(next_sel)
            if not btn and scope != self.page:
                btn = await self.page.query_selector(next_sel)
            if btn and await btn.is_visible() and await btn.is_enabled():
                logger.info("   ⏩ Multi-step wizard: Advancing to next step...")
                try:
                    await btn.click(force=True)
                except Exception:
                    await btn.evaluate("el => el.click()")
                try:
                    await self.page.wait_for_load_state("domcontentloaded", timeout=7000)
                except Exception:
                    pass
                await asyncio.sleep(3)
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

        # 2. Ashby Job Posting -> Click 'Apply for this Job' or navigate to /application
        elif "ashbyhq.com" in current_url.lower() and "/application" not in current_url.lower():
            try:
                apply_btn = await page.query_selector("a[href*='/application'], button:has-text('Apply for this Job'), a:has-text('Apply for this Job'), a:has-text('Apply')")
                if apply_btn and await apply_btn.is_visible():
                    logger.info("   -> Ashby description detected: Clicking 'Apply for this Job'...")
                    await apply_btn.click()
                    await asyncio.sleep(3)
                else:
                    parsed = urlparse(current_url)
                    path = parsed.path.rstrip('/')
                    if not path.endswith('/application'):
                        path = f"{path}/application"
                    apply_url = urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment))
                    logger.info(f"   -> Ashby navigating directly to: {apply_url}")
                    await page.goto(apply_url, wait_until="domcontentloaded", timeout=20000)
                platform = "ashby"
            except Exception as e:
                logger.debug(f"Ashby unwrap exception: {e}")

        # 3. LinkedIn Job Posting -> Check for Login Wall or Easy Apply or Offsite Apply
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

        # 4. Greenhouse Job Posting -> Check for top 'Apply' button to scroll down / reveal form
        elif "greenhouse.io" in current_url.lower():
            try:
                apply_btn = await page.query_selector("button:has-text('Apply'), a:has-text('Apply'), button[aria-label='Apply'], a[href*='#app']")
                if apply_btn and await apply_btn.is_visible():
                    logger.info("   -> Greenhouse 'Apply' button found. Clicking to reveal application form...")
                    await apply_btn.click()
                    await asyncio.sleep(1.5)
            except Exception as e:
                logger.debug(f"Greenhouse apply scroll note: {e}")
            platform = "greenhouse"

        # 5. Workday Job Posting -> Click 'Apply' button to open modal, then click 'Apply Manually'
        elif "myworkdayjobs.com" in current_url.lower() or "myworkday.com" in current_url.lower():
            try:
                if "/apply" in current_url.lower():
                    try:
                        await page.wait_for_selector(
                            "input[data-automation-id='email'], [data-automation-id='applyFlowPage'], [data-automation-id='progressBarActiveStep']",
                            timeout=15000
                        )
                    except Exception:
                        pass
                else:
                    apply_btn = None
                    try:
                        apply_btn = await page.wait_for_selector(
                            "a[data-automation-id='adventureButton'], [data-automation-id='applyButton'], a:has-text('Apply'), button:has-text('Apply')",
                            timeout=12000
                        )
                    except Exception:
                        pass

                    if apply_btn and await apply_btn.is_visible():
                        logger.info("   -> Workday job description detected: Clicking 'Apply'...")
                        await apply_btn.click()
                        
                        manually_btn = None
                        try:
                            manually_btn = await page.wait_for_selector(
                                "a[data-automation-id='applyManually'], button[data-automation-id='applyManually'], [data-automation-id='applyManually'], a:has-text('Apply Manually')",
                                timeout=8000
                            )
                        except Exception:
                            pass

                        if manually_btn and await manually_btn.is_visible():
                            logger.info("   -> Workday modal detected: Clicking 'Apply Manually'...")
                            await manually_btn.click()
                            try:
                                await page.wait_for_selector(
                                    "input[data-automation-id='email'], [data-automation-id='applyFlowPage'], [data-automation-id='progressBarActiveStep']",
                                    timeout=15000
                                )
                            except Exception:
                                pass
                        else:
                            parsed = urlparse(current_url)
                            path = parsed.path.rstrip('/') + "/apply/applyManually"
                            direct_apply_url = urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment))
                            logger.info(f"   -> Workday navigating directly to: {direct_apply_url}")
                            await page.goto(direct_apply_url, wait_until="domcontentloaded", timeout=20000)
            except Exception as e:
                logger.debug(f"Workday unwrap exception: {e}")
            platform = "workday"

        # 6. Indeed Job Posting -> Check for 'Apply now' (Indeed Apply) or 'Apply on company site'
        elif "indeed.com" in current_url.lower() or "indeedapply" in current_url.lower() or "smartapply" in current_url.lower():
            platform = "indeed"
            # Check for bot detection / sign in wall
            if "secure.indeed.com/auth" in current_url.lower() or "bot-detection" in current_url.lower():
                logger.warning("🔒 [INDEED LOGIN REQUIRED] Indeed requires an active user session.")
                if self.mode == 'semi-auto':
                    logger.info("   💡 Please sign in to Indeed in the browser window now.")
                    logger.info("   Session cookies will be preserved in ~/.job-autoapply-profile.")
                    logger.info("   Waiting up to 45s for sign-in...")
                    for _ in range(45):
                        if page.is_closed():
                            break
                        if "viewjob" in page.url.lower() or "indeedapply" in page.url.lower() or "smartapply" in page.url.lower():
                            logger.info("   ✅ Indeed authenticated!")
                            current_url = page.url
                            break
                        await asyncio.sleep(1)

            # Check if this is an Indeed job view page (needs clicking Apply)
            if "/viewjob" in current_url.lower() or "/jobs" in current_url.lower():
                try:
                    # 1. Check for offsite company apply button
                    offsite_btn = await page.query_selector(
                        "button:has-text('Apply on company site'), a:has-text('Apply on company site'), a[href*='apply']:has-text('Apply on company')"
                    )
                    if offsite_btn and await offsite_btn.is_visible():
                        logger.info("   -> Indeed offsite application detected: Following external apply link...")
                        href = await offsite_btn.get_attribute("href")
                        if href and href.startswith("http") and "indeed.com" not in href:
                            await page.goto(href, wait_until="domcontentloaded", timeout=20000)
                            return page, self.detector.detect(page.url)
                        else:
                            await offsite_btn.click()
                            await asyncio.sleep(3)
                            if hasattr(page, "context") and len(page.context.pages) > 1:
                                page = page.context.pages[-1]
                                await page.bring_to_front()
                            return page, self.detector.detect(page.url)

                    # 2. Check for Indeed Apply button
                    apply_btn = await page.query_selector(
                        "button#indeedApplyButton, [data-gnav-element-name='indeedApply'], .ia-IndeedApplyButton, button:has-text('Apply now'), a:has-text('Apply now')"
                    )
                    if apply_btn and await apply_btn.is_visible():
                        logger.info("   -> Indeed Apply detected: Clicking 'Apply now'...")
                        await apply_btn.click()
                        await asyncio.sleep(3)
                except Exception as e:
                    logger.debug(f"Indeed unwrap exception: {e}")

        # Check if browser opened a new tab/window during interaction
        if hasattr(page, "context") and len(page.context.pages) > 1:
            page = page.context.pages[-1]
            try:
                await page.bring_to_front()
            except Exception:
                pass
            platform = self.detector.detect(page.url)

        logger.info(f"🎯 Resolved Application Target: [{platform.upper()}] at {page.url[:80]}")
        return page, platform

    async def _process_page(self, page, application_url: str, resume_path: str, cover_letter_path: Optional[str], dry_run: bool, candidate: dict) -> Dict[str, Any]:
        """Performs form resolution, data mapping, screenshot capture, and submission handling."""
        page, platform = await self._resolve_application_page(page, application_url)
        if platform == "needs_login":
            return {"status": "needs_login", "platform": "linkedin", "message": "Sign-in required to access application"}

        # Wait for form or input elements to be rendered (handles React, Lever, Ashby, Indeed hydration)
        try:
            await page.wait_for_selector(
                "form, input[type='text'], input[type='email'], input[name='name'], [data-qa='name-input'], #first_name, .application-form, [data-automation-id='applyFlowPage'], [data-automation-id='progressBar'], iframe[src*='indeedapply'], #indeedApplyButton, [data-testid*='ContactInfo']",
                timeout=7000
            )
        except Exception:
            pass
        await asyncio.sleep(1.0)

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

        # Handle multi-step wizard if present (e.g. Workday, Indeed, Easy Apply)
        steps_navigated = 0
        max_steps = 7 if platform in ["workday", "indeed"] else 4
        while steps_navigated < max_steps:
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
            try:
                await page.screenshot(path=str(screenshot_path), full_page=True)
            except Exception:
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
    parser.add_argument('--test-greenhouse', action='store_true', help='Run visual inspection test on a verified live Greenhouse posting')
    args = parser.parse_args()

    if args.test_greenhouse:
        target_url = args.url or "https://job-boards.greenhouse.io/gitlab/jobs/8556658002"
        logger.info(f"🧪 [TEST GREENHOUSE] Initiating headful visual verification on: {target_url}")
        applier = AutoApplier(mode='semi-auto', browser_type=args.browser, profile_dir=args.profile_dir)
        asyncio.run(applier.apply(target_url, args.resume, args.cover_letter, dry_run=True))
    elif args.url:
        applier = AutoApplier(mode=args.mode, browser_type=args.browser, profile_dir=args.profile_dir)
        asyncio.run(applier.apply(args.url, args.resume, args.cover_letter, args.dry_run))
    else:
        asyncio.run(run_autofill_daemon(mode=args.mode, browser_type=args.browser, profile_dir=args.profile_dir, dry_run=args.dry_run))
