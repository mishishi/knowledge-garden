import asyncio
from playwright.async_api import async_playwright

URL = 'http://127.0.0.1:8765/'

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={'width': 1280, 'height': 800})
        page = await ctx.new_page()
        await page.goto(URL)
        await page.evaluate('localStorage.setItem("kg_welcomed", "1")')
        await page.reload()
        await page.wait_for_load_state('domcontentloaded')
        await page.wait_for_timeout(1500)

        # 开 toolbar menu
        await page.click('#more-btn')
        await page.wait_for_timeout(400)

        # 截图 (整页 1280x800)
        await page.screenshot(path=r'D:\workspaces\mcode\knowledge-garden\tools\settings_panel.png', full_page=False)
        print('saved tools/settings_panel.png')

        # 截图: 只 menu 区域
        menu = await page.query_selector('#toolbar-menu')
        if menu:
            await menu.screenshot(path=r'D:\workspaces\mcode\knowledge-garden\tools\settings_panel_only.png')
            print('saved tools/settings_panel_only.png')

        # 验两个 section 都有 label
        labels = await page.evaluate('Array.from(document.querySelectorAll(".t-section-label")).map(e => e.textContent)')
        print(f'section labels: {labels}')

        # 验 dark-btn 不可见但元素存在 (键盘 'D' 还能用)
        dark_exists = await page.evaluate('document.getElementById("dark-btn") !== null')
        dark_visible = await page.evaluate('document.getElementById("dark-btn").offsetWidth')
        print(f'dark-btn exists: {dark_exists}, visible width: {dark_visible}')

        # 移动端 viewport 测
        await page.set_viewport_size({'width': 390, 'height': 800})
        await page.wait_for_timeout(300)
        await page.click('#more-btn')
        await page.wait_for_timeout(300)
        menu2 = await page.query_selector('#toolbar-menu')
        if menu2:
            await menu2.screenshot(path=r'D:\workspaces\mcode\knowledge-garden\tools\settings_panel_mobile.png')
            print('saved tools/settings_panel_mobile.png')

        await browser.close()

asyncio.run(main())