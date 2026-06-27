"""Debug MediaSession: directly check if my code calls setActionHandler etc."""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()
        page = await context.new_page()
        # Spy on navigator.mediaSession methods
        await page.add_init_script("""
        window.__msLog = [];
        Object.defineProperty(navigator, 'mediaSession', {
            configurable: true,
            get() {
                return this.__ms || (this.__ms = {
                    _meta: null,
                    _state: 'none',
                    _handlers: {},
                    get metadata() { return this._meta; },
                    set metadata(v) { this._meta = v; window.__msLog.push(['metadata', v && {title: v.title, artist: v.artist, album: v.album}]); },
                    get playbackState() { return this._state; },
                    set playbackState(v) { this._state = v; window.__msLog.push(['state', v]); },
                    setActionHandler(action, h) { this._handlers[action] = !!h; window.__msLog.push(['handler', action, !!h]); }
                });
            }
        });
        """)
        # Capture console logs
        page.on("console", lambda m: print(f"  [console.{m.type}] {m.text}"))
        page.on("pageerror", lambda e: print(f"  [ERROR] {e}"))
        await page.goto("http://127.0.0.1:8766/index.html#cn-codex__01-battlefield", wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        # Trigger click via JS
        result = await page.evaluate("""() => {
            const btn = document.querySelector('.chapter-tts-btn[data-tts-anchor="cn-codex__01-battlefield"]');
            if (!btn) return 'no btn';
            btn.click();
            return 'clicked';
        }""")
        print(f"Click result: {result}")
        await page.wait_for_timeout(1500)
        # Get the log
        log = await page.evaluate("window.__msLog")
        print(f"MediaSession log ({len(log)} entries):")
        for entry in log[:30]:
            print(f"  {entry}")
        await browser.close()

asyncio.run(main())
