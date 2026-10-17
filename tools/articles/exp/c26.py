import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c26')
img('alpine:3.20')
purge()
def st(c): return json.loads(out('inspect', '--format', '{{json .State}}', c))
def line(c):
    s = st(c)
    return f'Status={s["Status"]} Running={s["Running"]} Paused={s["Paused"]} Pid={"0" if not s["Pid"] else ">0"} ExitCode={s["ExitCode"]} StartedAt={"(零值)" if s["StartedAt"].startswith("0001") else "有"} FinishedAt={"(零值)" if s["FinishedAt"].startswith("0001") else "有"}'
def events(since, until, name):
    rc, o = dk('events', '--since', str(since), '--until', str(until), '--filter', f'container={name}', '--format', '{{.Action}}|{{index .Actor.Attributes "signal"}}', timeout=60)
    return [(l.split('|')[0] + (f'(信号 {l.split(chr(124))[1]})' if len(l.split('|')) > 1 and l.split('|')[1].strip() else '')).replace('container ', '').strip() for l in o.strip().splitlines() if l.strip()]
print('== 一:docker create 之后、docker start 之后,容器的状态(Docker Engine 29.8.2)')
cid = out('create', '--name', 'bwlab-c26a', *LAB, 'alpine:3.20', 'sh', '-c', 'echo hi > /f; sleep 600')
print(f'  docker create 之后:{line(cid)}')
print(f'  docker ps(不带 -a)里有它吗?{"bwlab-c26a" in out("ps", "--format", "{{.Names}}")};docker ps -a 的 STATUS 列:{out("ps", "-a", "--filter", "name=bwlab-c26a", "--format", "{{.Status}}")}')
print(f'  网络里有 IP 吗?{bool(json.loads(out("inspect", "--format", "{{json .NetworkSettings.Networks}}", cid)).get("bridge", {}).get("IPAddress"))}(False 说明 create 时还没连网)')
dk('start', cid)
print(f'  docker start 之后:{line(cid)}')
print(f'  docker ps -a 的 STATUS 列:{out("ps", "-a", "--filter", "name=bwlab-c26a", "--format", "{{.Status}}")};有 IP 了吗?{bool(json.loads(out("inspect", "--format", "{{json .NetworkSettings.Networks}}", cid)).get("bridge", {}).get("IPAddress"))}')
print('== 二:暂停、停止、再启动')
dk('pause', cid); print(f'  docker pause 之后:{line(cid)}')
dk('unpause', cid); print(f'  docker unpause 之后:Status={st(cid)["Status"]}')
t0 = time.time(); dk('stop', '-t', '1', cid); print(f'  docker stop -t 1 之后:{line(cid)}(耗时 {ms(t0):.0f} ms,sh 是 PID 1 不处理 SIGTERM,所以等满了 1 秒后被 SIGKILL)')
rc, o = dk('exec', cid, 'true'); print(f'  对已停止的容器 docker exec → 退出码 {rc};{o.strip()[:90]}')
dk('start', cid)
print(f'  再 docker start:{line(cid)};之前写的 /f 还在吗?{out("exec", cid, "cat", "/f")};RestartCount={st(cid)["Status"] and out("inspect", "--format", "{{.RestartCount}}", cid)}(手动 start 不计入)')
print('== 三:docker rm')
rc, o = dk('rm', cid); print(f'  对运行中的容器 docker rm → 退出码 {rc};{o.strip()[:100]}')
rc, o = dk('rm', '-f', cid); print(f'  docker rm -f → 退出码 {rc}')
print('== 四:docker run --rm 一次完整生命周期里发生的事件(docker events)')
t1 = int(time.time()) - 1
dk('run', '--rm', '--name', 'bwlab-c26b', *LAB, 'alpine:3.20', 'true'); time.sleep(1); t2 = int(time.time()) + 1
print('  ' + ' → '.join(events(t1, t2, 'bwlab-c26b')))
print('  对比分步做:docker create / start / stop / rm 的事件')
t1 = int(time.time()) - 1
dk('create', '--name', 'bwlab-c26c', *LAB, 'alpine:3.20', 'sleep', '600'); dk('start', 'bwlab-c26c'); dk('stop', '-t', '1', 'bwlab-c26c'); dk('rm', 'bwlab-c26c'); time.sleep(1); t2 = int(time.time()) + 1
print('  ' + ' → '.join(events(t1, t2, 'bwlab-c26c')))
print('== 五:各步骤各花多久(5 次中位数)')
T = {'create': [], 'start': [], 'run --rm true(整套)': [], 'rm': []}
for i in range(5):
    t0 = time.time(); c = out('create', *LAB, 'alpine:3.20', 'true'); T['create'].append(ms(t0))
    t0 = time.time(); dk('start', '-a', c); T['start'].append(ms(t0))
    t0 = time.time(); dk('rm', c); T['rm'].append(ms(t0))
    t0 = time.time(); dk('run', '--rm', *LAB, 'alpine:3.20', 'true'); T['run --rm true(整套)'].append(ms(t0))
for k, v in T.items(): print(f'  {k}:{[round(x) for x in v]} ms,中位数 {med(v):.0f} ms')
purge()
