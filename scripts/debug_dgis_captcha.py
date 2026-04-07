from playwright.sync_api import sync_playwright
import time

url = "https://2gis.ru/astrakhan/search/%D0%B8%D0%B7%D0%B3%D0%BE%D1%82%D0%BE%D0%B2%D0%BB%D0%B5%D0%BD%D0%B8%D0%B5%20%D0%BF%D0%B0%D0%BC%D1%8F%D1%82%D0%BD%D0%B8%D0%BA%D0%BE%D0%B2"

def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        page.goto(url, wait_until="networkidle", timeout=30000)
        time.sleep(3)
        
        print("Page title:", page.title())
        print("Body text (first 500 chars):", page.evaluate("document.body.innerText").strip()[:500])

if __name__ == "__main__":
    main()
