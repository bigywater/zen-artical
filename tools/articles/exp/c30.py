import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c30')
img('python:3.12-alpine')
purge()
APP = '''
import signal, sys, time, os
work = float(os.environ.get("WORK", "0"))
def h(n, f):
    print("收到信号", signal.Signals(n).name, flush=True)
    time.sleep(work)
    print("清理完成,退出", flush=True)
    sys.exit(0)
for s in (signal.SIGTERM, signal.SIGINT, signal.SIGQUIT, signal.SIGHUP, signal.SIGUSR1):
    signal.signal(s, h)
print("启动,PID", os.getpid(), flush=True)
while True: time.sleep(1)
'''
d = ctx('c30', {'app.py': APP, 'Dockerfile': 'FROM python:3.12-alpine\nCOPY app.py /app.py\nCMD ["python","-u","/app.py"]\n', })
rc, o = build(d, 'bwlab-c30', '--provenance=false', '--sbom=false'); assert rc == 0, o[-300:]
d2 = ctx('c30b', {'app.py': APP, 'Dockerfile': 'FROM python:3.12-alpine\nCOPY app.py /app.py\nSTOPSIGNAL SIGQUIT\nCMD ["python","-u","/app.py"]\n'})
rc, o = build(d2, 'bwlab-c30q', '--provenance=false', '--sbom=false'); assert rc == 0, o[-300:]
def run_stop(label, image, run_opts=(), stop_args=(), env=()):
    n = 'bwlab-c30-' + str(abs(hash(label)) % 10**6)
    dk('run', '-d', '--name', n, *LAB, *run_opts, *[x for e in env for x in ('-e', e)], image)
    time.sleep(1)
    t0 = time.time(); dk('stop', *stop_args, n); t = ms(t0)
    s = json.loads(out('inspect', '--format', '{{json .State}}', n))
    lg = dk('logs', n)[1].replace('\n', ' | ')
    print(f'  {label}:docker stop 用时 {t:.0f} ms;ExitCode={s["ExitCode"]};日志:{lg}')
    dk('rm', '-f', n)
    return t, s
print('== 一:默认 docker stop 发的是什么信号(Docker Engine 29.8.2,PID 1 是 python,装了信号处理程序)')
run_stop('默认', 'bwlab-c30')
print('== 二:换信号:--stop-signal 与 Dockerfile 里的 STOPSIGNAL')
run_stop('docker run --stop-signal SIGINT', 'bwlab-c30', run_opts=['--stop-signal', 'SIGINT'])
run_stop('Dockerfile STOPSIGNAL SIGQUIT', 'bwlab-c30q')
run_stop('Dockerfile STOPSIGNAL SIGQUIT,运行时覆盖为 SIGUSR1', 'bwlab-c30q', run_opts=['--stop-signal', 'SIGUSR1'])
print(f'  镜像里记录的 StopSignal:{out("image", "inspect", "--format", "{{.Config.StopSignal}}", "bwlab-c30q")}')
print('== 三:清理要花 3 秒,宽限期给 5 秒还是 1 秒')
run_stop('清理 3 秒,docker stop -t 5', 'bwlab-c30', env=['WORK=3'], stop_args=['-t', '5'])
run_stop('清理 3 秒,docker stop -t 1', 'bwlab-c30', env=['WORK=3'], stop_args=['-t', '1'])
print('== 四:宽限期的来源:守护进程默认值、--stop-timeout、docker stop -t')
n = 'bwlab-c30-def'
dk('run', '-d', '--name', n, *LAB, '-e', 'WORK=15', 'bwlab-c30'); time.sleep(1)
rcv, ov = dk('run', '--rm', '--privileged', '--pid=host', *LAB, 'python:3.12-alpine', 'nsenter', '-t', '1', '-m', '-u', '-n', '-i', 'sh', '-c', 'grep default-stop-timeout /run/config/docker/daemon.json')
print(f'  这个 Docker Desktop 的守护进程配置(虚拟机里的 /run/config/docker/daemon.json)里:{ov.strip()}')
print(f'  默认的 Config.StopTimeout = {out("inspect", "--format", "{{.Config.StopTimeout}}", n)}')
t0 = time.time(); dk('stop', n, timeout=60); t = ms(t0); s = json.loads(out('inspect', '--format', '{{json .State}}', n))
print(f'  清理需要 15 秒时,docker stop(不带 -t):用时 {t:.0f} ms;ExitCode={s["ExitCode"]}')
dk('rm', '-f', n)
n = 'bwlab-c30-st'
dk('run', '-d', '--name', n, *LAB, '--stop-timeout', '2', '-e', 'WORK=15', 'bwlab-c30'); time.sleep(1)
print(f'  --stop-timeout 2 的 Config.StopTimeout = {out("inspect", "--format", "{{.Config.StopTimeout}}", n)}')
t0 = time.time(); dk('stop', n, timeout=60); t = ms(t0)
print(f'  docker stop(不带 -t):用时 {t:.0f} ms;ExitCode={json.loads(out("inspect", "--format", "{{json .State}}", n))["ExitCode"]}')
dk('rm', '-f', n)
n = 'bwlab-c30-st2'
dk('run', '-d', '--name', n, *LAB, '--stop-timeout', '2', '-e', 'WORK=15', 'bwlab-c30'); time.sleep(1)
t0 = time.time(); dk('stop', '-t', '4', n, timeout=60); t = ms(t0)
print(f'  --stop-timeout 2 再加 docker stop -t 4:用时 {t:.0f} ms(命令行参数优先)')
dk('rm', '-f', n)
purge()
