import asyncio
import os
import json
from playwright.async_api import async_playwright

URL = os.environ.get('KG_URL', 'https://mishishi.github.io/knowledge-garden/')

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context()
        page = await ctx.new_page()

        # 先打开, 设 localStorage
        await page.goto(URL)
        await page.wait_for_load_state('domcontentloaded')
        await page.wait_for_timeout(2000)

        # 注入: progress 含 2 章在读, 1 章未读
        await page.evaluate("""
            const prog = {
              lastRead: { chapterId: 'harness-engineering__01-cli-first', timestamp: Date.now() },
              completed: { 'crewai__00-intro': true },
              readPct: {
                'harness-engineering__01-cli-first': 0.45,
                'claude-code__01-fundamentals': 0.62,
                'harness-engineering__02-team-config': 0,
                'rag__01-naive-rag': 0
              }
            };
            localStorage.setItem('progress', JSON.stringify(prog));
            const bm = {
              'harness-engineering__01-cli-first': [{text: '备忘: 这里需要回头看章节映射', timestamp: Date.now() - 60_000, idx: 0}],
              'agent-skills__00-overview': [{text: 'TODO: 整理一个跨项目的 skill 选型清单', timestamp: Date.now() - 3600_000, idx: 0}]
            };
            localStorage.setItem('bookmarks', JSON.stringify(bm));
            localStorage.setItem('kg_welcomed', '1');
        """)
        await page.reload()
        await page.wait_for_load_state('domcontentloaded')
        await page.wait_for_timeout(2000)

        # 验 Overview 顶部的 today-panel
        cols = await page.evaluate("document.querySelectorAll('#today-panel .today-col').length")
        items = await page.evaluate("document.querySelectorAll('#today-panel .today-item').length")
        titles = await page.evaluate("Array.from(document.querySelectorAll('#today-panel .today-item-title')).map(e => e.textContent)")
        print(f"cols: {cols}, items: {items}")
        for t in titles:
            print(f"  - {t}")

        # 滚动到 today-panel 截图
        await page.evaluate("document.getElementById('today-panel').scrollIntoView({block: 'center'})")
        await page.wait_for_timeout(500)

        # 截图 desktop
        await page.screenshot(path=r'D:\workspaces\mcode\knowledge-garden\tools\today_panel.png', full_page=False)
        print('saved tools/today_panel.png')

        # 移动端 viewport 截图
        await page.set_viewport_size({'width': 390, 'height': 800})
        await page.wait_for_timeout(500)
        await page.evaluate("document.getElementById('today-panel').scrollIntoView({block: 'center'})")
        await page.wait_for_timeout(300)
        await page.screenshot(path=r'D:\workspaces\mcode\knowledge-garden\tools\today_panel_mobile.png', full_page=False)
        print('saved tools/today_panel_mobile.png')
        await browser.close()

asyncio.run(main())
