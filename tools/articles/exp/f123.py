import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f123'); R = {}
import urllib.parse as up
APP = '''
from flask import Flask, request, render_template_string
from markupsafe import Markup
app = Flask(__name__)
TAIL = "<script>setTimeout(() => { document.body.setAttribute('data-result', window.__x ? 'XSS 执行了' : '没有执行'); }, 800);</script>"
T = {
 'body_escaped': "<div>{{ q }}</div>",
 'body_safe': "<div>{{ q|safe }}</div>",
 'attr_unquoted': "<input value={{ q }}>",
 'attr_quoted': '<input value="{{ q }}">',
 'js_string': '<script>var name = "{{ q }}";</script>',
 'js_bare': "<script>var n = {{ q }};</script>",
 'js_tojson': "<script>var n = {{ q|tojson }};</script>",
 'href': '<a id=l href="{{ q }}">click</a><script>document.getElementById("l").click()</script>',
 'markup': "<div>{{ m }}</div>",
}
@app.get('/c/<name>')
def c(name):
    q = request.args.get('q', ''); return render_template_string("<!doctype html><meta charset=utf-8><body>" + T[name] + "</body>" + TAIL, q=q, m=Markup('<b>' + q + '</b>'))
@app.get('/raw')
def raw(): return request.args.get('q', '')
'''
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
d = mkapp('f123', {'app.py': APP})
def chrome_dom(url):
    prof = FT / 'f123chrome'; shutil.rmtree(prof, ignore_errors=True)
    pc = subprocess.Popen([CHROME, '--headless=new', '--disable-gpu', '--no-first-run', f'--user-data-dir={prof}', '--virtual-time-budget=6000', '--dump-dom', url], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, start_new_session=True)
    buf = ''; t0 = time.time()
    while time.time() - t0 < 40:
        l = pc.stdout.readline()
        if not l: break
        buf += l
        if '</html>' in l: break
    try: os.killpg(pc.pid, signal.SIGKILL)
    except ProcessLookupError: pass
    pc.wait(); return buf
cases = [
    ('body_escaped', '正文里 {{ q }}(自动转义)', '<script>window.__x=1</script>'),
    ('body_safe', '正文里 {{ q|safe }}', '<script>window.__x=1</script>'),
    ('attr_unquoted', '属性不加引号 value={{ q }}', 'x onfocus=window.__x=1 autofocus'),
    ('attr_quoted', '属性加引号 value="{{ q }}"', '" onfocus="window.__x=1" autofocus="'),
    ('js_string', '脚本里的字符串 "{{ q }}"', '";window.__x=1;//'),
    ('js_bare', '脚本里直接 {{ q }}(没有引号)', '1;window.__x=1'),
    ('js_tojson', '脚本里 {{ q|tojson }}', '1;window.__x=1'),
    ('href', 'href="{{ q }}"(页面自动点击链接)', 'javascript:window.__x=1'),
    ('markup', 'Markup("<b>" + q + "</b>") 拼接后输出', '<img src=x onerror=window.__x=1>'),
]
print('== 同一个 Flask 页面的 9 种输出位置,各用一个攻击载荷,在真实 Chrome 里看脚本是否执行(window.__x 被置位就算执行)')
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '1', 'app:app']) as s:
    R['cases'] = {}
    for name, label, payload in cases:
        r = s.get(f'/c/{name}?q={up.quote(payload)}'); src = r[2].decode(); line = [l for l in src.split('<body>')[1].split('</body>')[0].splitlines() if l.strip()][0][:110]
        dom = chrome_dom(f'http://127.0.0.1:{s.port}/c/{name}?q={up.quote(payload)}'); m = re.search(r'data-result="([^"]*)"', dom); res = m.group(1) if m else '(没有结果)'
        print(f'  {label:<34} 载荷 {payload[:34]!r}'); print(f'      服务端输出的 HTML: {line}'); print(f'      浏览器结果:{res}'); R['cases'][name] = dict(label=label, payload=payload, html=line, result=res)
save('f123', R)
