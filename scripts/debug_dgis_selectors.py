from playwright.sync_api import sync_playwright
import time

url = "https://2gis.ru/astrakhan/search/%D0%B8%D0%B7%D0%B3%D0%BE%D1%82%D0%BE%D0%B2%D0%BB%D0%B5%D0%BD%D0%B8%D0%B5%20%D0%BF%D0%B0%D0%BC%D1%8F%D1%82%D0%BD%D0%B8%D0%BA%D0%BE%D0%B2"

def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        print("Navigating...")
        page.goto(url, wait_until="networkidle", timeout=30000)
        time.sleep(5)
        
        print("Searching for firm links...")
        
        # Look for any A tag with '/firm/' in href
        firm_links = page.query_selector_all("a[href*='/firm/']")
        print(f"Found {len(firm_links)} firm links.")
        
        for i, a in enumerate(firm_links[:5]):
            print(f"Link {i}: {a.get_attribute('href')}")
            # Get the ancestor div that seems to contain it (the card wrapper)
            # Usually we can do parentNode traversal
            js_code = """
            (el) => {
                let curr = el;
                let depth = 0;
                while (curr && curr.tagName !== 'BODY' && depth < 5) {
                    curr = curr.parentNode;
                    depth++;
                    // return class name and text if not too big
                    if (curr.innerText && curr.innerText.includes('ул.') || curr.innerText.includes('Оценить')) {
                        return curr.className;
                    }
                }
                return 'unknown';
            }
            """
            container_class = a.evaluate(js_code)
            print(f"  Suggested container class: {container_class}")

        print("\nSearching for all text blocks...")
        texts = page.evaluate("""() => {
            const result = [];
            const elements = document.body.querySelectorAll('*');
            for (const el of elements) {
                if (el.children.length === 0 && el.textContent.trim().length > 0) {
                    if (el.textContent.includes('Ритуал') || el.textContent.includes('Гранит')) {
                        result.push({
                            text: el.textContent.trim(),
                            className: el.className,
                            tagName: el.tagName
                        });
                    }
                }
            }
            return result.slice(0, 10);
        }""")
        
        for t in texts:
            print(t)
            
        browser.close()

if __name__ == "__main__":
    main()
