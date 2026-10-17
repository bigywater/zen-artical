import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c87')
purge()
img('alpine:3.20', 'debian:12-slim')
d = ctx('c87img', {'Dockerfile': 'FROM debian:12-slim\nRUN apt-get update && apt-get install -y --no-install-recommends systemd procps && rm -rf /var/lib/apt/lists/*\nSTOPSIGNAL SIGRTMIN+3\nCMD ["/lib/systemd/systemd"]\n'})
t0 = time.time(); rc, o = build(d, 'bwlab-c87sd', '--provenance=false', '--sbom=false', timeout=1800); assert rc == 0, o[-300:]
print(f'说明:镜像 bwlab-c87sd 由 debian:12-slim 加 apt-get install systemd procps 构建(本次构建 {time.time() - t0:.0f} 秒,命中了之前的构建缓存;首次从网络安装花了约 10 分钟)')
N = 'bwlab-c87'
def trial(label, opts, wait=5):
    dk('rm', '-f', N)
    rc, o = dk('run', '-d', '-t', '--name', N, *LAB, *opts, 'bwlab-c87sd')
    time.sleep(wait)
    st = out('inspect', '--format', '{{.State.Status}} exit={{.State.ExitCode}}', N) if rc == 0 else f'(docker run 失败:{o.strip().splitlines()[-1][:100]})'
    lg = [re.sub(r'\x1b\[[0-9;]*m', '', l).strip() for l in dk('logs', N)[1].splitlines() if l.strip()]
    run = dk('exec', N, 'systemctl', 'is-system-running')[1].strip().splitlines()[-1] if st.startswith('running') else '-'
    print(f'  {label}:{st};systemctl is-system-running = {run};控制台最后几行:{" | ".join(lg[-2:])[:200] or "(无)"}')
    return st.startswith('running')
print('== 一:systemd 要在容器里当 PID 1,需要哪些条件(Docker Engine 29.8.2,cgroup v2;镜像 debian:12-slim + systemd,本机构建)')
trial('默认(什么选项都不加)', [])
trial('--tmpfs /run --tmpfs /tmp', ['--tmpfs', '/run', '--tmpfs', '/tmp'])
trial('--tmpfs /run --tmpfs /run/lock --tmpfs /tmp', ['--tmpfs', '/run', '--tmpfs', '/run/lock', '--tmpfs', '/tmp'])
trial('--cap-add SYS_ADMIN', ['--cap-add', 'SYS_ADMIN'])
trial('--cap-add SYS_ADMIN --security-opt seccomp=unconfined', ['--cap-add', 'SYS_ADMIN', '--security-opt', 'seccomp=unconfined'])
trial('--cap-add SYS_ADMIN + seccomp=unconfined + --tmpfs /run /run/lock /tmp', ['--cap-add', 'SYS_ADMIN', '--security-opt', 'seccomp=unconfined', '--tmpfs', '/run', '--tmpfs', '/run/lock', '--tmpfs', '/tmp'])
ok = trial('--privileged', ['--privileged'])
dk('rm', '-f', N)
print('== 二:能启动的那种配置(--privileged)里跑起来的是什么')
dk('run', '-d', '-t', '--name', N, *LAB, '--privileged', 'bwlab-c87sd'); time.sleep(6)
print('  PID 1 的名字:' + dk('exec', N, 'cat', '/proc/1/comm')[1].strip())
print('  systemctl is-system-running:' + dk('exec', N, 'systemctl', 'is-system-running')[1].strip())
print('  运行中的服务:' + dk('exec', N, 'sh', '-c', "systemctl list-units --type=service --state=running --no-legend | awk '{print $1}' | tr '\\n' ' '")[1].strip())
print('  进程(按名字统计 systemd / systemd-journald / agetty):' + dk('exec', N, 'sh', '-c', "for p in systemd systemd-journal agetty; do echo $p=$(ps -e -o comm= | grep -c \"^$p\"); done | tr '\\n' ' '")[1].strip())
print('  docker top 看到的进程数:' + str(len(dk('top', N)[1].splitlines()) - 1))
print('== 三:systemd 容器怎么停:SIGRTMIN+3 与 SIGTERM')
t0 = time.time(); dk('stop', '-t', '10', N); t_rt = time.time() - t0
print(f'  镜像里 STOPSIGNAL SIGRTMIN+3(c30):docker stop -t 10 用时 {t_rt:.1f} 秒,ExitCode={out("inspect", "--format", "{{.State.ExitCode}}", N)}')
dk('rm', '-f', N)
dk('run', '-d', '-t', '--name', N, *LAB, '--privileged', '--stop-signal', 'SIGTERM', 'bwlab-c87sd'); time.sleep(6)
t0 = time.time(); dk('stop', '-t', '10', N); t_tm = time.time() - t0
print(f'  --stop-signal SIGTERM:docker stop -t 10 用时 {t_tm:.1f} 秒,ExitCode={out("inspect", "--format", "{{.State.ExitCode}}", N)}(SIGTERM 没能让它关机,等满宽限期后被 SIGKILL)')
print('== 四:内存与启动时间')
dk('rm', '-f', N)
t0 = time.time(); dk('run', '-d', '-t', '--name', N, *LAB, '--privileged', 'bwlab-c87sd')
for _ in range(100):
    r = dk('exec', N, 'systemctl', 'is-system-running')[1].strip().splitlines()
    if r and r[-1] in ('running', 'degraded'): break
    time.sleep(0.2)
print(f'  从 docker run 到 systemctl is-system-running 返回 {r[-1]} 用了 {time.time() - t0:.1f} 秒')
time.sleep(3)
print(f'  docker stats 的 MemUsage:{out("stats", "--no-stream", "--format", "{{.MemUsage}} PIDs={{.PIDs}}", N)}')
dk('rm', '-f', N)
purge()
