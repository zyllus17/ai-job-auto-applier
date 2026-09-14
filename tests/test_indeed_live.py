import pytest
import asyncio
from pathlib import Path
from tools.browser_autofill import ATSDetector, FormFiller, AutoApplier
from tools.humanizer import HumanBehavior

REPO_ROOT = Path(__file__).parent.parent.resolve()

def test_indeed_url_detection():
    detector = ATSDetector()
    assert detector.detect("https://www.indeed.com/viewjob?jk=baa8cd7a6efd8f7f") == "indeed"
    assert detector.detect("https://in.indeed.com/viewjob?jk=78910") == "indeed"
    assert detector.detect("https://www.indeed.com/m/viewjob?jk=12345") == "indeed"
    assert detector.detect("https://smartapply.indeed.com/beta/indeedapply/form/contact-info") == "indeed"
    assert detector.detect("https://apply.indeed.com/indeedapply/resume") == "indeed"
    assert detector.detect("https://www.indeed.com/jobs?q=python&l=remote&vjk=abc12345") == "indeed"

@pytest.mark.asyncio
async def test_indeed_mock_apply_flow():
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
        "expected_salary": 100000,
        "work_authorization": {"requires_sponsorship": True, "authorized_india": True},
        "eeo_responses": {
            "gender": "Male",
            "race_ethnicity": "Decline to self-identify",
            "veteran_status": "I am not a protected veteran",
            "disability_status": "I do not wish to answer"
        }
    }

    mock_html = """
    <html>
    <head><title>Indeed Apply - Mock Application</title></head>
    <body>
      <div id="ia-container" class="ia-ApplyPage">
        <!-- Step 1: Contact Information -->
        <div id="step-contact" class="ia-Step">
          <h2>Contact information</h2>
          <div>
            <label for="input-firstName">First Name</label>
            <input type="text" id="input-firstName" name="firstName" />
          </div>
          <div>
            <label for="input-lastName">Last Name</label>
            <input type="text" id="input-lastName" name="lastName" />
          </div>
          <div>
            <label for="input-email">Email</label>
            <input type="email" id="input-email" name="email" />
          </div>
          <div>
            <label for="input-phoneNumber">Phone number</label>
            <input type="tel" id="input-phoneNumber" name="phoneNumber" />
          </div>
          <div>
            <label for="input-location">City, State</label>
            <input type="text" id="input-location" data-testid="Location" />
          </div>
        </div>

        <!-- Step 2: Resume -->
        <div id="step-resume" class="ia-Step">
          <h2>Add a resume</h2>
          <input type="file" id="resume-file" data-testid="resume" />
        </div>

        <!-- Step 3: Screening Questions -->
        <div id="step-questions" class="ia-Step">
          <h2>Questions from employer</h2>
          <div class="ia-Question">
            <label for="q-exp">How many years of work experience do you have with Python?</label>
            <input type="number" id="q-exp" name="experience" />
          </div>
          <fieldset class="ia-Question">
            <legend>Will you now or in the future require visa sponsorship?</legend>
            <label><input type="radio" name="sponsorship" value="yes" id="sp-yes" /> Yes</label>
            <label><input type="radio" name="sponsorship" value="no" id="sp-no" /> No</label>
          </fieldset>
          <fieldset class="ia-Question">
            <legend>Are you legally authorized to work?</legend>
            <label><input type="radio" name="authorized" value="yes" id="auth-yes" /> Yes</label>
            <label><input type="radio" name="authorized" value="no" id="auth-no" /> No</label>
          </fieldset>
        </div>

        <!-- Footer -->
        <div id="ia-footer">
          <button type="button" class="ia-continueButton" data-testid="continue-button">Continue</button>
          <button type="submit" data-testid="submit-application" style="display:none;">Submit your application</button>
        </div>
      </div>
    </body>
    </html>
    """

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(mock_html)

        humanizer = HumanBehavior(page)
        filler = FormFiller(page, "indeed", candidate, humanizer)

        success = await filler.fill_form()
        assert success is True

        # Assert Contact Info Filled
        assert await page.input_value("#input-firstName") == "Maruf"
        assert await page.input_value("#input-lastName") == "Hassan"
        assert await page.input_value("#input-email") == "csengineer.maruf@gmail.com"
        assert await page.input_value("#input-phoneNumber") == "7980356852"
        assert await page.input_value("#input-location") == "Kolkata"

        # Assert Screening Questions Filled
        assert await page.input_value("#q-exp") == "5"
        assert await page.is_checked("#sp-yes") is True
        assert await page.is_checked("#auth-yes") is True

        # Assert Continue Button is detectable
        cont_btn = await page.query_selector("[data-testid='continue-button']")
        assert cont_btn is not None

        await browser.close()

@pytest.mark.asyncio
async def test_indeed_iframe_resolution():
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
        "city": "Kolkata",
        "location": "Kolkata, India",
        "resume_pdf_path": str(REPO_ROOT / "cv" / "main_example.pdf"),
        "years_experience": 5,
        "work_authorization": {"requires_sponsorship": True}
    }

    # Host page with embedded Indeed Apply iframe
    host_html = """
    <html>
    <head><title>Job View with Indeed Apply Modal</title></head>
    <body>
      <div id="viewJobSSRRoot">
        <h1>Senior Python Developer</h1>
        <button id="indeedApplyButton">Apply now</button>
      </div>

      <iframe id="indeedapply-modal-preload-iframe" name="indeedapply-modal-preload-iframe" src="about:blank" title="Job application form"></iframe>
    </body>
    </html>
    """

    iframe_inner_html = """
    <html>
    <body>
      <div id="smartapply-container">
        <h2>Contact information</h2>
        <input type="text" id="input-firstName" />
        <input type="text" id="input-lastName" />
        <input type="email" id="input-email" />
        <input type="tel" id="input-phoneNumber" />
        <input type="text" id="input-location" />
        <button type="button" data-testid="continue-button">Continue</button>
      </div>
    </body>
    </html>
    """

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(host_html)

        # Set content inside the iframe
        iframe_handle = await page.query_selector("#indeedapply-modal-preload-iframe")
        frame = await iframe_handle.content_frame()
        await frame.set_content(iframe_inner_html)

        humanizer = HumanBehavior(page)
        filler = FormFiller(page, "indeed", candidate, humanizer)

        # Assert active scope resolves to the iframe!
        scope = await filler._get_scope()
        assert scope != page, "Scope should resolve to Indeed iframe"

        # Execute fill
        success = await filler.fill_form()
        assert success is True

        # Assert elements inside the iframe were filled!
        assert await frame.input_value("#input-firstName") == "Maruf"
        assert await frame.input_value("#input-lastName") == "Hassan"
        assert await frame.input_value("#input-email") == "csengineer.maruf@gmail.com"
        assert await frame.input_value("#input-phoneNumber") == "7980356852"
        assert await frame.input_value("#input-location") == "Kolkata"

        # Assert advance wizard detects continue button inside iframe
        advanced = await filler.advance_wizard_step()
        assert advanced is True

        await browser.close()
