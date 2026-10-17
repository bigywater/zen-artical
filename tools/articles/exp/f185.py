import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
import json as _j
tee('f185'); R = {}
DUP = '''
import logging, sys, io, json
from flask import Flask
buf_root = io.StringIO(); buf_app = io.StringIO()
def fresh():
    root = logging.getLogger(); root.handlers = []; root.setLevel(logging.INFO)
    lg = logging.getLogger("myapp"); lg.handlers = []; lg.propagate = True; lg.setLevel(logging.INFO); return root, lg
out = {}
def count(case, setup):
    root, lg = fresh(); b = io.StringIO(); setup(root, lg, b); lg.info("one message"); out[case] = b.getvalue().count("one message")
def h(b): x = logging.StreamHandler(b); return x
count("只在 app logger 上加 handler(根 logger 没有)", lambda r, l, b: l.addHandler(h(b)))
count("根 logger 有 handler 且 app logger 也加了", lambda r, l, b: (r.addHandler(h(b)), l.addHandler(h(b))))
def both_off(r, l, b): r.addHandler(h(b)); l.addHandler(h(b)); l.propagate = False
count("两处都有 handler,但 app logger 关了 propagate", both_off)
def init(l, b):
    l.addHandler(h(b))
def repeated(r, l, b):
    for _ in range(3): init(l, b)
count("初始化函数被调用了 3 次(每次都 addHandler)", repeated)
def guarded(r, l, b):
    for _ in range(3):
        if not l.handlers: init(l, b)
count("同上,但加之前判断 handlers 是否已存在", guarded)
print("JSON:" + json.dumps(out, ensure_ascii=False))
'''
GAPP = '''
import os, logging
from flask import Flask
logging.basicConfig(level=logging.INFO, format="%(process)d %(message)s")
logging.getLogger("boot").info("module imported in pid %s", os.getpid())
app = Flask(__name__)
@app.get("/")
def i(): return str(os.getpid())
'''
DEVAPP = '''
import os, logging, sys
from flask import Flask
logging.basicConfig(level=logging.INFO, format="%(process)d %(message)s")
logging.getLogger("boot").info("module top-level ran in pid %s", os.getpid())
app = Flask(__name__)
if __name__ == "__main__": app.run(port=int(sys.argv[1]), debug=True)
'''
WR = '''
import logging, logging.handlers, os, sys, time
mode, n = sys.argv[1], int(sys.argv[2]); tag = sys.argv[3]
lg = logging.getLogger("w"); lg.setLevel(logging.INFO)
if mode == "rotating": lg.addHandler(logging.handlers.RotatingFileHandler("rot.log", maxBytes=20000, backupCount=200))
else: lg.addHandler(logging.FileHandler("plain.log"))
for i in range(n): lg.info("proc=%s line=%05d %s", tag, i, "x" * 60)
'''
d = mkapp('f185', {'dup.py': DUP, 'gapp.py': GAPP, 'devapp.py': DEVAPP, 'wr.py': WR})
rc, o = pyfile(d, 'dup.py'); D = _j.loads([l for l in o.splitlines() if l.startswith('JSON:')][-1][5:]); R['dup'] = D
print('== 一:同一条日志被输出多次:handler 加在哪里、被加了几次(一条 logger.info,数输出里它出现了几遍)')
for k, v in D.items(): print(f'  {k:<42} → 输出 {v} 次')
print()
print('== 二:gunicorn 3 个 worker 时,模块顶层的日志(例如启动时打印一行配置)输出几次?--preload 与不 preload')
R['preload'] = {}
for label, extra in (('默认(每个 worker 自己导入应用)', []), ('--preload(master 导入一次再 fork)', ['--preload'])):
    with Server(d, ['gunicorn', '-w', '3', '-b', '127.0.0.1:{port}'] + extra + ['gapp:app']) as s:
        time.sleep(1.0); lg = [l for l in s.logtext().splitlines() if 'module imported' in l]
    print(f'  {label}:顶层日志 {len(lg)} 行,pid {sorted(set(l.split()[0] for l in lg))}'); R['preload'][label] = len(lg)
print()
print('== 三:开发服务器 python app.py(debug=True,有 reloader):模块顶层日志输出几次?')
port = free_port(); pr_ = subprocess.Popen([str(PY), 'devapp.py', str(port)], cwd=d, env=env(d), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
time.sleep(2.0); os.killpg(pr_.pid, signal.SIGTERM); txt = pr_.stdout.read(); lg = [l for l in txt.splitlines() if 'module top-level' in l]
print(f'  顶层日志 {len(lg)} 行,pid {sorted(set(l.split()[0] for l in lg))}(reloader 的父进程和子进程各导入了一次)'); R['dev'] = len(lg)
print()
print('== 四:3 个进程同时写同一个日志文件,每个 3000 行(共 9000 行,每行约 90 字节)')
R['files'] = {}
for mode, name in (('plain', 'FileHandler(追加模式)'), ('rotating', 'RotatingFileHandler(maxBytes=20000,备份保留 200 个,保证不会因备份满而丢)')):
    for f in d.glob('*.log*'): f.unlink()
    ps = [subprocess.Popen([str(PY), 'wr.py', mode, '3000', t], cwd=d, env=env(d)) for t in 'abc']; [p.wait() for p in ps]
    files = sorted(d.glob('plain.log' if mode == 'plain' else 'rot.log*')); lines = []; bad = 0
    for f in files:
        for l in f.read_text().splitlines():
            if re.match(r'^proc=[abc] line=\d{5} x{60}$', l): lines.append(l)
            else: bad += 1
    print(f'  {name}:文件 {len(files)} 个,完整的行 {len(lines)} / 9000,损坏的行 {bad}'); R['files'][mode] = [len(files), len(lines), bad]
save('f185', R)
