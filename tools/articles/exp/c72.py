import sys, os, re, time, subprocess, json, shutil; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c72')
img('alpine:3.20')
purge()
def vm(cmd):
    rc, o = dk('run', '--rm', '--privileged', '--pid=host', *LAB, 'alpine:3.20', 'nsenter', '-t', '1', '-m', '-u', '-n', '-i', 'sh', '-c', cmd, raw=True)
    return o.strip()
n = 'bwlab-c72a'
dk('run', '-d', '--name', n, *LAB, 'alpine:3.20', 'sh', '-c', 'sleep 300 & sleep 301 & wait'); time.sleep(1)
print('== 一:docker top 与容器里的 ps 看到的 PID(Docker Engine 29.8.2)')
print('  docker top(默认列):')
for l in dk('top', n)[1].splitlines(): print('    ' + ' '.join(l.split())[:100])
print('  docker exec ps(容器里的视角):')
for l in dk('exec', n, 'ps', '-o', 'pid,ppid,comm,args')[1].splitlines(): print('    ' + ' '.join(l.split())[:100])
hp = int(out('inspect', '--format', '{{.State.Pid}}', n))
print(f'  容器主进程在虚拟机里的 PID = {hp};/proc/{hp}/status 的 NSpid = {vm(f"grep NSpid /proc/{hp}/status")}')
print('== 二:docker top 把参数交给 ps')
for label, a in (('-o pid,ppid,user,comm', ['-o', 'pid,ppid,user,comm']), ('aux', ['aux']), ('-eo pid,nlwp,rss,etime,args', ['-eo', 'pid,nlwp,rss,etime,args'])):
    rc, o = dk('top', n, *a)
    print(f'  docker top {label}:退出码 {rc};' + ' | '.join(' '.join(l.split())[:70] for l in o.splitlines()[:3]))
print('== 三:用户名是谁解析的')
m = 'bwlab-c72b'
dk('run', '-d', '--name', m, *LAB, '--user', '1', 'alpine:3.20', 'sleep', '300'); time.sleep(1)
print('  容器里 uid 1 的名字(容器的 /etc/passwd):' + dk('exec', m, 'sh', '-c', 'grep ":x:1:" /etc/passwd | cut -d: -f1; id -un 2>&1')[1].strip().replace('\n', ' / '))
print('  虚拟机里 uid 1 的名字:' + vm('grep ":x:1:" /etc/passwd | cut -d: -f1'))
print('  docker top 显示这个进程的 UID 列:' + ' | '.join(' '.join(l.split())[:40] for l in dk('top', m)[1].splitlines()))
print('  docker top -o user,uid:' + ' | '.join(' '.join(l.split()) for l in dk('top', m, '-o', 'user,uid,comm')[1].splitlines()))
dk('rm', '-f', m)
print('== 四:容器里没有 ps 也能用 docker top')
d = ctx('c72', {'main.go': 'package main\nimport "time"\nfunc main() { time.Sleep(300 * time.Second) }\n', 'go.mod': 'module lab\n\ngo 1.27\n', 'Dockerfile': 'FROM scratch\nCOPY app /app\nENTRYPOINT ["/app"]\n'})
env = dict(os.environ, GOTOOLCHAIN='local', GOPROXY='off', CGO_ENABLED='0', GOOS='linux', GOARCH='arm64')
subprocess.run(['/opt/homebrew/bin/go', 'build', '-o', 'app', '.'], cwd=d, env=env, check=True, capture_output=True)
rc, o = build(d, 'bwlab-c72', '--provenance=false', '--sbom=false'); assert rc == 0, o[-300:]
s = 'bwlab-c72s'
dk('run', '-d', '--name', s, *LAB, 'bwlab-c72'); time.sleep(1)
rc, o = dk('exec', s, 'ps'); print(f'  scratch 镜像里 docker exec ps:退出码 {rc};{o.strip().splitlines()[-1][:110]}')
print('  同一个容器 docker top:' + ' | '.join(' '.join(l.split())[:60] for l in dk('top', s)[1].splitlines()))
purge()
