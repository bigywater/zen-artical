import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
import threading, shlex
tee('f189'); R = {}
APP = '''
import os, time
from flask import Flask
app = Flask(__name__)
@app.get("/slow")
def slow(): time.sleep(3); return "done"
@app.get("/ping")
def ping(): return "pong"
'''
ENTRY_PLAIN = '#!/bin/sh\necho "entrypoint start"\ngunicorn -w 1 -b 127.0.0.1:$PORT app:app\n'
ENTRY_EXEC = '#!/bin/sh\necho "entrypoint start"\nexec gunicorn -w 1 -b 127.0.0.1:$PORT app:app\n'
d = mkapp('f189', {'app.py': APP, 'entry_plain.sh': ENTRY_PLAIN, 'entry_exec.sh': ENTRY_EXEC}); os.chmod(d / 'entry_plain.sh', 0o755); os.chmod(d / 'entry_exec.sh', 0o755)
G = str(BIN / 'gunicorn')
def ps_tree(port):
    out = subprocess.run(['ps', '-axo', 'pid=,ppid=,command='], capture_output=True, text=True).stdout; rows = []
    for l in out.splitlines():
        p = l.split(None, 2)
        if len(p) == 3 and (f'127.0.0.1:{port}' in p[2] or f'PORT={port}' in p[2]) and 'ps -axo' not in p[2]: rows.append((int(p[0]), int(p[1]), p[2]))
    return rows
def alive(pid):
    try: os.kill(pid, 0); return True
    except ProcessLookupError: return False
def run_case(label, argv, extra_env=None):
    port = free_port(); e = env(d, PORT=port); e['PATH'] = f'{BIN}:' + e['PATH']
    argv = [a.replace('{port}', str(port)).replace('{G}', G) for a in argv]
    p = subprocess.Popen(argv, cwd=d, env=e, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    t0 = time.time()
    while time.time() - t0 < 10:
        with socket.socket() as s_:
            if s_.connect_ex(('127.0.0.1', port)) == 0: break
        time.sleep(0.05)
    time.sleep(0.3); rows = ps_tree(port); pids = {r[0] for r in rows}
    master = [r for r in rows if 'gunicorn' in r[2] and r[1] not in pids or ('gunicorn' in r[2] and r[0] == p.pid)]
    master_pid = [r[0] for r in rows if 'gunicorn' in r[2].lower() and (r[1] == p.pid or r[0] == p.pid or r[1] not in pids)][0] if rows else None
    same = master_pid == p.pid
    box = {}
    def req():
        t1 = time.perf_counter()
        try: r = http(port, 'GET', '/slow', timeout=15); box['r'] = str(r[0])
        except Exception as ex: box['r'] = type(ex).__name__
        box['t'] = round(time.perf_counter() - t1, 2)
    th = threading.Thread(target=req); th.start(); time.sleep(0.6)
    t1 = time.perf_counter(); os.kill(p.pid, signal.SIGTERM)
    try: p.wait(8); pexit = round(time.perf_counter() - t1, 2)
    except subprocess.TimeoutExpired: pexit = None
    th.join(); time.sleep(0.5)
    orphan = alive(master_pid) if master_pid and master_pid != p.pid else False
    still = bool(ps_tree(port))
    try: os.killpg(p.pid, signal.SIGKILL)
    except Exception: pass
    for r in ps_tree(port):
        try: os.kill(r[0], signal.SIGKILL)
        except Exception: pass
    time.sleep(0.3)
    return dict(label=label, same_pid=same, ntree=len(rows), pid1_exit=pexit, req=box.get('r'), req_t=box.get('t'), orphan=still)
cases = [
    ('exec 形式:直接运行 gunicorn(CMD ["gunicorn", ...])', [ '{G}', '-w', '1', '-b', '127.0.0.1:{port}', 'app:app']),
    ('shell 形式,单条命令:sh -c "gunicorn ..."', ['/bin/sh', '-c', '{G} -w 1 -b 127.0.0.1:{port} app:app']),
    ('shell 形式,多条命令:sh -c "gunicorn ...; echo done"', ['/bin/sh', '-c', '{G} -w 1 -b 127.0.0.1:{port} app:app; echo done']),
    ('入口脚本最后一行是 gunicorn(没有 exec)', ['./entry_plain.sh']),
    ('入口脚本最后一行是 exec gunicorn', ['./entry_exec.sh']),
]
print('== 一:docker stop 先给容器里的 1 号进程发 SIGTERM。这里用「被发信号的进程」代替 1 号进程:3 秒的请求在进行,给它发 SIGTERM,看 gunicorn 有没有收到')
print(f'{"启动方式":<46}{"被发信号的进程就是 gunicorn?":<26}{"它的退出":<10}{"请求结果":<14}{"gunicorn 变孤儿继续运行?"}')
R['cases'] = []
for label, argv in cases:
    r = run_case(label, argv); R['cases'].append(r)
    print(f'{label:<46}{str(r["same_pid"]):<30}{str(r["pid1_exit"]) + " s":<10}{(str(r["req"]) + " " + str(r["req_t"]) + " s"):<14}{r["orphan"]}')
print()
print('== 二:同一个多条命令的 shell 形式再跑一次,确认「孤儿 gunicorn」可以复现')
r = run_case('sh -c 多条命令(再次)', ['/bin/sh', '-c', '{G} -w 1 -b 127.0.0.1:{port} app:app; echo done'])
R['again'] = r; print(f'  再跑一次 sh -c "...; echo done":sh 退出后 gunicorn 孤儿存在 = {r["orphan"]}')
print()
print('== 三:grace 期比请求短:docker stop 默认 10 秒后补 SIGKILL。这里用 2 秒代替(给进程组发 SIGTERM,2 秒后 SIGKILL),3 秒的请求')
port = free_port(); p = subprocess.Popen([G, '-w', '1', '-b', f'127.0.0.1:{port}', 'app:app'], cwd=d, env=env(d), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
t0 = time.time()
while time.time() - t0 < 10:
    with socket.socket() as s_:
        if s_.connect_ex(('127.0.0.1', port)) == 0: break
    time.sleep(0.05)
box = {}
def req2():
    t1 = time.perf_counter()
    try: rr = http(port, 'GET', '/slow', timeout=15); box['r'] = str(rr[0])
    except Exception as ex: box['r'] = type(ex).__name__
    box['t'] = round(time.perf_counter() - t1, 2)
th = threading.Thread(target=req2); th.start(); time.sleep(0.5); os.killpg(p.pid, signal.SIGTERM); time.sleep(1.5); os.killpg(p.pid, signal.SIGKILL); p.wait(); th.join()
print(f'  SIGTERM 之后 1.5 秒补 SIGKILL:请求 → {box["r"]},{box["t"]} s 后(这个请求本来要 3 秒才完成,被打断)'); R['kill'] = box
save('f189', R)
