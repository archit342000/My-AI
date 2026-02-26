from playwright.sync_api import sync_playwright

def verify_design():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Go to local app
        page.goto("http://localhost:5000")

        # Wait for content
        page.wait_for_selector("#app-root")

        # Take screenshot of the main view
        page.screenshot(path="verification_screenshot.png", full_page=True)

        browser.close()

if __name__ == "__main__":
    verify_design()
