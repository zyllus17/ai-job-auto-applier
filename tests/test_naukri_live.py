import pytest
import asyncio
from pathlib import Path
from tools.browser_autofill import ATSDetector, FormFiller, AutoApplier
from tools.humanizer import HumanBehavior

REPO_ROOT = Path(__file__).parent.parent.resolve()

def test_naukri_url_detection():
    detector = ATSDetector()
    assert detector.detect("https://www.naukri.com/job-listings-python-genai-developer-tata-consultancy-services-chennai-4-to-9-years-300826004292") == "naukri"
    assert detector.detect("https://www.naukri.com/python-developer-jobs-in-kolkata") == "naukri"
    assert detector.detect("https://www.naukri.com/jobs-in-bengaluru") == "naukri"
    assert detector.detect("https://www.naukri.com/desc/python-engineer-12345") == "naukri"
    assert detector.detect("https://naukri.com/viewjob?id=999") == "naukri"

@pytest.mark.asyncio
async def test_naukri_mock_apply_flow():
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        pytest.skip("Playwright not installed")

    candidate = {
        "first_name": "Maruf",
        "last_name": "Hassan",
        "full_name": "Maruf Hassan",
        "email": "csengineer.maruf@gmail.com",
        "phone": "+91 79803 56852",
        "country": "India",
        "city": "Kolkata",
        "location": "Kolkata, West Bengal, India",
        "current_company": "Floor Boss",
        "current_title": "AI Automation Engineer",
        "linkedin_url": "https://linkedin.com/in/maruf-hassan",
        "github_url": "https://github.com/zyllus17",
        "resume_pdf_path": str(REPO_ROOT / "cv" / "main_example.pdf"),
        "years_experience": 5,
        "notice_period_days": 15,
        "notice_period_text": "15 Days or less",
        "current_ctc_lakhs": 12.0,
        "expected_ctc_lakhs": 18.0,
        "work_authorization": {"requires_sponsorship": True, "authorized_india": True}
    }

    mock_html = """
    <!DOCTYPE html>
    <html>
    <head><title>Python Developer - Mock Naukri Application</title></head>
    <body>
      <div id="root">
        <!-- Main Job Header Area -->
        <section id="job_header">
          <h1>Python GenAI Developer</h1>
          <button id="apply-button" class="apply-button">Apply</button>
        </section>

        <!-- Naukri Screening Questionnaire Drawer -->
        <div class="chatbot_drawer apply-drawer">
          <h2>Screening Questions</h2>
          
          <!-- Contact info -->
          <div>
            <label>Name</label>
            <input type="text" name="name" id="user-name" />
          </div>
          <div>
            <label>Email ID</label>
            <input type="email" name="email" id="user-email" />
          </div>
          <div>
            <label>Mobile Number</label>
            <input type="tel" name="mobile" id="user-mobile" />
          </div>

          <!-- Total Experience -->
          <div>
            <label>Total Experience (Years)</label>
            <input type="number" id="user-exp" placeholder="Total Experience in years" />
          </div>

          <!-- Notice Period -->
          <div>
            <label>Notice Period</label>
            <select name="notice" id="user-notice">
              <option value="">Select Notice Period</option>
              <option value="15">15 Days or less</option>
              <option value="30">1 Month / 30 Days</option>
              <option value="60">2 Months</option>
            </select>
          </div>

          <!-- Current CTC -->
          <div>
            <label>Current CTC (in Lakhs)</label>
            <input type="text" id="currentCtc" placeholder="Enter Current CTC" />
          </div>

          <!-- Expected CTC -->
          <div>
            <label>Expected CTC (in Lakhs)</label>
            <input type="text" id="expectedCtc" placeholder="Enter Expected CTC" />
          </div>

          <!-- Current Location -->
          <div>
            <label>Current Location</label>
            <input type="text" id="location" placeholder="Enter Current Location" />
          </div>

          <!-- Radio Question: Relocation -->
          <div class="question-group">
            <p>Are you willing to relocate or commute for this role?</p>
            <label><input type="radio" name="relocate" value="yes" id="relocate-yes" /> Yes</label>
            <label><input type="radio" name="relocate" value="no" id="relocate-no" /> No</label>
          </div>

          <!-- Resume Upload -->
          <div>
            <label>Attach Resume</label>
            <input type="file" id="resume-file" name="resume" />
          </div>

          <!-- Save and Apply Button -->
          <div>
            <button type="button" id="save-apply-btn">Save & Apply</button>
          </div>
        </div>
      </div>
    </body>
    </html>
    """

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        await page.set_content(mock_html)

        humanizer = HumanBehavior(page)
        filler = FormFiller(page, "naukri", candidate, humanizer)

        success = await filler.fill_form()
        assert success is True

        # Assert Contact Information
        name_val = await page.input_value("input#user-name")
        assert name_val == "Maruf Hassan"

        email_val = await page.input_value("input#user-email")
        assert email_val == "csengineer.maruf@gmail.com"

        mobile_val = await page.input_value("input#user-mobile")
        assert mobile_val == "+91 79803 56852"

        # Assert Experience
        exp_val = await page.input_value("input#user-exp")
        assert exp_val == "5"

        # Assert Notice Period Select
        notice_val = await page.input_value("select#user-notice")
        assert notice_val == "15"

        # Assert Current & Expected CTC
        c_ctc = await page.input_value("input#currentCtc")
        assert c_ctc == "12.0"

        e_ctc = await page.input_value("input#expectedCtc")
        assert e_ctc == "18.0"

        # Assert Location
        loc_val = await page.input_value("input#location")
        assert "Kolkata" in loc_val

        # Assert Radio Question
        reloc_checked = await page.is_checked("input#relocate-yes")
        assert reloc_checked is True

        # Assert Wizard Step / Save & Apply Button
        advanced = await filler.advance_wizard_step()
        assert advanced is True

        await browser.close()

@pytest.mark.asyncio
async def test_naukri_offsite_apply_unwrap():
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        pytest.skip("Playwright not installed")

    mock_html = """
    <html>
    <head><title>Enterprise Job - Naukri</title></head>
    <body>
      <div id="job_header">
        <h1>Senior Backend Engineer</h1>
        <a id="company-site-button" href="https://boards.greenhouse.io/enterprise/jobs/99999">Apply on company site</a>
      </div>
    </body>
    </html>
    """

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        context = await browser.new_context()
        page = await context.new_page()
        # Mock network routes for isolation
        await page.route("https://www.naukri.com/**", lambda route: route.fulfill(status=200, content_type="text/html", body=mock_html))
        await page.route("https://boards.greenhouse.io/**", lambda route: route.fulfill(status=200, content_type="text/html", body="<html><body><h1>Greenhouse Form</h1></body></html>"))

        applier = AutoApplier(mode="semi-auto")
        resolved_page, detected_platform = await applier._resolve_application_page(page, "https://www.naukri.com/job-listings-enterprise-99999")

        # Confirm offsite unwrapping detected Greenhouse target platform
        assert detected_platform == "greenhouse"
        assert "greenhouse.io" in resolved_page.url

        await browser.close()
