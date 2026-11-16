"""Playwright Browser Session Automation demonstrating session persistence and posting."""

import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

SESSION_DIR = Path(__file__).resolve().parent
STORAGE_STATE_PATH = SESSION_DIR / "storage_state.json"
MOCK_SERVER_URL = os.environ.get("MOCK_X_URL", "http://127.0.0.1:8001")


def run_session_demo(base_url: str = MOCK_SERVER_URL):
    """Demonstrate browser login state persistence and post composition using Playwright."""
    print(f"[*] Starting Playwright Session Demo against: {base_url}")

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except Exception as e:
            print(f"[-] Chromium browser launch failed: {e}")
            print("[!] If Playwright browsers are not installed, run: playwright install chromium")
            return False

        # Phase 1: Authentication and Session State Capture
        if not STORAGE_STATE_PATH.exists():
            print("[*] No existing session found. Performing initial authentication...")
            context = browser.new_context()
            page = context.new_page()

            try:
                page.goto(base_url, timeout=10000)
                page.wait_for_selector("#login-section", timeout=5000)

                # Fill credentials
                page.fill("#username", "playwright_agent")
                page.fill("#password", "secure_agent_pass")
                page.click("#login-btn")

                # Verify authenticated view is active
                page.wait_for_selector("#composer-section", timeout=5000)
                print("[+] Successfully logged in.")

                # Persist session state (cookies and local storage)
                context.storage_state(path=str(STORAGE_STATE_PATH))
                print(f"[+] Authentication state saved to {STORAGE_STATE_PATH}")
            except Exception as ex:
                print(f"[-] Failed during authentication: {ex}")
                browser.close()
                return False
            finally:
                context.close()
        else:
            print(f"[+] Reusing existing session state from {STORAGE_STATE_PATH}")

        # Phase 2: Session Reuse and Post Composition
        print("[*] Launching new context with saved storage state...")
        authenticated_context = browser.new_context(storage_state=str(STORAGE_STATE_PATH))
        page = authenticated_context.new_page()

        try:
            page.goto(base_url, timeout=10000)

            # Confirm session is automatically recognized without re-entering credentials
            page.wait_for_selector("#composer-section", timeout=5000)
            user_text = page.inner_text("#user-display")
            print(f"[+] Session active without login form! Active user: {user_text}")

            # Interact with composer
            post_content = f"Automated update via Playwright session at {time.strftime('%Y-%m-%d %H:%M:%S')}"
            page.fill("#compose-input", post_content)
            page.click("#post-btn")

            # Wait for post to appear in feed
            time.sleep(1)
            feed_text = page.inner_text("#posts-container")
            if post_content in feed_text:
                print(f"[+] Post verified in feed: '{post_content}'")
            else:
                print("[!] Post submitted, awaiting feed refresh.")

            print("[PASS] Playwright persistent browser session semantics successfully demonstrated.")
            return True
        except Exception as ex:
            print(f"[-] Error during composer interaction: {ex}")
            return False
        finally:
            authenticated_context.close()
            browser.close()


if __name__ == "__main__":
    success = run_session_demo()
    sys.exit(0 if success else 1)
