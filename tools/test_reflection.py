import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={'width': 1280, 'height': 800})
        page = await ctx.new_page()
        await page.goto('http://127.0.0.1:8765/')
        setup = """
        const prog = {
          completed: {
            'harness-engineering__01-what-is-harness': true,
            'harness-engineering__02-agent-loop': true,
            'harness-engineering__03-tool-design': true,
            'harness-engineering__04-context-management': true,
            'harness-engineering__05-permissions-sandbox': true,
            'harness-engineering__06-observability': true,
            'harness-engineering__07-memory-layers': true,
            'harness-engineering__08-failure-recovery': true,
            'harness-engineering__09-eval-driven': true,
            'harness-engineering__10-build-from-scratch': true
          },
          readPct: {
            'rag__01-why-rag': 0.6,
            'rag__02-embedding-models': 0.4
          },
          timeSpent: {
            'harness-engineering__01-what-is-harness': 18,
            'harness-engineering__02-agent-loop': 22,
            'harness-engineering__03-tool-design': 31,
            'harness-engineering__04-context-management': 14,
            'harness-engineering__05-permissions-sandbox': 19
          },
          lastRead: null
        };
        localStorage.setItem('progress', JSON.stringify(prog));
        const ns = [
            {quote: 'harness 模式', text: 'team + plan 双层', color: 'yellow', type: 'note', chapterId: 'harness-engineering__01-what-is-harness', bookSlug: 'harness-engineering', timestamp: Date.now()},
            {quote: 'eval', text: '必须量化', color: 'green', type: 'note', chapterId: 'harness-engineering__09-eval-driven', bookSlug: 'harness-engineering', timestamp: Date.now()},
            {quote: 'RAG', text: '召回是上限', color: 'blue', type: 'note', chapterId: 'rag__01-why-rag', bookSlug: 'rag', timestamp: Date.now()}
        ];
        localStorage.setItem('notes', JSON.stringify(ns));
        localStorage.setItem('kg_takeaways', JSON.stringify({
            'harness-engineering': '三层 harness 模式让多 agent 可治理, 比裸 multi-agent 强很多。',
            'harness-engineering_ts': Date.now() - 86400000
        }));
        localStorage.setItem('kg_welcomed', '1');
        """
        await page.evaluate(setup)
        # 预标记已庆祝 (object 格式, key=slug, value=ts), 避免 series-celebration modal 弹
        await page.evaluate("localStorage.setItem('kg_series_celebrated', JSON.stringify({'harness-engineering': Date.now()}))")
        await page.reload()
        await page.wait_for_load_state('domcontentloaded')
        await page.wait_for_timeout(2500)

        zones = await page.evaluate('document.querySelectorAll(".reflection-zone").length')
        print(f'reflection zones: {zones}')

        # 滚到 harness 卡片
        await page.evaluate("document.querySelector('.overview-card[data-book=\"harness-engineering\"]').scrollIntoView({block: 'center'})")
        await page.wait_for_timeout(500)
        # 用 JS click 避免 sidebar 拦截
        await page.evaluate("document.querySelector('.overview-card[data-book=\"harness-engineering\"] [data-reflection-toggle]').click()")
        await page.wait_for_timeout(500)

        # 验 summary / takeaway
        summary = await page.evaluate("document.querySelector('.overview-card[data-book=\"harness-engineering\"] [data-reflection-summary]').textContent")
        print(f'harness summary: {summary}')

        ta = await page.evaluate("document.querySelector('.overview-card[data-book=\"harness-engineering\"] [data-reflection-text]').value")
        print(f'takeaway loaded: {ta[:40]}...')

        await page.screenshot(path=r'D:\workspaces\mcode\knowledge-garden\tools\reflection_expanded.png', full_page=False)
        print('saved reflection_expanded.png')

        # RAG 卡片
        await page.evaluate("document.querySelector('.overview-card[data-book=\"rag\"]').scrollIntoView({block: 'center'})")
        await page.wait_for_timeout(500)
        await page.evaluate("document.querySelector('.overview-card[data-book=\"rag\"] [data-reflection-toggle]').click()")
        await page.wait_for_timeout(500)
        rag_summary = await page.evaluate("document.querySelector('.overview-card[data-book=\"rag\"] [data-reflection-summary]').textContent")
        print(f'rag summary: {rag_summary}')

        # 输入 RAG takeaway
        await page.fill('.overview-card[data-book="rag"] [data-reflection-text]', 'RAG 看起来简单, 真做起来召回质量是上限。embedding + rerank 必选。')
        await page.wait_for_timeout(900)  # debounce 400ms + save

        saved = await page.evaluate("JSON.parse(localStorage.getItem('kg_takeaways') || '{}')")
        print(f'saved rag takeaway: {(saved.get("rag") or "")[:40]}...')
        print(f'saved rag ts exists: {"rag_ts" in saved}')

        await page.screenshot(path=r'D:\workspaces\mcode\knowledge-garden\tools\reflection_rag.png', full_page=False)
        print('saved reflection_rag.png')

        # 收起后 badge 应该出现 ●
        await page.evaluate("document.querySelector('.overview-card[data-book=\"rag\"] [data-reflection-toggle]').click()")
        await page.wait_for_timeout(300)
        has_dot = await page.evaluate("document.querySelector('.overview-card[data-book=\"rag\"] [data-reflection-toggle]').classList.contains('has-takeaway')")
        print(f'rag has-takeaway badge: {has_dot}')

        await browser.close()

asyncio.run(main())