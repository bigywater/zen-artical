import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f15'); R = {}
import logging
from flask import Flask
print('== 一:debug 开关在哪里设置,各种方式的效果(用子进程看 app.debug)')
d = mkapp('f15', {'a.py': '''
import os
from flask import Flask
app = Flask(__name__)
if os.environ.get("SET_CFG"): app.config["DEBUG"] = True
if os.environ.get("SET_ATTR"): app.debug = True
print("app.debug =", app.debug, "| config[DEBUG] =", app.config["DEBUG"], "| logger 级别 =", app.logger.level, "| jinja auto_reload =", app.jinja_env.auto_reload, "| TEMPLATES_AUTO_RELOAD =", app.config["TEMPLATES_AUTO_RELOAD"])
'''})
R['debug'] = {}
for label, ex in (('默认', {}), ('FLASK_DEBUG=1', {'FLASK_DEBUG': '1'}), ('FLASK_DEBUG=0', {'FLASK_DEBUG': '0'}), ('app.config["DEBUG"]=True', {'SET_CFG': '1'}), ('app.debug = True', {'SET_ATTR': '1'})):
    rc, o = pyfile(d, 'a.py', **ex); R['debug'][label] = o; print(f'  {label:<26} {o}')
print('  (没有设置 logger 级别时 level 为 0 = NOTSET;debug 时 Flask 在第一次访问 logger 时把级别设成 DEBUG)')
print()
print('== 二:出错时的响应:debug=False 是一个简短的 500 页;debug=True 是 Werkzeug 调试器页(含完整 traceback 与交互式控制台)')
APP = '''
from flask import Flask
app = Flask(__name__)
@app.get("/boom")
def boom():
    secret_local = 42
    return 1 / 0
'''
d2 = mkapp('f15b', {'dbg.py': APP}); R['err'] = {}
for label, flag in (('debug=False', '0'), ('debug=True', '1')):
    port = free_port()
    with Server(d2, ['flask', '--app', 'dbg', 'run', '--port', str(port)] + (['--debug', '--no-reload'] if flag == '1' else []), port=port) as s:
        time.sleep(0.4); st, h, b, dt = s.get('/boom'); t = b.decode(); R['err'][label] = dict(status=st, size=len(b), has_traceback='Traceback' in t, has_debugger='Werkzeug Debugger' in t or '__debugger__' in t, has_source='return 1 / 0' in t, has_console='console' in t.lower())
        print(f'  {label:<12} → {st} | 正文 {len(b)} 字节 | 含 Traceback: {R["err"][label]["has_traceback"]} | 含调试器标记: {R["err"][label]["has_debugger"]} | 页面里能看到源码行 return 1 / 0: {R["err"][label]["has_source"]}')
        if flag == '1': dbg_port = port
print()
print('== 三:调试器的控制台要靠 PIN 解锁:没有 PIN 时请求控制台执行代码会被拒绝(只用本机自己的实验服务器验证)')
port = free_port()
with Server(d2, ['flask', '--app', 'dbg', 'run', '--port', str(port), '--debug', '--no-reload'], port=port, WERKZEUG_DEBUG_PIN='123-456-789') as s:
    time.sleep(0.4); st, h, b, dt = s.get('/boom'); t = b.decode(); import re as _re
    ssec = _re.search(r'SECRET\s*=\s*"([^"]+)"', t); secret = ssec.group(1); frames = _re.findall(r'id="frame-(\d+)"', t); frm = frames[-1]
    ev = _re.search(r'EVALEX\s*=\s*(\w+)', t); print('  页面里的 EVALEX =', ev.group(1), '| 页面内嵌了 SECRET:', bool(secret), '| 页面里的栈帧数:', len(frames)); R['page'] = [ev.group(1), len(frames)]
    q = f'/boom?__debugger__=yes&cmd=__import__("os").getpid()&frm={frm}&s={secret}'.replace('"', '%22').replace('(', '%28').replace(')', '%29')
    def is_exec(b_): return 'class="input"' in b_ or '&gt;&gt;&gt;' in b_ or '>>>' in b_
    st1, h1, b1, _ = s.get(q); body1 = b1.decode(); print(f'  ① 没有 PIN 认证就请求在栈帧里执行代码 → {st1};返回的是应用自己的 500 页(含 "ZeroDivisionError"): {"ZeroDivisionError" in body1};没有执行结果: {"cmd" in body1 and False or not _re.search(r">>> |<span class=.?output", body1)}'); R['nopin'] = [st1, 'ZeroDivisionError' in body1]
    st2, h2, b2, _ = s.get(f'/boom?__debugger__=yes&cmd=pinauth&pin=000-000-000&s={secret}'); print(f'  ② 用错误的 PIN 认证 → {st2} {b2.decode()}'); R['badpin'] = b2.decode()
    pin = '123-456-789'  # 用环境变量 WERKZEUG_DEBUG_PIN 固定的实验 PIN
    st3, h3, b3, _ = s.get(f'/boom?__debugger__=yes&cmd=pinauth&pin={pin}&s={secret}'); ck = [v for k, v in h3 if k.lower() == 'set-cookie']; print(f'  ③ 用正确的 PIN(实验里用 WERKZEUG_DEBUG_PIN 环境变量固定)认证 → {st3} {b3.decode()};响应设置了 cookie: {bool(ck)}(名字以 {ck[0].split("=")[0][:6] if ck else None}… 开头)'); R['goodpin'] = [b3.decode(), bool(ck)]
    cookie = ck[0].split(';')[0]
    st4, h4, b4, _ = s.get(q, headers={'Cookie': cookie}); out4 = b4.decode(); import os as _os; print(f'  ④ 带着认证 cookie 再执行 __import__("os").getpid() → {st4};返回内容里包含服务器进程的 pid: {str(s.p.pid) in out4 or "output" in out4};返回的前 80 字符:{out4[:80]!r}'); R['withcookie'] = [st4, out4[:80]]
    st5, h5, b5, _ = s.get('/boom?__debugger__=yes&cmd=resource&f=style.css'); print(f'  ⑤ 取调试器的静态资源(cmd=resource&f=style.css)→ {st5},{len(b5)} 字节(不需要 PIN)'); R['resource'] = [st5, len(b5)]
print()
print('== 四:模板自动重载:debug 下改了模板立刻生效;非 debug 下要重启')
d3 = mkapp('f15c', {'t.py': '''
from flask import Flask, render_template
app = Flask(__name__)
@app.get("/")
def i(): return render_template("p.html")
''', 'templates/p.html': 'version 1'})
R['reload'] = {}
for label, flag in (('非 debug', []), ('--debug', ['--debug', '--no-reload'])):
    (d3 / 'templates' / 'p.html').write_text('version 1'); port = free_port()
    with Server(d3, ['flask', '--app', 't', 'run', '--port', str(port)] + flag, port=port) as s:
        time.sleep(0.4); a1 = s.get('/')[2].decode(); (d3 / 'templates' / 'p.html').write_text('version 2'); time.sleep(0.2); a2 = s.get('/')[2].decode()
    R['reload'][label] = [a1, a2]; print(f'  {label:<8} 第一次读到 {a1!r};改文件后读到 {a2!r}')
print()
print('== 五:--debug 与 --reload 是两件事:--debug --no-reload 只开调试器与 DEBUG,不监视文件')
port = free_port()
with Server(d3, ['flask', '--app', 't', 'run', '--port', str(port), '--debug', '--no-reload'], port=port) as s:
    time.sleep(0.4); L = s.logtext(); print('  日志:'); pr('\n'.join(L.split('\n')[:8]), 8); R['noreload_log'] = L.split('\n')[:8]
save('f15', R)
