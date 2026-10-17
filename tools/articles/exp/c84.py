import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c84')
img('python:3.12-alpine')
purge()
APP = '''
import signal, sys, time, os
def h(n, f):
    print("收到信号", signal.Signals(n).name, flush=True)
    if n == signal.SIGHUP: return
    time.sleep(0.5); print("清理完成,退出", flush=True); sys.exit(0)
for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP): signal.signal(s, h)
print("app 启动,PID", os.getpid(), flush=True)
while True: time.sleep(0.2)
'''
SCRIPTS = {
 'A 不用 exec(sh 启动 python)': '#!/bin/sh\necho "entrypoint 启动,PID $$"\npython -u /app.py\necho "entrypoint 结束"\n',
 'B exec python': '#!/bin/sh\necho "entrypoint 启动,PID $$"\nexec python -u /app.py\n',
 'C1 trap 转发 TERM,只 wait 一次': '#!/bin/sh\necho "entrypoint 启动,PID $$"\npython -u /app.py &\nchild=$!\ntrap \'kill -TERM $child\' TERM INT\nwait $child\nrc=$?\necho "entrypoint 结束,第一次 wait 返回 $rc"\nexit $rc\n',
 'C2 trap 转发 TERM,被信号打断后再 wait 一次': '#!/bin/sh\necho "entrypoint 启动,PID $$"\npython -u /app.py &\nchild=$!\ntrap \'kill -TERM $child\' TERM INT\nwait $child\ntrap - TERM INT\nwait $child\nrc=$?\necho "entrypoint 结束,python 退出码 $rc"\nexit $rc\n',
}
files = {'app.py': APP, 'Dockerfile': 'FROM python:3.12-alpine\nCOPY app.py /app.py\nCOPY a.sh b.sh c.sh c2.sh /\nRUN chmod +x /a.sh /b.sh /c.sh /c2.sh\n'}
for k, f in zip(SCRIPTS, ('a.sh', 'b.sh', 'c.sh', 'c2.sh')): files[f] = SCRIPTS[k]
d = ctx('c84', files); rc, o = build(d, 'bwlab-c84', '--provenance=false', '--sbom=false'); assert rc == 0, o[-300:]
def trial(label, script, opts=(), stop=('-t', '5'), sig=None):
    n = 'bwlab-c84-' + str(abs(hash(label + str(opts))) % 10**6)
    dk('run', '-d', '--name', n, *LAB, *opts, '--entrypoint', script, 'bwlab-c84'); time.sleep(1.5)
    t0 = time.time()
    if sig: dk('kill', '-s', sig, n); time.sleep(1)
    else: dk('stop', *stop, n)
    t = time.time() - t0
    s = json.loads(out('inspect', '--format', '{{json .State}}', n))
    lg = ' | '.join(l.strip() for l in dk('logs', n)[1].splitlines())
    print(f'  {label}:' + (f'docker kill -s {sig}' if sig else f'docker stop {" ".join(stop)}') + f' 用时 {t:.1f} 秒;Status={s["Status"]} ExitCode={s["ExitCode"]};日志:{lg}')
    dk('rm', '-f', n)
print('== 一:入口脚本怎么启动应用,决定应用收不收得到 docker stop 的 SIGTERM(docker stop -t 5;Docker Engine 29.8.2)')
for (label, _), sc in zip(SCRIPTS.items(), ('/a.sh', '/b.sh', '/c.sh', '/c2.sh')): trial(label, sc)
print('== 二:加 --init(tini)会改变结果吗')
trial('A + --init(sh 脚本不 exec)', '/a.sh', opts=['--init'])
trial('B + --init(exec python)', '/b.sh', opts=['--init'])
print('== 三:不只是 stop:docker kill -s HUP(热加载信号)')
trial('A 不用 exec,发 HUP', '/a.sh', sig='HUP')
trial('B exec python,发 HUP', '/b.sh', sig='HUP')
trial('C2 trap 只转发 TERM/INT,发 HUP', '/c2.sh', sig='HUP')
purge()
