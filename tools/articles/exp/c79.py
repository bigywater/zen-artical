import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c79')
img('alpine:3.20', 'docker:dind')
purge()
N = 'bwlab-dind79'
def inner(cmd, timeout=120):
    r = subprocess.run(['docker', 'exec', N, 'sh', '-c', cmd], capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr).strip()
def wait_ready():
    for _ in range(80):
        if inner('docker info >/dev/null 2>&1')[0] == 0: return True
        time.sleep(0.5)
    return False
def start_daemon(flags):
    inner(f'(dockerd --storage-driver=vfs {flags} > /tmp/dockerd.log 2>&1 &)')
    return wait_ready()
def stop_daemon(sig='TERM'):
    t0 = time.time()
    inner(f'kill -{sig} $(pidof dockerd)')
    for _ in range(400):
        if not inner("ps -o stat=,comm= | awk '$2==\"dockerd\" && $1 !~ /^Z/' | grep -q .")[0] == 0: break
        time.sleep(0.25)
    dt = time.time() - t0
    inner('rm -f /var/run/docker.pid')
    return dt
rc, o = dk('run', '-d', '--name', N, *LAB, '--privileged', '--entrypoint', 'sh', 'docker:dind', '-c', 'sleep 3600'); time.sleep(1)
print('说明:为了不影响真正的 Docker Desktop 守护进程,这里在一个特权的 docker:dind 容器里单独起一个嵌套的 dockerd(存储驱动 vfs),反复停止、重启它。')
print(f'  嵌套 dockerd 版本:{inner("dockerd --version")[1]}')
start_daemon('')
p = subprocess.run(f'docker save alpine:3.20 | docker exec -i {N} docker load', shell=True, capture_output=True, text=True); 
print(f'  给嵌套的 dockerd 载入 alpine:3.20:{(p.stdout + p.stderr).strip().splitlines()[-1][:80]}')
stop_daemon()
def scenario(title, flags, kill_sig):
    print(f'== {title}')
    ok = start_daemon(flags)
    live = inner('docker info --format "{{.LiveRestoreEnabled}}"')[1]
    inner('docker rm -f tc >/dev/null 2>&1')
    rc_, o_ = inner('docker run -d --name tc alpine:3.20 sleep 600')
    if rc_: print('  docker run 失败:' + o_[-150:])
    st0 = inner('docker inspect --format "{{.State.Pid}} {{.State.StartedAt}}" tc')[1].split()
    print(f'  dockerd 启动参数:{flags or "(无)"};docker info 的 LiveRestoreEnabled = {live};容器 tc 启动,容器主进程在嵌套环境里的 PID = {st0[0]}')
    dt = stop_daemon(kill_sig)
    alive = inner(f'[ -d /proc/{st0[0]} ] && echo 还活着 || echo 已不在')[1]
    print(f'  给 dockerd 发 SIG{kill_sig} 并等它退出,用时 {dt:.1f} 秒;容器的主进程 {st0[0]}:{alive}')
    ok = start_daemon(flags)
    if not ok: print('  重新启动 dockerd 后没有就绪;日志尾部:' + inner('tail -3 /tmp/dockerd.log')[1][-300:].replace(chr(10), ' | '))
    st1 = inner('docker inspect --format "{{.State.Status}} {{.State.Pid}} {{.State.StartedAt}} exit={{.State.ExitCode}}" tc')[1].split()
    if len(st1) >= 4: print(f'  重新启动 dockerd 后:容器 Status={st1[0]} Pid={st1[1]} ExitCode={st1[3].split("=")[1]};StartedAt 与重启前{"相同" if st1[2] == st0[1] else "不同"}')
    else: print('  重新启动 dockerd 后 docker inspect 失败:' + ' '.join(st1)[:200])
    print(f'  docker ps 里的容器:{inner("docker ps --format \'{{.Names}} {{.Status}}\'")[1] or "(没有运行的容器)"}')
    inner('docker rm -f tc >/dev/null 2>&1')
    stop_daemon()
scenario('一:默认(没有 live-restore)停止 dockerd', '', 'TERM')
scenario('二:--live-restore,停止 dockerd', '--live-restore', 'TERM')
scenario('三:--live-restore,dockerd 被 kill -9(模拟崩溃)', '--live-restore', 'KILL')
print('== 四:live-restore 的限制:守护进程停着的时候')
start_daemon('--live-restore')
inner('docker run -d --name tc alpine:3.20 sh -c "echo tick; sleep 600"'); time.sleep(1)
stop_daemon('TERM')
alive = inner('pgrep -f "sleep 600" | head -1')[1]
rc, o = inner('docker ps')
print(f'  dockerd 停着时:容器的 sleep 进程仍在运行(pgrep 得到 PID {alive});docker ps → 退出码 {rc};{o.splitlines()[0][:90] if o else ""}')
start_daemon('--live-restore')
print('  重启后 docker logs tc:' + inner('docker logs tc')[1].replace('\n', ' | '))
inner('docker rm -f tc >/dev/null 2>&1'); stop_daemon()
print('  Docker Desktop 本身的 daemon.json 里有 live-restore 吗?' + dk('run', '--rm', '--privileged', '--pid=host', *LAB, 'alpine:3.20', 'nsenter', '-t', '1', '-m', '-u', '-n', '-i', 'sh', '-c', 'grep -c live-restore /run/config/docker/daemon.json || true')[1].strip() + ' 处(0 表示没有配置,即默认关闭)')
dk('rm', '-f', N)
purge()
