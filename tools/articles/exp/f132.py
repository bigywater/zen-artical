import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f132'); R = {}
APP = '''
import os
from flask import Flask
app = Flask(__name__)
app.config["SECRET_KEY"] = "hidden-secret-value"
if os.environ.get("APP_DEBUG") == "1": app.debug = True
@app.get("/")
def index(): return "ok"
@app.get("/boom")
def boom():
    db_password = "s3cret-in-local-var"
    return 1 / 0
'''
d = mkapp('f132', {'app.py': APP})
def summarize(body):
    return {'含 "Werkzeug Debugger"': 'Werkzeug Debugger' in body, '含源码行 "return 1 / 0"': 'return 1 / 0' in body, '含文件路径 app.py': 'app.py' in body, '含异常类型 ZeroDivisionError': 'ZeroDivisionError' in body, '含 console 脚本(交互式控制台)': 'console' in body.lower() and 'debugger=yes' in body or '__debugger__' in body, '含局部变量值 s3cret': 's3cret-in-local-var' in body, '含 SECRET_KEY 的值': 'hidden-secret-value' in body}
print('== 一:flask run --debug 时,出错的页面里有什么(真实服务器)')
with Server(d, ['flask', '--app', 'app', 'run', '--debug', '--no-reload', '--port', '{port}']) as s:
    r = s.get('/boom'); body = r[2].decode(); sm = summarize(body); print('  状态码', r[0]); [print(f'    {k:<34} {v}') for k, v in sm.items()]; R['debug'] = [r[0], sm]
    log = s.logtext(); print('  服务器启动日志里的提示:', [l.strip() for l in log.splitlines() if 'Debug' in l or 'PIN' in l][:4]); R['debug_log'] = [l.strip() for l in log.splitlines() if 'Debug' in l or 'PIN' in l][:4]
print()
print('== 二:不开 debug 的 flask run:同一个出错的页面')
with Server(d, ['flask', '--app', 'app', 'run', '--no-reload', '--port', '{port}']) as s:
    r = s.get('/boom'); body = r[2].decode(); sm = summarize(body); print('  状态码', r[0], '| 响应:', body.strip().replace('\n', ' ')[:110]); [print(f'    {k:<34} {v}') for k, v in sm.items()]; R['nodebug'] = [r[0], sm, body.strip().replace('\n', ' ')[:110]]
print()
print('== 三:gunicorn 加载了 app.debug = True 的应用:Werkzeug 调试器不会出现')
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', 'app:app'], APP_DEBUG='1') as s:
    r = s.get('/boom'); body = r[2].decode(); sm = summarize(body); print('  状态码', r[0], '| 响应:', body.strip().replace('\n', ' ')[:110]); print('  含调试器页面:', sm['含 "Werkzeug Debugger"']); R['gunicorn'] = [r[0], sm['含 "Werkzeug Debugger"'], body.strip().replace('\n', ' ')[:110]]
    print('  gunicorn 日志里记录了异常(堆栈在服务端日志里,不在响应里):', 'ZeroDivisionError' in s.logtext()); R['gunicorn_log'] = 'ZeroDivisionError' in s.logtext()
print()
print('== 四:调试服务器默认只监听 127.0.0.1;--host 0.0.0.0 才对外')
for label, extra in (('默认', []), ('--host 0.0.0.0', ['--host', '0.0.0.0'])):
    with Server(d, ['flask', '--app', 'app', 'run', '--debug', '--no-reload', '--port', '{port}'] + extra) as s:
        log = s.logtext(); line = [l.strip() for l in log.splitlines() if 'Running on' in l]; print(f'  {label:<16} → {line[:2]}'); R.setdefault('bind', {})[label] = line[:2]
print()
print('== 五:app.debug 与 FLASK_DEBUG 环境变量、--debug 参数的关系')
R['flags'] = {}
for label, argv, env_ in (('flask run(无参数)', [], {}), ('flask run --debug', ['--debug'], {}), ('FLASK_DEBUG=1 flask run', [], {'FLASK_DEBUG': '1'}), ('FLASK_DEBUG=0 flask run --debug', ['--debug'], {'FLASK_DEBUG': '0'})):
    with Server(d, ['flask', '--app', 'app', 'run', '--no-reload', '--port', '{port}'] + argv, **env_) as s:
        r = s.get('/boom'); dbg = 'Werkzeug Debugger' in r[2].decode(); print(f'  {label:<34} → 调试器页面: {dbg}'); R['flags'][label] = dbg
save('f132', R)
