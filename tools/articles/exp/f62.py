import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f62'); R = {}
import traceback
d = mkapp('f62', {'main.py': '''
import time
from flask import Flask, render_template, stream_template, abort
from jinja2 import StrictUndefined
app = Flask(__name__)
@app.get("/ok")
def ok(): return render_template("ok.html", n=3)
@app.get("/undef")
def undef(): return render_template("undef.html")
@app.get("/syntax")
def syntax(): return render_template("syntax.html")
@app.get("/missing-tpl")
def missing_tpl(): return render_template("nope.html")
@app.get("/typeerr")
def typeerr(): return render_template("typeerr.html", x=None)
@app.get("/in-include")
def in_include(): return render_template("outer.html")
@app.get("/stream-bad")
def stream_bad(): return stream_template("stream_bad.html", items=[1, 2, 3, 4, 5])
@app.get("/render-bad")
def render_bad(): return render_template("stream_bad.html", items=[1, 2, 3, 4, 5])
@app.get("/lenient")
def lenient():
    from flask import render_template_string
    return render_template_string("[{{ nothing }}]")
@app.errorhandler(500)
def h500(e): return "自定义 500 页", 500
''', 'templates/ok.html': '{% for i in range(n) %}<li>{{ i }}</li>{% endfor %}\n', 'templates/undef.html': '第 1 行\n第 2 行 {{ user.name.first }}\n第 3 行', 'templates/syntax.html': '第 1 行\n{% if x %}\n第 3 行\n{% for %}\n', 'templates/typeerr.html': '行1\n行2 {{ x + 1 }}\n行3', 'templates/outer.html': 'outer 第 1 行\n{% include "inner.html" %}\nouter 第 3 行', 'templates/inner.html': 'inner 第 1 行\n{{ 1 / 0 }}\n', 'templates/stream_bad.html': '<ul>\n{% for i in items %}<li>{{ i }}{% if i == 4 %}{{ 1 / 0 }}{% endif %}</li>\n{% endfor %}</ul>\n'})
sys.path.insert(0, str(d)); os.chdir(d)
import main
app = main.app; app.logger.disabled = True; c = app.test_client()
print('== 一:各种模板错误在 Flask 里变成什么:异常类型与消息(TESTING=True 让异常原样传出来看)')
app.testing = True; R['errs'] = {}
for p in ('/undef', '/syntax', '/missing-tpl', '/typeerr', '/in-include'):
    try: c.get(p); print(f'  GET {p:<13} → 没有异常')
    except Exception as e:
        tb = traceback.extract_tb(e.__traceback__); tpl_frames = [f'{os.path.basename(f.filename)}:{f.lineno}' for f in tb if f.filename.endswith(('.html',))]
        R['errs'][p] = [type(e).__name__, str(e), tpl_frames]; print(f'  GET {p:<13} → {type(e).__name__}: {str(e)[:70]} | traceback 里的模板帧: {tpl_frames}')
print('  (模板帧 = Jinja 把渲染异常的 traceback 改写成指向模板文件与行号;语法错误时异常对象自带 filename 与 lineno)')
try: c.get('/syntax')
except Exception as e: print('  TemplateSyntaxError 的属性:lineno =', e.lineno, '| name =', e.name, '| filename 末尾 =', os.path.basename(e.filename or ''), '| message =', e.message); R['syntax_attrs'] = [e.lineno, e.name, e.message]
print()
print('== 二:不是测试模式时:Flask 把模板异常当作普通 500;日志里有完整 traceback')
app.testing = False
for p in ('/undef', '/missing-tpl', '/in-include'): r = c.get(p); print(f'  GET {p:<13} → {r.status_code} {r.get_data(as_text=True)!r}'); R.setdefault('as500', {})[p] = [r.status_code, r.get_data(as_text=True)]
print()
print('== 三:Undefined 的宽容:缺失的变量输出空字符串,不报错;读缺失变量的属性才报 UndefinedError;换 StrictUndefined 后立刻报错')
from jinja2 import StrictUndefined
c2 = app.test_client()
print('  默认 Undefined 渲染 [{{ nothing }}] →', repr(app.test_client().get('/lenient').get_data(as_text=True)[:40]))
app.jinja_env.undefined = StrictUndefined; app.testing = True
try: app.test_client().get('/lenient')
except Exception as e: print('  jinja_env.undefined = StrictUndefined 后 →', type(e).__name__ + ':', e); R['strict'] = f'{type(e).__name__}: {e}'
app.jinja_env.undefined = __import__('jinja2').Undefined; app.testing = False
print()
print('== 四:render_template 是「先渲染完再返回」:异常发生时客户端什么都没收到(只有错误页);stream_template 是边渲染边发送:出错时已经发出去的部分会留在客户端')
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '--workers', '1', 'main:app']) as s:
    R['real'] = {}
    for p in ('/render-bad', '/stream-bad'):
        r = subprocess.run(['curl', '-s', '-i', f'http://127.0.0.1:{s.port}{p}'], capture_output=True); out = r.stdout.decode('utf-8', 'replace'); head, _, body = out.partition('\r\n\r\n'); status = head.split('\r\n')[0]; R['real'][p] = [status, body[:120], r.returncode]
        print(f'  GET {p:<12} → {status} | curl 退出码 {r.returncode} | 收到的正文 {body[:120]!r}')
    time.sleep(0.3); L = [l for l in s.logtext().split('\n') if 'ZeroDivisionError' in l or 'Error handling request' in l or 'Exception on' in l][:3]; print('  服务器日志里的错误行:', L); R['log'] = L
print('  curl 退出码 18 表示「传输提前结束」(chunked 响应没有正常收尾)。/stream-bad 已经发出的 <ul>、<li>1 等内容留在了客户端,状态码仍是 200,因为状态行在渲染之前就发出去了。')
print()
print('== 五:调试页(debug=True)里模板错误的呈现:traceback 会指向模板文件与行号,并显示出错的源码行')
d2 = mkapp('f62d', {'dbg.py': 'from flask import Flask, render_template\napp = Flask(__name__)\n@app.get("/u")\ndef u(): return render_template("undef.html")\n', 'templates/undef.html': '第 1 行\n第 2 行 {{ user.name.first }}\n第 3 行'})
port = free_port()
with Server(d2, ['flask', '--app', 'dbg', 'run', '--port', str(port), '--debug', '--no-reload'], port=port) as s:
    time.sleep(0.4); st, h, b, dt = s.get('/u'); t = b.decode(); has_tpl = 'undef.html' in t; has_line = 'user.name.first' in t; print(f'  debug 页面:状态 {st};含模板文件名 undef.html: {has_tpl};含出错的模板源码行 {{{{ user.name.first }}}}: {has_line};含 UndefinedError: {"UndefinedError" in t}'); R['debug_page'] = [st, has_tpl, has_line, 'UndefinedError' in t]
save('f62', R)
