import pytest
import asyncio
from pathlib import Path
from tools.browser_autofill import ATSDetector, FormFiller
from tools.humanizer import HumanBehavior

REPO_ROOT = Path(__file__).parent.parent.resolve()

def test_ashby_url_detection():
    detector = ATSDetector()
    assert detector.detect("https://jobs.ashbyhq.com/won.ai/b6b87c60-8f41-4fa1-939b-2cc1ba2598c7") == "ashby"
    assert detector.detect("https://jobs.ashbyhq.com/won.ai/b6b87c60-8f41-4fa1-939b-2cc1ba2598c7/application") == "ashby"
    assert detector.detect("https://jobs.ashbyhq.com/thirdlaw/146d2379-88e4-4073-9c2a-1899871fdaeb?utm_source=freehire.me") == "ashby"
    assert detector.detect("https://jobs.ashbyhq.com/retool/01234567-89ab-cdef-0123-456789abcdef") == "ashby"

@pytest.mark.asyncio
async def test_ashby_full_form_structure():
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
        "resume_pdf_path": "cv/main_example.pdf",
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
    <head><title>Mock Ashby Job Application</title></head>
    <body>
      <div class="ashby-job-posting-right-pane">
        <!-- Top Autofill widget (must not be confused with real resume upload) -->
        <div class="ashby-application-form-autofill-pane">
          <input type="file" id="autofill-file" />
        </div>

        <form class="ashby-application-form-container">
          <!-- Standard Core Fields with _systemfield IDs -->
          <div class="ashby-application-form-field-entry">
            <label for="_systemfield_name">First & Last Name</label>
            <input type="text" id="_systemfield_name" name="_systemfield_name" />
          </div>

          <div class="ashby-application-form-field-entry">
            <label for="_systemfield_email">Email</label>
            <input type="email" id="_systemfield_email" name="_systemfield_email" />
          </div>

          <div class="ashby-application-form-field-entry">
            <label for="_systemfield_phone">Phone</label>
            <input type="tel" id="_systemfield_phone" name="_systemfield_phone" />
          </div>

          <div class="ashby-application-form-field-entry">
            <label for="_systemfield_resume">Resume</label>
            <input type="file" id="_systemfield_resume" name="_systemfield_resume" />
          </div>

          <!-- Location Autocomplete Input -->
          <div class="ashby-application-form-field-entry">
            <label for="loc-input">Location</label>
            <input type="text" id="loc-input" placeholder="Start typing..." />
          </div>

          <!-- Yes/No Button Widget -->
          <div class="ashby-application-form-field-entry">
            <label>Are you based in or willing to relocate to Medellin Colombia?</label>
            <div class="ashby-application-form-input-yesno">
              <button type="button">Yes</button>
              <button type="button">No</button>
              <input type="checkbox" name="relocate_cb" style="display:none" />
            </div>
          </div>

          <!-- Radio Groups: Salary Cadence -->
          <fieldset class="ashby-application-form-input-radio-group">
            <label class="ashby-application-form-question-title">Desired Salary Range Format</label>
            <div class="ashby-application-form-input-radio-group-option">
              <input type="radio" id="sal-0" name="salary_format" value="Annual" />
              <label for="sal-0">Annual</label>
            </div>
            <div class="ashby-application-form-input-radio-group-option">
              <input type="radio" id="sal-1" name="salary_format" value="Monthly" />
              <label for="sal-1">Monthly</label>
            </div>
          </fieldset>

          <!-- Radio Groups: Work Type -->
          <fieldset class="ashby-application-form-input-radio-group">
            <label class="ashby-application-form-question-title">Work Type Preference</label>
            <div class="ashby-application-form-input-radio-group-option">
              <input type="radio" id="wt-0" name="work_type" value="Full-time" />
              <label for="wt-0">Full-time</label>
            </div>
            <div class="ashby-application-form-input-radio-group-option">
              <input type="radio" id="wt-1" name="work_type" value="Contract" />
              <label for="wt-1">Contract / Freelance</label>
            </div>
          </fieldset>

          <!-- Radio Groups: English Proficiency -->
          <fieldset class="ashby-application-form-input-radio-group">
            <label class="ashby-application-form-question-title">English Proficiency</label>
            <div class="ashby-application-form-input-radio-group-option">
              <input type="radio" id="eng-0" name="english" value="Native / Fluent" />
              <label for="eng-0">Native / Fluent</label>
            </div>
            <div class="ashby-application-form-input-radio-group-option">
              <input type="radio" id="eng-1" name="english" value="Professional working proficiency" />
              <label for="eng-1">Professional working proficiency</label>
            </div>
          </fieldset>

          <!-- Radio Groups: Experience Range -->
          <fieldset class="ashby-application-form-input-radio-group">
            <label class="ashby-application-form-question-title">Years of Experience</label>
            <div class="ashby-application-form-input-radio-group-option">
              <input type="radio" id="yoe-0" name="yoe" value="0-2" />
              <label for="yoe-0">0-2</label>
            </div>
            <div class="ashby-application-form-input-radio-group-option">
              <input type="radio" id="yoe-1" name="yoe" value="3-5" />
              <label for="yoe-1">3-5</label>
            </div>
            <div class="ashby-application-form-input-radio-group-option">
              <input type="radio" id="yoe-2" name="yoe" value="6-10" />
              <label for="yoe-2">6-10</label>
            </div>
          </fieldset>

          <!-- Custom UUID Fields -->
          <div class="ashby-application-form-field-entry">
            <label for="custom-uuid-notice">Availability / Notice Period</label>
            <input type="text" id="custom-uuid-notice" name="custom-uuid-notice" />
          </div>

          <div class="ashby-application-form-field-entry">
            <label for="custom-uuid-linkedin">LinkedIn Profile</label>
            <input type="url" id="custom-uuid-linkedin" name="custom-uuid-linkedin" />
          </div>

          <div class="ashby-application-form-field-entry">
            <label for="custom-uuid-salary">Desired Salary Range in USD</label>
            <input type="number" id="custom-uuid-salary" name="custom-uuid-salary" />
          </div>

          <div class="ashby-application-form-field-entry">
            <label for="custom-uuid-why">Why are you interested in working at this company?</label>
            <textarea id="custom-uuid-why" name="custom-uuid-why"></textarea>
          </div>

          <!-- Submit Button with Ashby canonical class -->
          <button type="submit" class="ashby-application-form-submit-button">Submit Application</button>
        </form>
      </div>
    </body>
    </html>
    """

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(mock_html)

        humanizer = HumanBehavior(page)
        filler = FormFiller(page, "ashby", candidate, humanizer)

        success = await filler.fill_form()
        assert success is True

        # Assert Core Standard Fields
        assert await page.input_value("#_systemfield_name") == "Maruf Hassan"
        assert await page.input_value("#_systemfield_email") == "csengineer.maruf@gmail.com"
        assert await page.input_value("#_systemfield_phone") == "+91 79803 56852"

        # Assert Custom UUID Fields via label resolution
        assert await page.input_value("#custom-uuid-notice") == "2 weeks"
        assert await page.input_value("#custom-uuid-linkedin") == "https://linkedin.com/in/maruf-hassan"
        assert await page.input_value("#custom-uuid-salary") == "100000"
        why_val = await page.input_value("#custom-uuid-why")
        assert len(why_val) > 20 and "experience" in why_val.lower()

        # Assert Radios Checked
        assert await page.is_checked("#sal-0") is True   # Annual
        assert await page.is_checked("#wt-0") is True    # Full-time
        assert await page.is_checked("#eng-0") is True   # Native / Fluent
        assert await page.is_checked("#yoe-1") is True   # 3-5

        # Assert Submit button found
        submit_btn = await page.query_selector("button.ashby-application-form-submit-button, button:has-text('Submit Application')")
        assert submit_btn is not None
        assert await submit_btn.is_visible() is True

        await browser.close()
