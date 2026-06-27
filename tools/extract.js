const fs = require('fs');
const html = fs.readFileSync('D:/workspaces/mcode/knowledge-garden/index.html', 'utf8');
const re = /<script>([\s\S]*?)<\/script>/g;
let m, idx = 0;
while ((m = re.exec(html)) !== null) {
    fs.writeFileSync(`D:/tmp_script_${idx}.js`, m[1]);
    console.log('script', idx, 'len', m[1].length);
    idx++;
}