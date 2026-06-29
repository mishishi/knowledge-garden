import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={'width': 1280, 'height': 800})
        page = await ctx.new_page()
        await page.goto('http://127.0.0.1:8765/')
        await page.evaluate('localStorage.setItem("kg_welcomed", "1")')
        # 注入几条笔记让图谱不空
        await page.evaluate("""
            const ns = [
                {quote: 'RAG 系统的核心是检索质量', text: '需要多路召回 + rerank', color: 'yellow', type: 'note', chapterId: 'rag__01-naive-rag', bookSlug: 'rag', timestamp: Date.now()},
                {quote: 'embedding 模型选型', text: 'BGE 中文场景首选', color: 'green', type: 'note', chapterId: 'rag__02-embedding', bookSlug: 'rag', timestamp: Date.now()},
                {quote: 'multi-agent 的消息传递', text: '需要明确 schema', color: 'blue', type: 'note', chapterId: 'a2a-multi-agent__01-protocol', bookSlug: 'a2a-multi-agent', timestamp: Date.now()},
                {quote: 'harness 模式', text: 'team + plan 双层', color: 'pink', type: 'note', chapterId: 'harness-engineering__01-cli-first', bookSlug: 'harness-engineering', timestamp: Date.now()},
                {quote: '上下文窗口', text: '128k 起步, 留 buffer', color: 'yellow', type: 'note', chapterId: 'context-engineering__01-window', bookSlug: 'context-engineering', timestamp: Date.now()}
            ];
            localStorage.setItem('notes', JSON.stringify(ns));
        """)
        await page.reload()
        await page.wait_for_load_state('domcontentloaded')
        await page.wait_for_timeout(2000)

        # 打开 notes panel (键盘 N)
        await page.keyboard.press('n')
        await page.wait_for_timeout(500)

        # 截图 notes panel
        await page.screenshot(path=r'D:\workspaces\mcode\knowledge-garden\tools\notes_panel_with_graph_btn.png', full_page=False)
        print('saved notes_panel_with_graph_btn.png')

        # 验: notes-graph-btn 存在 + 可见
        btn_exists = await page.evaluate('document.getElementById("notes-graph-btn") !== null')
        btn_visible = await page.evaluate('document.getElementById("notes-graph-btn").offsetWidth > 0')
        print(f'notes-graph-btn: exists={btn_exists}, visible={btn_visible}')

        # 点击 graph 按钮 → 应该打开图谱 modal
        await page.click('#notes-graph-btn')
        await page.wait_for_timeout(800)
        all_visible = await page.evaluate("""
            Array.from(document.querySelectorAll('.modal, [class*=\"graph\"], [class*=\"notes-graph\"]'))
              .map(m => ({cls: m.className, vis: m.classList.contains('visible'), id: m.id || ''}))
        """)
        print('modals:', all_visible)

        # 截图 图谱
        await page.screenshot(path=r'D:\workspaces\mcode\knowledge-garden\tools\notes_graph.png', full_page=False)
        print('saved notes_graph.png')

        await browser.close()

asyncio.run(main())