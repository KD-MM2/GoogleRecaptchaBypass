from patchright.async_api import Page
from RecaptchaSolver import RecaptchaSolver
import time

async with async_playwright() as p:
    browser = await p.chromium.launch_persistent_context(
      user_data_dir="user-data-dir",
      channel="chrome",
      headless=False,
      no_viewport=True,
      executable_path="/path/to/chrome",
      devtools=False,
)
    page = await browser.new_page()
    recaptchaSolver = RecaptchaSolver(page)

    await page.goto("https://www.google.com/recaptcha/api2/demo")

    t0 = time.time()
    recaptchaSolver.solveCaptcha()
    print(f"Time to solve the captcha: {time.time()-t0:.2f} seconds")

    page.locator("#recaptcha-demo-submit").click()

    await browser.close()
