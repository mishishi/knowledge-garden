"""Verify SW cache works: same-book chapter 02 served from cache (no network)."""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()
        page = await context.new_page()
        # Track network requests for codex-cases.json
        network_hits = []
        page.on("request", lambda r: network_hits.append(r.url) if "codex-cases.json" in r.url else None)
        page.on("console", lambda m: None if m.type == "log" else print(f"  [{m.type}] {m.text[:200]}"))

        # Visit page 1: triggers SW install + first codex-cases.json fetch (cached)
        await page.goto("http://localhost:8000/index.html#codex-cases__01-paradigm-shift", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        # Manually trigger fetch via JS to see what happens
        test_result = await page.evaluate("""
            async () => {
                const r = await fetch('assets/books/codex-cases.json');
                const j = await r.json();
                return { status: r.status, ok: r.ok, chapters: j.chapters ? j.chapters.length : 0 };
            }
        """)
        print(f"DEBUG: manual fetch result: {test_result}")
        print(f"1. After first visit, network hits: {len(network_hits)} (expected 1)")
        # Check cache content
        cache_detail = await page.evaluate("""
            caches.open('knowledge-book-v3').then(c =>
                c.keys().then(keys => keys.map(k => new URL(k.url).pathname))
            )
        """)
        print(f"2. Cache entries: {cache_detail}")

        # Block network for codex-cases.json
        await context.route("**/assets/books/codex-cases.json", lambda route: route.abort())

        # Reload page (fresh load, navigation to chapter 01 again)
        await page.reload(wait_until="domcontentloaded")
        await page.wait_for_timeout(2500)
        # Check cache again (should still have it)
        cache_after_reload = await page.evaluate("""
            caches.open('knowledge-book-v3').then(c =>
                c.keys().then(keys => keys.map(k => new URL(k.url).pathname))
            )
        """)
        print(f"3. Cache after reload: {cache_after_reload}")
        body1 = await page.query_selector("#codex-cases__01-paradigm-shift .chapter-content")
        body1_text = await body1.inner_text() if body1 else ""
        print(f"4. Chapter 01 body length: {len(body1_text)}")
        print(f"   Network hits total: {len(network_hits)} (no new should fire if SW cache works)")

        # Navigate to chapter 02 (same book, also cached) - find a real href
        nav_links = await page.evaluate("""
            Array.from(document.querySelectorAll('a[href^="#codex-cases__"]'))
                .map(a => a.getAttribute('href'))
                .filter(h => h && h !== '#codex-cases__01-paradigm-shift')
                .slice(0, 3)
        """)
        print(f"DEBUG: nav links: {nav_links}")
        if nav_links:
            target = nav_links[0].lstrip('#')
            await page.evaluate(f"window.location.hash = '{target}'")
            await page.wait_for_timeout(2500)
            # Scroll to it
            await page.evaluate(f"document.getElementById('{target}').scrollIntoView()")
            await page.wait_for_timeout(1500)
            body2 = await page.query_selector(f"#{target} .chapter-content")
            body2_text = await body2.inner_text() if body2 else ""
            print(f"4. After nav to chapter in same book (cached), body length: {len(body2_text)}")
        else:
            print("4. (no nav link found)")

        # Try a different book (NOT cached, should fail)
        await page.evaluate("window.location.hash = 'rag__01-intro'")
        await page.wait_for_timeout(2500)
        await page.evaluate("document.getElementById('rag__01-intro').scrollIntoView()")
        await page.wait_for_timeout(1500)
        body3 = await page.query_selector("#rag__01-intro .chapter-content")
        body3_text = await body3.inner_text() if body3 else ""
        print(f"5. Different book (NOT cached, network blocked), body length: {len(body3_text)} (expected 0)")

        await context.unroute("**/assets/books/codex-cases.json")
        await browser.close()

asyncio.run(main())
