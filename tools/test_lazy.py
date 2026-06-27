"""Smoke test: open knowledge garden, verify lazy load works."""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        # Track network requests
        book_fetches = []
        # Catch errors
        page.on("console", lambda msg: print(f"  [console.{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: print(f"  [PAGE ERROR] {err}"))
        page.on("request", lambda req: book_fetches.append(req.url) if "/assets/books/" in req.url else None)
        await page.goto("http://127.0.0.1:8765/index.html#overview", wait_until="domcontentloaded")
        await page.wait_for_timeout(500)
        # Check initial: no book JSON fetched yet
        print(f"Initial book fetches: {len(book_fetches)}")
        # Check chapter placeholders exist
        placeholders = await page.query_selector_all(".chapter-body[data-load-book]")
        print(f"Chapter placeholders: {len(placeholders)}")
        # Click a chapter link
        await page.goto("http://127.0.0.1:8765/index.html#codex-cases__01-paradigm-shift", wait_until="domcontentloaded")
        await page.wait_for_timeout(2500)
        print(f"After chapter jump fetches: {len(book_fetches)}")
        for f in book_fetches[:5]:
            print(f"  - {f}")
        # Check the chapter body is now populated
        body = await page.query_selector("#codex-cases__01-paradigm-shift .chapter-body")
        inner = await body.inner_html() if body else None
        print(f"Chapter body length: {len(inner) if inner else 0}")
        print(f"Body starts: {(inner or '')[:200]}")
        # Test scroll: go back to overview, then scroll down
        book_fetches.clear()
        await page.goto("http://127.0.0.1:8765/index.html#overview", wait_until="domcontentloaded")
        await page.wait_for_timeout(500)
        print(f"\nAfter reload to overview: {len(book_fetches)} fetches")
        # Scroll deep to first book chapters
        await page.evaluate("window.scrollTo(0, 8000)")
        await page.wait_for_timeout(2000)
        print(f"After scroll 8000: {len(book_fetches)} fetches")
        await page.evaluate("window.scrollTo(0, 30000)")
        await page.wait_for_timeout(2000)
        print(f"After scroll 30000: {len(book_fetches)} fetches")
        for f in book_fetches[:5]:
            print(f"  - {f}")
        await browser.close()

asyncio.run(main())
