"""Final smoke test: verify all major features work end-to-end."""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        page.on("pageerror", lambda e: print(f"  [ERROR] {e}"))
        page.on("console", lambda m: None if m.type == "log" else print(f"  [{m.type}] {m.text}"))

        # 1. Open page
        await page.goto("http://127.0.0.1:8765/index.html#overview", wait_until="domcontentloaded")
        await page.wait_for_timeout(800)

        # 2. Lazy load check: no book JSON fetched on overview
        requests = []
        page.on("request", lambda r: requests.append(r.url) if "/assets/books/" in r.url else None)
        await page.wait_for_timeout(500)
        print(f"1. Overview book fetches: {len(requests)} (expected 0)")

        # 3. Direct chapter link triggers lazy load
        await page.goto("http://127.0.0.1:8765/index.html#codex-cases__01-paradigm-shift", wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)
        print(f"2. Direct chapter jump fetches: {len(requests)}")
        for r in requests:
            print(f"   - {r.split('/')[-1]}")

        # 4. Q&A modal opens
        await page.evaluate("document.getElementById('kb-launcher')?.click()")
        await page.wait_for_timeout(500)
        modal_visible = await page.evaluate("document.getElementById('kb-modal')?.classList.contains('visible')")
        print(f"3. Q&A modal visible: {modal_visible}")

        # 5. Welcome modal check (first-time)
        # We don't trigger it here (it only shows on first visit), skip

        # 6. TTS button exists for cn-codex (10 chapters have MP3)
        tts_btns = await page.query_selector_all('.chapter-tts-btn[data-audio-url]')
        print(f"4. TTS buttons with audio: {len(tts_btns)} (expected 10)")

        # 7. Lazy load book body is in DOM
        body = await page.query_selector("#codex-cases__01-paradigm-shift .chapter-body .chapter-content")
        print(f"5. Chapter body populated: {body is not None}")

        # 8. Search history localStorage check
        # Set a history item
        await page.evaluate("localStorage.setItem('kg_kb_history', JSON.stringify(['test query 1', 'test query 2']))")
        history = await page.evaluate("localStorage.getItem('kg_kb_history')")
        print(f"6. Search history localStorage: {history}")

        # 9. Related chapters
        rel = await page.query_selector("#related-chapters-codex-cases__01-paradigm-shift .related-card")
        print(f"7. Related chapter card exists: {rel is not None}")

        # 10. Streak heatmap
        heatmap = await page.query_selector("#streak-heatmap .streak-heatmap-grid")
        print(f"8. Streak heatmap grid: {heatmap is not None}")

        # 11. Resume carousel (no lastRead set, so it should be hidden)
        carousel = await page.evaluate("document.getElementById('resume-carousel')?.style.display")
        print(f"9. Resume carousel display: '{carousel}' (expected 'none' if no lastRead)")

        # 12. Breadcrumb
        bc = await page.query_selector("#codex-cases__01-paradigm-shift .breadcrumb")
        print(f"10. Breadcrumb exists: {bc is not None}")

        # 13. Chapter ribbon
        rib = await page.query_selector("#codex-cases__01-paradigm-shift .chapter-ribbon")
        print(f"11. Chapter ribbon exists: {rib is not None}")

        await browser.close()
        print("\n✓ Smoke test done")

asyncio.run(main())
