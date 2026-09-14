import pytest
import asyncio
from pathlib import Path
from tools.browser_autofill import ATSDetector, FormFiller
from tools.humanizer import HumanBehavior

REPO_ROOT = Path(__file__).parent.parent.resolve()

def test_greenhouse_url_detection():
    detector = ATSDetector()
    assert detector.detect("https://boards.greenhouse.io/gitlab/jobs/8556658002") == "greenhouse"
    assert detector.detect("https://job-boards.greenhouse.io/gitlab/jobs/8556658002") == "greenhouse"
    assert detector.detect("https://board.greenhouse.io/vanta/jobs/12345") == "greenhouse"

@pytest.mark.asyncio
async def test_greenhouse_classic_form_structure():
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
        "linkedin_url": "https://linkedin.com/in/maruf-hassan",
        "github_url": "https://github.com/zyllus17",
        "resume_pdf_path": "cv/main_example.pdf",
        "work_authorization": {"requires_sponsorship": True}
    }

    mock_html = """
    <html>
    <body>
      <form id="application_form">
        <input type="text" id="first_name" name="first_name" />
        <input type="text" id="last_name" name="last_name" />
        <input type="email" id="email" name="email" />
        <input type="tel" id="phone" name="phone" />
        <input type="file" id="resume" name="resume" />
        <textarea id="cover_letter_text" name="cover_letter_text"></textarea>
        <label for="sponsorship_select">Will you require visa sponsorship?</label>
        <select id="sponsorship_select" name="sponsorship">
          <option value="">Select...</option>
          <option value="no">No</option>
          <option value="yes">Yes</option>
        </select>
        <input type="text" id="job_application_answers_attributes_0_text_value" autocomplete="custom-question-linkedin-profile" />
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
        assert await page.input_value("#job_application_answers_attributes_0_text_value") == "https://linkedin.com/in/maruf-hassan"
        assert await page.input_value("#sponsorship_select") == "yes"

        submit_btn = await page.query_selector("button#submit_app, button[type='submit']")
        assert submit_btn is not None

        await browser.close()

@pytest.mark.asyncio
async def test_greenhouse_modern_remix_form_structure():
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
        "linkedin_url": "https://linkedin.com/in/maruf-hassan",
        "github_url": "https://github.com/zyllus17",
        "portfolio_url": "https://marufhassan.dev",
        "resume_pdf_path": "cv/main_example.pdf",
        "work_authorization": {"requires_sponsorship": True},
        "eeo_responses": {
            "gender": "Male",
            "veteran_status": "I am not a protected veteran",
            "disability_status": "I do not wish to answer"
        }
    }

    # Modern Greenhouse (job-boards.greenhouse.io) DOM pattern
    mock_html = """
    <html>
    <body>
      <main>
        <button type="button" aria-label="Apply" class="btn btn--pill">Apply</button>
        <form id="job-application-form">
          <input id="first_name" type="text" aria-label="First Name" />
          <input id="last_name" type="text" aria-label="Last Name" />
          <input id="email" type="text" aria-label="Email" />
          <input id="phone" type="tel" aria-label="Phone" />
          <input id="resume" type="file" />
          <input id="question_36622854002" type="text" aria-label="LinkedIn Profile" />
          <input id="question_36622855002" type="text" aria-label="What's the name you'd prefer us to use throughout the interview process?" />
          <input id="question_36622856002" type="text" aria-label="Will you now or in the future require visa sponsorship?" />
          <div class="select__container">
            <label id="gender-label" for="gender">Gender</label>
            <div class="select__control" id="gender_ctrl">
              <input id="gender" class="select__input" />
            </div>
            <div class="select__option" role="option">Female</div>
            <div class="select__option" role="option">Male</div>
            <div class="select__option" role="option">Decline To Self Identify</div>
          </div>
          <button type="submit" class="btn btn--pill">Submit application</button>
        </form>
      </main>
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

        # Check standard fields
        assert await page.input_value("#first_name") == "Maruf"
        assert await page.input_value("#last_name") == "Hassan"
        assert await page.input_value("#email") == "csengineer.maruf@gmail.com"
        assert await page.input_value("#phone") == "+91 79803 56852"

        # Check custom ARIA-labeled questions
        assert await page.input_value("#question_36622854002") == "https://linkedin.com/in/maruf-hassan"
        assert await page.input_value("#question_36622855002") == "Maruf Hassan"
        assert await page.input_value("#question_36622856002") == "Yes"

        # Verify submit button matches
        plat_sel = filler.selectors.get("greenhouse", {})
        submit_sel = plat_sel.get("submit_button")
        submit_btn = await page.query_selector(submit_sel)
        assert submit_btn is not None
        btn_text = (await submit_btn.inner_text()).strip()
        assert "Submit application" in btn_text

        await browser.close()
