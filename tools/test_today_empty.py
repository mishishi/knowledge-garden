import asyncio
import os
from playwright.async_api import async_playwright

URL = os.environ.get('KG_URL', 'http://127.0.0.1:8765/')

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context()
        page = await ctx.new_page()
        await page.goto(URL)
        await page.evaluate('localStorage.clear(); localStorage.setItem("kg_welcomed", "1")')
        await page.reload()
        await page.wait_for_load_state('domcontentloaded')
        await page.wait_for_timeout(2000)
        display = await page.evaluate('document.getElementById("today-panel").style.display')
        items = await page.evaluate('document.querySelectorAll("#today-panel .today-item").length')
        print(f'empty case: display="{display}", items={items}')
        # debug
        prog = await page.evaluate('localStorage.getItem("progress")')
        bm = await page.evaluate('localStorage.getItem("bookmarks")')
        print(f'  progress={prog}')
        print(f'  bookmarks={bm}')
        titles = await page.evaluate('Array.from(document.querySelectorAll("#today-panel .today-item-title")).map(e => e.textContent)')
        print(f'  titles: {titles}')
        await browser.close()

asyncio.run(main())
