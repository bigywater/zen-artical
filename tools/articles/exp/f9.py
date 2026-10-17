import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f9'); R = {}
import threading, flask
from flask import Flask
print('== 一:before_first_request 在这个版本里还在吗')
app = Flask('x'); print('  Flask 版本', flask.__version__, '| hasattr(app, "before_first_request") =', hasattr(app, 'before_first_request'))
try:
    @app.before_first_request
    def init(): pass
except AttributeError as e: print('  用 @app.before_first_request → AttributeError:', e); R['attr'] = str(e)
print('  Flask 类上还留着的 before_ 开头的方法:', sorted(n for n in dir(Flask) if n.startswith('before')))
R['before_methods'] = sorted(n for n in dir(Flask) if n.startswith('before'))
print()
print('== 二:替代方案 A:启动时在应用工厂里初始化(一次、在接收请求之前)')
src('''
    def create_app():
        app = Flask(__name__)
        with app.app_context():
            warm_up()          # 加载配置、建表、预热缓存……
        return app
''')
cnt = {'n': 0}
def warm_up(): time.sleep(0.05); cnt['n'] += 1
def create_app():
    a = Flask('fac'); a.get('/')(lambda: 'ok')
    with a.app_context(): warm_up()
    return a
t0 = time.perf_counter(); a = create_app(); dt = ms(t0); c = a.test_client(); [c.get('/') for _ in range(5)]
print(f'  create_app() 耗时 {dt:.0f} ms(包含 50 ms 的 warm_up);之后 5 个请求,warm_up 总共执行了 {cnt["n"]} 次'); R['factory'] = [round(dt), cnt['n']]
print()
print('== 三:替代方案 B:在 before_request 里用标志位——不加锁,并发的第一批请求会重复初始化')
APP = '''
import os, time, threading
from flask import Flask
app = Flask(__name__)
LOG = os.environ["INIT_LOG"]
_done = False
_lock = threading.Lock()
def init(tag):
    time.sleep(0.2)
    with open(LOG, "a") as f: f.write(f"{tag} pid={os.getpid()}\\n")
if os.environ["MODE"] == "nolock":
    @app.before_request
    def first():
        global _done
        if not _done:
            init("nolock"); _done = True
elif os.environ["MODE"] == "lock":
    @app.before_request
    def first():
        global _done
        if not _done:
            with _lock:
                if not _done:
                    init("lock"); _done = True
elif os.environ["MODE"] == "module":
    init("module-level")
@app.get("/")
def idx(): return "ok"
'''
d = mkapp('f9', {'app.py': APP})
src(APP.split('@app.get')[0].split('_lock = threading.Lock()')[1], 'app.py 中两种写法(省略 init 的定义)')
R['race'] = {}
def run_mode(mode, nreq=12, workers=1, extra_args=()):
    log = d / f'init_{mode}_{workers}{"p" if extra_args else ""}.log'; log.unlink(missing_ok=True)
    with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '--threads', '16', '--workers', str(workers), *extra_args, 'app:app'], MODE=mode, INIT_LOG=str(log)) as s:
        time.sleep(0.5 if workers > 1 else 0.1); res = []; ths = [threading.Thread(target=lambda: res.append(s.get('/')[0])) for _ in range(nreq)]; [t.start() for t in ths]; [t.join() for t in ths]; time.sleep(0.5)
    L = log.read_text().strip().split('\n') if log.exists() else []; return L, res
for mode in ('nolock', 'lock', 'module'):
    L, res = run_mode(mode); print(f'  MODE={mode:<7} 1 个 worker、16 线程,12 个并发的第一批请求:init 执行了 {len(L)} 次(都返回 200: {all(r == 200 for r in res)})'); R['race'][mode] = len(L)
print()
print('== 四:多个 worker 进程:每个进程各自初始化一次(--workers 3);--preload 让主进程先导入应用')
R['workers'] = {}
for label, ex in (('--workers 3', ()), ('--workers 3 --preload', ('--preload',))):
    L, res = run_mode('module', nreq=9, workers=3, extra_args=ex); pids = sorted({l.split('pid=')[1] for l in L}); print(f'  {label:<24} MODE=module:init 执行 {len(L)} 次,涉及 {len(pids)} 个不同的 pid'); R['workers'][label] = [len(L), len(pids)]
L, res = run_mode('lock', nreq=18, workers=3); pids = sorted({l.split('pid=')[1] for l in L}); print(f'  --workers 3 MODE=lock:   init 执行 {len(L)} 次,涉及 {len(pids)} 个不同的 pid(线程锁只在进程内有效)'); R['workers']['lock3'] = [len(L), len(pids)]
save('f9', R)
