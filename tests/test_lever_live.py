import pytest
import asyncio
from pathlib import Path
from tools.browser_autofill import ATSDetector, FormFiller
from tools.humanizer import HumanBehavior

REPO_ROOT = Path(__file__).parent.parent.resolve()

def test_lever_url_detection():
    detector = ATSDetector()
    assert detector.detect("https://jobs.lever.co/magnetforensics/7a86a5a7-79a6-41fd-8ac4-e668ae34665f") == "lever"
    assert detector.detect("https://jobs.lever.co/magnetforensics/7a86a5a7-79a6-41fd-8ac4-e668ae34665f/apply") == "lever"
    assert detector.detect("https://jobs.lever.co/jobgether/ae0af345-9692-4cea-9e9a-0e9d851bcc1a?utm_source=freehire.me") == "lever"

@pytest.mark.asyncio
async def test_lever_full_form_structure():
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
        "cover_letter_pdf_path": "cover_letters/cover_example.pdf",
        "work_authorization": {"requires_sponsorship": False, "authorized_india": True},
        "eeo_responses": {
            "gender": "Male",
            "race_ethnicity": "Decline to self-identify",
            "veteran_status": "I am not a protected veteran",
            "disability_status": "I do not wish to answer"
        }
    }

    mock_html = """
    <html>
    <body>
      <form id="application-form">
        <input type="file" id="resume-upload-input" name="resume" />
        <input type="text" name="name" data-qa="name-input" />
        <input type="email" name="email" data-qa="email-input" />
        <input type="text" name="phone" data-qa="phone-input" />
        <input type="text" name="location" id="location-input" />
        <input type="text" name="org" data-qa="org-input" />
        <input type="text" name="urls[LinkedIn]" />
        <input type="text" name="urls[GitHub]" />
        <textarea name="comments"></textarea>

        <!-- Custom Questions -->
        <div class="application-question">
          <div class="text">How did you hear about us? ✱</div>
          <label><input type="checkbox" name="field0" value="LinkedIn" /> LinkedIn</label>
          <label><input type="checkbox" name="field0" value="Other" /> Other</label>
        </div>

        <div class="application-question">
          <div class="text">Have you previously been employed by this company? ✱</div>
          <label><input type="checkbox" name="field1" value="Yes" /> Yes</label>
          <label><input type="checkbox" name="field1" value="No" /> No</label>
        </div>

        <div class="application-question">
          <div class="text">Please enter the country you are legally registered to work in. ✱</div>
          <input type="text" name="country_field" />
        </div>

        <div class="application-question">
          <div class="text">Will you require sponsorship to work from your country of residence? ✱</div>
          <select name="sponsorship_field">
            <option value="">Select...</option>
            <option value="Yes">Yes</option>
            <option value="No">No</option>
          </select>
        </div>

        <div class="application-question">
          <div class="text">What is your notice period to begin working? ✱</div>
          <select name="notice_field">
            <option value="">Select...</option>
            <option value="1-2 weeks">1-2 weeks</option>
            <option value="4+ weeks">4+ weeks</option>
          </select>
        </div>

        <div class="application-question">
          <div class="text">I have read and agree to the Applicant Privacy Notice ✱</div>
          <label><input type="checkbox" name="privacy_field" value="Yes" /> I agree</label>
        </div>

        <!-- EEO Section -->
        <div class="application-question">
          <div class="text">Gender</div>
          <select name="eeo[gender]">
            <option value="">Select ...</option>
            <option value="Male">Male</option>
            <option value="Female">Female</option>
            <option value="Decline">Decline to self-identify</option>
          </select>
        </div>

        <div class="application-question">
          <div class="text">Race</div>
          <label><input type="radio" name="eeo[race]" value="Asian (Not Hispanic or Latino)" /> Asian</label>
          <label><input type="radio" name="eeo[race]" value="Decline to self-identify" /> Decline to self-identify</label>
        </div>

        <div class="application-question">
          <div class="text">Veteran status</div>
          <select name="eeo[veteran]">
            <option value="">Select ...</option>
            <option value="I identify as one or more classifications">I identify as one or more classifications</option>
            <option value="I am not a Protected Veteran">I am not a Protected Veteran</option>
          </select>
        </div>

        <div class="application-question">
          <div class="text">Disability status</div>
          <select name="eeo[disability]">
            <option value="">Select ...</option>
            <option value="Yes, I have a disability">Yes, I have a disability</option>
            <option value="No, I do not have a disability">No, I do not have a disability</option>
            <option value="I do not want to answer">I do not want to answer</option>
          </select>
        </div>

        <div class="application-question">
          <div class="text">Name</div>
          <input type="text" name="eeo[disabilitySignature]" />
        </div>

        <div class="application-question">
          <div class="text">Date</div>
          <input type="text" name="eeo[disabilitySignatureDate]" />
        </div>

        <!-- Submit Button -->
        <button id="hcaptchaSubmitBtn" class="hidden" type="submit" style="display:none"></button>
        <button id="btn-submit" type="button" class="postings-btn template-btn-submit">SUBMIT APPLICATION</button>
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

        # Check standard fields
        assert await page.input_value("input[name='name']") == "Maruf Hassan"
        assert await page.input_value("input[name='email']") == "csengineer.maruf@gmail.com"
        assert await page.input_value("input[name='phone']") == "+91 79803 56852"
        assert await page.input_value("input[name='location']") == "Kolkata, West Bengal, India"
        assert await page.input_value("input[name='org']") == "Floor Boss"
        assert await page.input_value("input[name='urls[LinkedIn]']") == "https://linkedin.com/in/maruf-hassan"
        assert await page.input_value("input[name='urls[GitHub]']") == "https://github.com/zyllus17"

        # Check custom questions
        assert await page.is_checked("input[name='field0'][value='LinkedIn']")
        assert await page.is_checked("input[name='field1'][value='No']")
        assert await page.input_value("input[name='country_field']") == "India"
        assert await page.input_value("select[name='sponsorship_field']") == "No"
        assert await page.input_value("select[name='notice_field']") == "1-2 weeks"
        assert await page.is_checked("input[name='privacy_field']")

        # Check EEO
        assert await page.input_value("select[name='eeo[gender]']") == "Male"
        assert await page.is_checked("input[name='eeo[race]'][value='Decline to self-identify']")
        assert await page.input_value("select[name='eeo[veteran]']") == "I am not a Protected Veteran"
        assert await page.input_value("select[name='eeo[disability]']") == "I do not want to answer"
        assert await page.input_value("input[name='eeo[disabilitySignature]']") == "Maruf Hassan"
        assert len(await page.input_value("input[name='eeo[disabilitySignatureDate]']")) > 5

        # Check submit button
        plat_sel = filler.selectors.get("lever", {})
        submit_sel = plat_sel.get("submit_button")
        submit_btn = await page.query_selector(submit_sel)
        assert submit_btn is not None
        assert await submit_btn.is_visible()
        btn_text = (await submit_btn.inner_text()).strip()
        assert "SUBMIT APPLICATION" in btn_text

        await browser.close()
