import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={'width': 390, 'height': 800})
        page = await ctx.new_page()
        await page.goto('http://127.0.0.1:8765/')
        await page.evaluate('localStorage.setItem("kg_welcomed", "1")')
        await page.reload()
        await page.wait_for_load_state('domcontentloaded')
        await page.wait_for_timeout(1500)
        # mobile: 先关 sidebar 再开 menu
        await page.click('#more-btn')
        await page.wait_for_timeout(400)
        menu = await page.query_selector('#toolbar-menu')
        if menu:
            await menu.screenshot(path=r'D:\workspaces\mcode\knowledge-garden\tools\settings_panel_mobile.png')
            print('saved')
        await browser.close()

asyncio.run(main())