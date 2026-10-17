import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f181'); R = {}
LEVELS = '''
import logging, sys
from flask import Flask
CASE = sys.argv[1]
if CASE == "basic": logging.basicConfig(level=logging.INFO, format="%(levelname)s root-handler: %(message)s")
app = Flask(__name__)
if CASE == "debug": app.debug = True
if CASE == "setlevel": app.logger.setLevel(logging.INFO)
for n in ("debug", "info", "warning", "error"): getattr(app.logger, n)(f"{n} message")
print("handlers on app.logger:", [type(h).__name__ for h in app.logger.handlers], "| effective level:", logging.getLevelName(app.logger.getEffectiveLevel()))
'''
GAPP = '''
import logging, os
from flask import Flask
app = Flask(__name__)
if os.environ.get("HOOK") == "1":
    g = logging.getLogger("gunicorn.error"); app.logger.handlers = g.handlers; app.logger.setLevel(g.level)
@app.get("/")
def index():
    app.logger.info("info from view"); app.logger.warning("warning from view"); return "ok"
@app.get("/boom")
def boom(): 1 / 0
'''
JAPP = '''
import json, logging, logging.config
from flask import Flask, request, has_request_context
class Req(logging.Filter):
    def filter(self, rec):
        rec.method = request.method if has_request_context() else None; rec.path = request.path if has_request_context() else None; return True
class J(logging.Formatter):
    def format(self, rec):
        d = {"level": rec.levelname, "msg": rec.getMessage(), "logger": rec.name, "method": rec.method, "path": rec.path}
        if rec.exc_info: d["exc"] = self.formatException(rec.exc_info).splitlines()[-1]
        return json.dumps(d, ensure_ascii=False)
logging.config.dictConfig({"version": 1, "disable_existing_loggers": False, "filters": {"req": {"()": Req}}, "formatters": {"j": {"()": J}},
    "handlers": {"h": {"class": "logging.StreamHandler", "formatter": "j", "filters": ["req"]}}, "root": {"level": "INFO", "handlers": ["h"]}})
app = Flask(__name__)
@app.get("/hello")
def hello(): app.logger.info("handling hello"); return "ok"
@app.get("/boom")
def boom(): 1 / 0
'''
DEV = '''
import sys, logging
from flask import Flask
app = Flask(__name__)
if sys.argv[2] == "quiet": logging.getLogger("werkzeug").setLevel(logging.WARNING)
@app.get("/")
def index(): return "ok"
app.run(port=int(sys.argv[1]))
'''
d = mkapp('f181', {'levels.py': LEVELS, 'gapp.py': GAPP, 'japp.py': JAPP, 'dev.py': DEV})
print('== 一:Flask 自带的 app.logger:默认没有配置时,四个级别各有哪些会输出?(每种设置跑一个新进程,看 stderr)')
R['lv'] = {}
for label, case in (('什么都不配(debug 关)', 'none'), ('app.debug = True', 'debug'), ('app.logger.setLevel(INFO)', 'setlevel'), ('先 logging.basicConfig(level=INFO)', 'basic')):
    rc, out = pyfile(d, 'levels.py', args=[case]); lines = out.splitlines(); shown = [w for w in ('debug', 'info', 'warning', 'error') if any(f'{w} message' in l for l in lines)]
    print(f'  [{label}] 输出的级别:{shown}'); [print('      ' + l[:120]) for l in lines]; R['lv'][label] = [shown, lines[-1]]
print()
print('== 二:在 gunicorn 下(--log-level info,错误日志到 stdout):view 里 app.logger.info / warning,与 /boom 里的未捕获异常')
R['g'] = {}
for label, hook in (('什么都不配', '0'), ('把 gunicorn.error 的 handler 接到 app.logger', '1')):
    with Server(d, ['gunicorn', '-w', '1', '--log-level', 'info', '--error-logfile', '-', '-b', '127.0.0.1:{port}', 'gapp:app'], HOOK=hook) as s:
        s.get('/'); s.get('/boom'); time.sleep(0.3); lg = [l for l in s.logtext().splitlines() if 'view' in l or 'Exception on' in l or 'ZeroDivision' in l]
    print(f'  [{label}]'); [print('    ' + l[:130]) for l in lg]; R['g'][label] = lg
print()
print('== 三:dictConfig 配一个 JSON 格式 + 请求信息的 filter(根 logger 一个 handler),/hello 与 /boom')
with Server(d, ['gunicorn', '-w', '1', '-b', '127.0.0.1:{port}', 'japp:app']) as s:
    s.get('/hello'); s.get('/boom'); time.sleep(0.3); lg = [l for l in s.logtext().splitlines() if l.startswith('{')]
[print('  ' + l[:170]) for l in lg]; R['json'] = lg
print()
print('== 四:开发服务器的访问日志来自 werkzeug 的 logger:默认与 getLogger("werkzeug").setLevel(WARNING) 之后')
R['dev'] = {}
for label, mode in (('默认', 'loud'), ('werkzeug 设为 WARNING', 'quiet')):
    with Server(d, ['python', 'dev.py', '{port}', mode]) as s:
        s.get('/'); time.sleep(0.3); lg = [l.strip()[:110] for l in s.logtext().splitlines() if '"GET' in l]
    print(f'  [{label}] 访问日志行:{lg}'); R['dev'][label] = lg
save('f181', R)
