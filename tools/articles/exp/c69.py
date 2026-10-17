import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c69')
img('alpine:3.20')
purge()
t1 = int(time.time()) - 1
dk('volume', 'create', '--label', 'bwlab=1', 'bwlab-c69v')
dk('network', 'create', '--label', 'bwlab=1', 'bwlab-c69n')
dk('tag', 'alpine:3.20', 'bwlab-c69-tagged:1')
dk('run', '--rm', '--name', 'bwlab-c69c', *LAB, '--network', 'bwlab-c69n', '-v', 'bwlab-c69v:/data', 'alpine:3.20', 'sh', '-c', 'echo hi > /data/f; sleep 1')
dk('rmi', 'bwlab-c69-tagged:1')
dk('volume', 'rm', 'bwlab-c69v'); dk('network', 'rm', 'bwlab-c69n')
time.sleep(1); t2 = int(time.time()) + 1
rc, o = dk('events', '--since', str(t1), '--until', str(t2), '--format', '{{json .}}', timeout=60)
evs = [json.loads(l) for l in o.splitlines() if l.startswith('{')]
mine = [e for e in evs if 'bwlab-c69' in json.dumps(e) or e.get('Type') == 'image']
print('== 一:一轮操作产生的事件(Docker Engine 29.8.2,docker events --since/--until --format json)')
print(f'  操作:创建卷和网络、给镜像打 tag、run --rm 一个挂卷并接网络的容器、删 tag、删卷和网络')
print(f'  这段时间 docker events 共 {len(evs)} 条,其中和这次实验相关的 {len(mine)} 条')
for e in mine:
    a = e['Actor']['Attributes']
    name = a.get('name') or e['Actor']['ID']
    print(f'    {e["Type"]:10s} {e["Action"]:12s} {name[:40]}')
print('== 二:一条事件的字段')
e = [x for x in mine if x['Type'] == 'container' and x['Action'] == 'start'][0]
print('  顶层字段:' + str(sorted(e.keys())))
print('  Actor.Attributes 里有:' + str(sorted(e['Actor']['Attributes'].keys())))
print(f'  time={e["time"]}(秒)timeNano={e["timeNano"]}(纳秒)')
print('== 三:过滤')
t3 = int(time.time())
dk('network', 'create', '--label', 'bwlab=1', 'bwlab-c69n2')
dk('run', '--rm', '--name', 'bwlab-c69c2', *LAB, 'alpine:3.20', 'true')
dk('network', 'rm', 'bwlab-c69n2'); time.sleep(1)
t4 = int(time.time()) + 1
for label, flt in (('type=network', ['--filter', 'type=network']), ('type=container --filter event=die', ['--filter', 'type=container', '--filter', 'event=die']), ('container=bwlab-c69c2 --filter event=start --filter event=die', ['--filter', 'container=bwlab-c69c2', '--filter', 'event=start', '--filter', 'event=die'])):
    rc, o = dk('events', '--since', str(t3), '--until', str(t4), *flt, '--format', '{{.Type}}/{{.Action}}', timeout=60)
    print(f'  --filter {label}:' + ' ; '.join(l for l in o.splitlines() if l.strip()))
print('== 四:docker events 能看多久以前的')
rc, o = dk('events', '--since', '1h', '--until', str(t4), '--format', '{{.Time}}', timeout=60)
ts = [int(x) for x in o.split() if x.isdigit()]
print(f'  --since 1h 能取到 {len(ts)} 条;最早的是 {int(time.time()) - min(ts)} 秒前' if ts else '  --since 1h 没有事件')
rc, o = dk('events', '--since', '24h', '--until', str(t4), '--format', '{{.Time}}', timeout=60)
ts2 = [int(x) for x in o.split() if x.isdigit()]
print(f'  --since 24h 能取到 {len(ts2)} 条;最早的是 {(int(time.time()) - min(ts2)) // 60} 分钟前' if ts2 else '  --since 24h 没有事件')
purge()
