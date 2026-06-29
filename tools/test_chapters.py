import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={'width': 1280, 'height': 800})
        page = await ctx.new_page()
        await page.goto('http://127.0.0.1:8765/')
        await page.evaluate("localStorage.setItem('kg_welcomed', '1')")
        await page.evaluate("localStorage.setItem('progress', JSON.stringify({completed: {'harness-engineering__01-cli-first': true}, readPct: {'harness-engineering__01-cli-first': 1}}))")
        await page.reload()
        await page.wait_for_load_state('domcontentloaded')
        await page.wait_for_timeout(2500)
        chs = await page.evaluate("CHAPTERS_BY_BOOK['harness-engineering']")
        print(f'harness ({len(chs)}): {chs}')
        chs2 = await page.evaluate("CHAPTERS_BY_BOOK['rag']")
        print(f'rag ({len(chs2)}): {chs2}')
        # 验 renderReflections 的计算
        completed = await page.evaluate("JSON.parse(localStorage.getItem('progress')).completed")
        readPct = await page.evaluate("JSON.parse(localStorage.getItem('progress')).readPct")
        print(f'completed keys: {Object.keys(completed)}')
        print(f'readPct keys: {Object.keys(readPct)}')
        await browser.close()

asyncio.run(main())