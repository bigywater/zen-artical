import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f2'); R = {}
APP = '''
import os, time, threading
from flask import Flask
app = Flask(__name__)
@app.get("/")
def index(): return f"pid={os.getpid()} run_main={os.environ.get('WERKZEUG_RUN_MAIN')}\\n"
@app.get("/slow")
def slow():
    time.sleep(0.5); return "slow done\\n"
if __name__ == "__main__":
    app.run(port=int(os.environ["PORT"]), debug=os.environ.get("DBG") == "1", host=os.environ.get("HOST", "127.0.0.1"), threaded=os.environ.get("THR", "1") == "1")
'''
d = app('f2', {'app.py': APP})
def procs(port):
    r = subprocess.run(['ps', '-axo', 'pid,ppid,command'], capture_output=True, text=True).stdout
    return [l.strip() for l in r.split('\n') if 'app.py' in l and 'ps -axo' not in l and 'grep' not in l]
def listen(port):
    r = subprocess.run(['lsof', '-nP', f'-iTCP:{port}', '-sTCP:LISTEN'], capture_output=True, text=True).stdout.strip().split('\n')[1:]
    return sorted(set(re.sub(r'.*TCP\s+', '', l).replace(' (LISTEN)', '') for l in r))
print('== 一:python app.py(app.run 的默认参数)启动后:终端里的启动信息、监听地址、进程')
src(APP, 'app.py')
port = free_port()
with Server(d, ['python', 'app.py'], port=port, PORT=port) as s:
    time.sleep(0.3); st, h, b, dt = s.get('/'); print(f'  GET / → {st} {b.decode().strip()}')
    print('  启动时服务器打印的内容(app.run 往 stderr 写):'); L = s.logtext().split('\n'); pr('\n'.join(L), 8); R['banner'] = L[:8]
    print('  监听地址:', listen(port)); R['listen'] = listen(port)
    pp = procs(port); print(f'  相关进程数 {len(pp)}:'); pr('\n'.join(re.sub(r'/[^ ]*python', 'python', p)[:100] for p in pp), 4); R['nproc'] = len(pp)
print()
print('== 二:debug=True:多出一个重载器子进程;子进程里 WERKZEUG_RUN_MAIN 被设成 true;改了文件会自动重启')
port = free_port()
with Server(d, ['python', 'app.py'], port=port, PORT=port, DBG=1) as s:
    time.sleep(0.5); st, h, b, dt = s.get('/'); first = b.decode().strip(); print(f'  GET / → {first}')
    pp = procs(port); print(f'  相关进程数 {len(pp)}:'); pr('\n'.join(re.sub(r'/[^ ]*python', 'python', p)[:100] for p in pp), 4); R['nproc_dbg'] = len(pp)
    print('  启动信息:'); L = s.logtext().split('\n'); pr('\n'.join(L), 10); R['banner_dbg'] = L[:10]
    p0 = (d / 'app.py').read_text(); (d / 'app.py').write_text(p0 + '\n# touched\n'); t0 = time.time()
    while time.time() - t0 < 15:
        if 'Detected change' in s.logtext(): break
        time.sleep(0.05)
    t_detect = time.time() - t0; time.sleep(1.0)
    for _ in range(40):
        try: st, h, b, dt = s.get('/'); break
        except Exception: time.sleep(0.1)
    print(f'  改动 app.py 后 {t_detect:.2f} 秒日志出现重载;再请求:{b.decode().strip()}'); R['reload'] = [round(t_detect, 2), first, b.decode().strip()]
    print('  重载相关日志:'); pr('\n'.join(l for l in s.logtext().split('\n') if 'Detected' in l or 'Restarting' in l or 'Debugger' in l), 4); R['reload_log'] = [l for l in s.logtext().split('\n') if 'Detected' in l or 'Restarting' in l]
(d / 'app.py').write_text(p0)
print()
print('== 三:host 参数:默认只监听 127.0.0.1;host="0.0.0.0" 监听所有网卡(用 lsof 看)')
R['host'] = {}
for h_ in ('127.0.0.1', '0.0.0.0'):
    port = free_port()
    with Server(d, ['python', 'app.py'], port=port, PORT=port, HOST=h_) as s:
        time.sleep(0.2); R['host'][h_] = listen(port); print(f'  host={h_:<10} → lsof 看到的监听:{R["host"][h_]}')
print()
print('== 四:threaded 参数:同时发 2 个各睡 0.5 秒的请求,总耗时(每种 3 次)')
R['thr'] = {}
for thr in ('1', '0'):
    port = free_port(); ts = []
    with Server(d, ['python', 'app.py'], port=port, PORT=port, THR=thr) as s:
        for _ in range(3):
            res = []; th = [threading.Thread(target=lambda: res.append(s.get('/slow')[3])) for _ in range(2)]; t0 = time.perf_counter(); [t.start() for t in th]; [t.join() for t in th]; ts.append((time.perf_counter() - t0) * 1000)
    R['thr'][thr] = ts; print(f'  threaded={"True" if thr == "1" else "False":<5} 总耗时 {", ".join(f"{x:.0f}" for x in ts)} ms(中位数 {median(ts):.0f})')
print()
print('== 五:flask run 与 app.run 的差别:flask --app app run 不执行 if __name__ == "__main__" 里的代码')
port = free_port()
with Server(d, ['flask', '--app', 'app', 'run', '--port', str(port)], port=port) as s:
    time.sleep(0.2); st, h, b, dt = s.get('/'); print(f'  flask --app app run --port {port} → GET / {st} {b.decode().strip()}'); print('  启动信息:'); L = s.logtext().split('\n'); pr('\n'.join(L), 8); R['flask_run'] = L[:8]
port = free_port()
with Server(d, ['flask', '--app', 'app', 'run', '--port', str(port), '--debug'], port=port) as s:
    time.sleep(0.5); print('  加 --debug:'); L = [l for l in s.logtext().split('\n') if 'Debug' in l or 'Debugger' in l]; pr('\n'.join(L), 4); R['flask_run_dbg'] = L
save('f2', R)
