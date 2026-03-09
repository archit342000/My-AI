from playwright.sync_api import sync_playwright

def test_folder_delete():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        print("Navigating to localhost:5000...")
        page.goto("http://localhost:5000")

        # Wait for initialization
        page.wait_for_timeout(2000)

        # Click the "New Folder" button
        print("Clicking new folder button...")
        new_folder_btn = page.locator('#new-folder-btn')
        new_folder_btn.click()

        # Fill the prompt
        print("Filling prompt...")
        prompt_input = page.locator('#prompt-input')
        prompt_input.fill("Test Delete Folder")

        # The prompt action btn
        confirm_btn = page.locator('#prompt-action-btn')
        confirm_btn.click()

        # Wait for folder to be created and rendered
        page.wait_for_timeout(1000)

        # Take a screenshot showing the folder without hover
        print("Taking initial folder screenshot...")
        page.screenshot(path="folder_delete_initial.png")

        # Hover over the new folder header to make the delete button appear
        print("Hovering folder header...")
        folder_header = page.locator('.folder-header', has_text="Test Delete Folder").first
        folder_header.hover()

        # Wait a moment for hover effect
        page.wait_for_timeout(500)

        # Take a screenshot showing the delete button
        print("Taking hover screenshot...")
        page.screenshot(path="folder_delete_hover.png")

        # Click the delete button
        print("Clicking delete button...")
        delete_btn = folder_header.locator('.folder-delete-btn')
        delete_btn.click()

        # A confirmation modal should appear
        page.wait_for_timeout(500)

        print("Taking confirmation modal screenshot...")
        page.screenshot(path="folder_delete_confirm.png")

        confirm_modal_btn = page.locator('#confirm-action-btn')
        confirm_modal_btn.click()

        # Wait for deletion
        page.wait_for_timeout(1000)

        print("Taking final screenshot...")
        page.screenshot(path="folder_delete_after.png")

        browser.close()

if __name__ == "__main__":
    test_folder_delete()
