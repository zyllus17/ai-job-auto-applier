import pytest
import asyncio
import json
from pathlib import Path
from tools.browser_autofill import ATSDetector, CompanyFilter, FormFiller
from tools.humanizer import HumanBehavior

REPO_ROOT = Path(__file__).parent.parent.resolve()

def test_ats_detection():
    detector = ATSDetector()
    assert detector.detect("https://boards.greenhouse.io/stripe/jobs/12345") == "greenhouse"
    assert detector.detect("https://board.greenhouse.io/vanta/jobs/6789") == "greenhouse"
    assert detector.detect("https://jobs.lever.co/jobgether/75d5f3e3/apply") == "lever"
    assert detector.detect("https://jobs.ashbyhq.com/openai/98765") == "ashby"
    assert detector.detect("https://mycompany.myworkdayjobs.com/en-US/careers/job/123") == "workday"
    assert detector.detect("https://careers.smartrecruiters.com/Acme/123") == "smartrecruiters"
    assert detector.detect("https://www.linkedin.com/jobs/view/123456789/?apply=true") == "linkedin"
    assert detector.detect("https://www.indeed.com/apply/123") == "indeed"
    assert detector.detect("https://www.naukri.com/job-listings-123") == "naukri"
    assert detector.detect("https://www.monster.com/job-openings/123") == "monster"
    assert detector.detect("https://acme.applytojob.com/apply/123") == "jazzhr"
    assert detector.detect("https://unknowncompany.com/career") == "generic"

def test_company_filter():
    profile = {"current_company": "Floor Boss"}
    filter_obj = CompanyFilter(profile)
    assert filter_obj.should_skip("Floor Boss") is True
    assert filter_obj.should_skip("floor boss inc") is True
    assert filter_obj.should_skip("The Floor Boss Company") is True
    assert filter_obj.should_skip("Google") is False
    assert filter_obj.should_skip("Microsoft") is False
    assert filter_obj.should_skip("") is False

def test_ats_selectors_syntax_integrity():
    selectors_path = REPO_ROOT / "tools" / "ats_selectors.json"
    assert selectors_path.exists()
    with open(selectors_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    platforms = data.get("platforms", [])
    assert len(platforms) >= 8

    # Ensure no platform has invalid 'aria-label=' without CSS brackets
    for p in platforms:
        pname = p.get("platform_name")
        for field, sel in p.get("selectors", {}).items():
            if sel:
                assert not sel.strip().startswith("aria-label="), (
                    f"Platform {pname} field {field} has raw aria-label: {sel}. Must use [aria-label=...]"
                )

@pytest.mark.asyncio
async def test_form_filler_selector_sanitization():
    filler = FormFiller(page=None, platform="generic", candidate={}, humanizer=None)
    sanitized = filler._sanitize_selector("aria-label=First Name, input[name='first']")
    assert "[aria-label*='First Name' i]" in sanitized
    assert "input[name='first']" in sanitized

@pytest.mark.asyncio
async def test_lever_mock_form_filling():
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        pytest.skip("Playwright not installed in test environment")

    candidate = {
        "first_name": "Maruf",
        "last_name": "Hassan",
        "full_name": "Maruf Hassan",
        "email": "csengineer.maruf@gmail.com",
        "phone": "+91 79803 56852",
        "current_company": "Floor Boss",
        "current_title": "AI Automation Engineer",
        "location": "Kolkata, West Bengal, India"
    }

    mock_html = """
    <html>
    <body>
      <form id="application-form">
        <input type="text" name="name" data-qa="name-input" />
        <input type="email" name="email" data-qa="email-input" />
        <input type="text" name="phone" data-qa="phone-input" />
        <input type="text" name="org" data-qa="org-input" />
        <input type="text" name="location" data-qa="location-input" />
        <button id="btn-submit" type="button" class="postings-btn">Submit application</button>
      </form>
    </body>
    </html>
    """

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(mock_html)

        humanizer = HumanBehavior(page)
        filler = FormFiller(page, "lever", candidate, humanizer)
        await filler.fill_form()

        # Check values
        name_val = await page.input_value("input[name='name']")
        email_val = await page.input_value("input[name='email']")
        phone_val = await page.input_value("input[name='phone']")
        org_val = await page.input_value("input[name='org']")
        loc_val = await page.input_value("input[name='location']")

        assert name_val == "Maruf Hassan"
        assert email_val == "csengineer.maruf@gmail.com"
        assert phone_val == "+91 79803 56852"
        assert org_val == "Floor Boss"
        assert loc_val == "Kolkata, West Bengal, India"

        await browser.close()

@pytest.mark.asyncio
async def test_greenhouse_mock_form_filling():
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        pytest.skip("Playwright not installed in test environment")

    candidate = {
        "first_name": "Maruf",
        "last_name": "Hassan",
        "email": "csengineer.maruf@gmail.com",
        "phone": "+91 79803 56852",
        "current_company": "Floor Boss"
    }

    mock_html = """
    <html>
    <body>
      <form id="application_form">
        <input type="text" id="first_name" name="first_name" />
        <input type="text" id="last_name" name="last_name" />
        <input type="email" id="email" name="email" />
        <input type="text" id="phone" name="phone" />
        <button id="submit_app" type="submit">Submit Application</button>
      </form>
    </body>
    </html>
    """

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(mock_html)

        humanizer = HumanBehavior(page)
        filler = FormFiller(page, "greenhouse", candidate, humanizer)
        await filler.fill_form()

        assert await page.input_value("#first_name") == "Maruf"
        assert await page.input_value("#last_name") == "Hassan"
        assert await page.input_value("#email") == "csengineer.maruf@gmail.com"
        assert await page.input_value("#phone") == "+91 79803 56852"

        await browser.close()
