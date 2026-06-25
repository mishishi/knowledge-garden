"""Parse-check the inline script in index.html"""
import re, os, tempfile
ROOT = r"D:\workspaces\mcode\knowledge-garden"
with open(os.path.join(ROOT, "index.html"), encoding="utf-8") as f:
    html = f.read()
scripts = re.findall(r"<script>([\s\S]*?)</script>", html)
for i, js in enumerate(scripts):
    fd, path = tempfile.mkstemp(suffix=".js")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(js)
    rc = os.system(f'node --check "{path}" 2>nul')
    if rc != 0:
        print(f"BAD script #{i+1}")
        os.unlink(path)
        raise SystemExit(1)
    os.unlink(path)
print(f"OK: {len(scripts)} script(s) parse cleanly")
