import pytest
import asyncio
from pathlib import Path
from tools.browser_autofill import ATSDetector, FormFiller, AutoApplier
from tools.humanizer import HumanBehavior

REPO_ROOT = Path(__file__).parent.parent.resolve()

def test_workday_url_detection():
    detector = ATSDetector()
    assert detector.detect("https://autodesk.wd1.myworkdayjobs.com/Ext/job/Norway---Oslo/Prncipal-Software-Engineer_26WD101129-1") == "workday"
    assert detector.detect("https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/Yokneam/Mechanical-Hardware-Design-Engineer_JR2020215") == "workday"
    assert detector.detect("https://target.wd5.myworkdayjobs.com/targetcareers/job/Kingston/Tech-Consultant_R0000453293") == "workday"
    assert detector.detect("https://visa.wd1.myworkdayjobs.com/en-US/VisaJobs/job/Bengaluru/Sr-Software-Engineer_REF69300V") == "workday"
    assert detector.detect("https://company.myworkdayjobs.com/en-US/careers/job/12345/apply") == "workday"

@pytest.mark.asyncio
async def test_workday_mock_wizard_steps():
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
        "location": "Park Street, Kolkata, West Bengal, India",
        "current_company": "Floor Boss",
        "current_title": "AI Automation Engineer",
        "linkedin_url": "https://linkedin.com/in/maruf-hassan",
        "github_url": "https://github.com/zyllus17",
        "resume_pdf_path": str(REPO_ROOT / "cv" / "main_example.pdf"),
        "years_experience": 5,
        "expected_salary": 100000,
        "workday_password": "WorkdayApplier2026!#",
        "work_authorization": {"requires_sponsorship": True, "authorized_india": True},
        "eeo_responses": {
            "gender": "Male",
            "race_ethnicity": "Decline to self-identify",
            "veteran_status": "I am not a protected veteran",
            "disability_status": "I do not wish to answer"
        }
    }

    # Complete Mock HTML simulating Workday Canvas Kit structure
    mock_html = """
    <html>
    <head><title>Workday Mock Application Flow</title></head>
    <body>
      <div data-automation-id="applyFlowPage">
        <ol data-automation-id="progressBar">
          <li data-automation-id="progressBarActiveStep">current step 1 of 5 My Information</li>
          <li data-automation-id="progressBarInactiveStep">step 2 of 5 My Experience</li>
          <li data-automation-id="progressBarInactiveStep">step 3 of 5 Application Questions</li>
          <li data-automation-id="progressBarInactiveStep">step 4 of 5 Voluntary Disclosures</li>
          <li data-automation-id="progressBarInactiveStep">step 5 of 5 Review</li>
        </ol>

        <!-- Step 1: My Information Page -->
        <div data-automation-id="applyFlowMyInfoPage">
          <div data-automation-id="formField-source">
            <label>How Did You Hear About Us?*</label>
            <div data-automation-id="multiselectInputContainer">
              <span data-automation-id="promptIcon">🔍</span>
              <input type="text" id="source-input" />
            </div>
            <!-- Menu container that opens on click -->
            <div data-automation-id="activeListContainer" style="display:none;">
              <div data-automation-id="menuItem">Job Board</div>
              <div data-automation-id="menuItem">Company Careers</div>
            </div>
          </div>

          <div data-automation-id="formField-candidateIsPreviousWorker">
            <label>Have you previously worked for our company?*</label>
            <div id="previousWorker--candidateIsPreviousWorker">
              <label><input type="radio" name="prev_work" value="yes" /> Yes</label>
              <label><input type="radio" name="prev_work" value="no" id="pw-no" /> No</label>
            </div>
          </div>

          <div data-automation-id="formField-legalName--firstName">
            <label>Given Name(s)*</label>
            <input type="text" id="fn" />
          </div>

          <div data-automation-id="formField-legalName--lastName">
            <label>Family Name*</label>
            <input type="text" id="ln" />
          </div>

          <div data-automation-id="formField-addressLine1">
            <label>Address Line 1*</label>
            <input type="text" id="addr" />
          </div>

          <div data-automation-id="formField-city">
            <label>City*</label>
            <input type="text" id="city" />
          </div>

          <div data-automation-id="formField-postalCode">
            <label>Postal Code*</label>
            <input type="text" id="postal" />
          </div>

          <div data-automation-id="formField-countryRegion">
            <label>State</label>
            <button type="button" name="countryRegion" id="address--countryRegion">Select One</button>
            <div id="state-list" style="display:none;">
              <div data-automation-id="promptOption" data-automation-label="West Bengal">West Bengal</div>
              <div data-automation-id="promptOption" data-automation-label="Maharashtra">Maharashtra</div>
            </div>
          </div>

          <div data-automation-id="formField-phoneType">
            <label>Phone Device Type*</label>
            <button type="button" name="phoneType" id="phoneNumber--phoneType">Select One</button>
            <div id="pt-list" style="display:none;">
              <li role="option">Mobile</li>
              <li role="option">Telephone</li>
            </div>
          </div>

          <div data-automation-id="formField-phoneNumber">
            <label>Phone Number*</label>
            <input type="text" id="phone" />
          </div>

          <!-- Workday Anti-Bot Honeypot: MUST REMAIN EMPTY -->
          <input type="text" data-automation-id="beecatcher" id="beecatcher" style="display:none;" />
        </div>

        <div data-automation-id="pageFooter">
          <button type="button" data-automation-id="pageFooterNextButton">Save and Continue</button>
        </div>
      </div>

      <script>
        // Interactive mocks for dropdowns
        document.getElementById("source-input").addEventListener("click", () => {
          document.querySelector("[data-automation-id='activeListContainer']").style.display = "block";
        });
        document.getElementById("address--countryRegion").addEventListener("click", () => {
          document.getElementById("state-list").style.display = "block";
        });
        document.getElementById("phoneNumber--phoneType").addEventListener("click", () => {
          document.getElementById("pt-list").style.display = "block";
        });
        document.querySelectorAll("#pt-list li").forEach(li => {
          li.addEventListener("click", (e) => {
            document.getElementById("phoneNumber--phoneType").innerText = e.target.innerText;
            document.getElementById("pt-list").style.display = "none";
          });
        });
        document.querySelectorAll("#state-list [data-automation-id='promptOption']").forEach(div => {
          div.addEventListener("click", (e) => {
            document.getElementById("address--countryRegion").innerText = e.target.getAttribute("data-automation-label");
            document.getElementById("state-list").style.display = "none";
          });
        });
      </script>
    </body>
    </html>
    """

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(mock_html)

        humanizer = HumanBehavior(page)
        filler = FormFiller(page, "workday", candidate, humanizer)

        success = await filler.fill_form()
        assert success is True

        # Assert Step 2 Fields Filled
        assert await page.input_value("#fn") == "Maruf"
        assert await page.input_value("#ln") == "Hassan"
        assert await page.input_value("#addr") == "Park Street"
        assert await page.input_value("#city") == "Kolkata"
        assert await page.input_value("#postal") == "700016"
        assert await page.input_value("#phone") == "7980356852"

        # Assert Honeypot is completely empty!
        honeypot_val = await page.input_value("#beecatcher")
        assert honeypot_val == "", "CRITICAL: Honeypot beecatcher must never be filled!"

        # Assert Radio was selected
        assert await page.is_checked("#pw-no") is True

        # Assert State & Phone Type dropdowns selected
        assert await page.inner_text("#phoneNumber--phoneType") == "Mobile"
        assert await page.inner_text("#address--countryRegion") == "West Bengal"

        # Assert Next button exists
        next_btn = await page.query_selector("button[data-automation-id='pageFooterNextButton']")
        assert next_btn is not None

        await browser.close()
