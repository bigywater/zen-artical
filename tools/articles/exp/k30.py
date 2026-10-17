import sys, os, re, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k30')
cn, _ = up('main')
NS = ns('k30')
def pod(name, containers, extra=''):
    cs = ''.join(f'  - {{name: {n}, image: busybox:1.36, command: [sleep, "3600"]{", resources: " + r if r else ""}}}\n' for n, r in containers)
    return f'apiVersion: v1\nkind: Pod\nmetadata: {{name: {name}, namespace: {NS}}}\nspec:\n  terminationGracePeriodSeconds: 0\n{extra}  containers:\n{cs}'
CASES = [
    ('guar', 'requests = limits(cpu 和 memory,每个容器)', [('c', '{requests: {cpu: 200m, memory: 64Mi}, limits: {cpu: 200m, memory: 64Mi}}')]),
    ('guar-lim', '只写了 limits(requests 自动等于 limits)', [('c', '{limits: {cpu: 200m, memory: 64Mi}}')]),
    ('burst', 'requests 小于 limits', [('c', '{requests: {cpu: 100m, memory: 32Mi}, limits: {cpu: 200m, memory: 64Mi}}')]),
    ('burst-req', '只写了 requests', [('c', '{requests: {cpu: 100m}}')]),
    ('burst-mem', 'memory 满足、cpu 只有 requests', [('c', '{requests: {cpu: 100m, memory: 64Mi}, limits: {memory: 64Mi}}')]),
    ('burst-two', '两个容器,一个满足一个没写', [('a', '{requests: {cpu: 100m, memory: 64Mi}, limits: {cpu: 100m, memory: 64Mi}}'), ('b', '')]),
    ('best', '什么都没写', [('c', '')]),
]
for n, d, cs in CASES: k('apply', '-f', '-', input=pod(n, cs))
until(lambda: all((kj('get', 'pod', n, '-n', NS) or {}).get('status', {}).get('phase') == 'Running' for n, _, _ in CASES), 90)
print(f'集群 {cn};QoS 等级(status.qosClass)由 Pod 里所有容器的 requests / limits 决定,创建时一次算好;kubelet 据此放置 cgroup、设置 oom_score_adj、决定驱逐顺序')

print('== 一:七个 Pod,各自被分到哪个 QoS 等级')
for n, d, cs in CASES:
    p = kj('get', 'pod', n, '-n', NS)
    print(f'  {n:<10} {p["status"]["qosClass"]:<11} {d}')

print('== 二:cgroup 里的位置——Guaranteed 直接挂在 kubepods 下,Burstable 与 BestEffort 各有一层')
for n in ('guar', 'burst', 'best'):
    p = kj('get', 'pod', n, '-n', NS); node, path = pod_cgroup(p)
    print(f'  {n:<6} → ' + path.replace('/sys/fs/cgroup/', '').replace(p['metadata']['uid'].replace('-', '_'), '<uid>'))

print('== 三:同一个 QoS 在内核里的参数——cpu.weight、memory.max 与进程的 oom_score_adj')
def oom_adj(p, cname='c'):
    node, cg, cid = container_cgroup(p, cname)
    rc, o = nx(node, f'pid=$(cat {cg}/cgroup.procs | head -1); cat /proc/$pid/oom_score_adj'); return o.strip()
rows = []
cap = int(ko('get', 'node', 'kx-main-worker', '-o', 'jsonpath={.status.capacity.memory}').rstrip('Ki')) * 1024
print(f'  节点内存容量 {cap / 2**20:.0f} MiB(影响 Burstable 的 oom_score_adj 计算)')
for n in ('guar', 'burst', 'burst-req', 'best'):
    p = kj('get', 'pod', n, '-n', NS); node, cg, cid = container_cgroup(p, 'c')
    mem_req = {'guar': 64, 'burst': 32, 'burst-req': 0, 'best': 0}[n]
    expect = {'guar': '-997', 'best': '1000'}.get(n)
    if n.startswith('burst'):
        expect = str(min(max(1000 - int(1000 * mem_req * 2**20 / cap), 2), 999)) if mem_req else '999'
    print(f'  {n:<10} {p["status"]["qosClass"]:<11} cpu.weight={cgread(node, cg, "cpu.weight"):<4} cpu.max={cgread(node, cg, "cpu.max"):<14} memory.max={cgread(node, cg, "memory.max"):<11} oom_score_adj={oom_adj(p)}(按规则应为 {expect})')

print('== 四:QoS 等级不能被改——在线调整资源如果会改变 QoS,就被拒绝')
rc, o = k('patch', 'pod', 'guar', '-n', NS, '--subresource=resize', '--type=strategic', '-p', '{"spec":{"containers":[{"name":"c","resources":{"limits":{"cpu":"400m"}}}]}}')
print(f'  Guaranteed 的 guar 只把 cpu limit 改成 400m(requests 仍是 200m,会变成 Burstable):退出码 {rc};{re.sub(r"^.*Forbidden: ", "Forbidden: ", o.strip())[:200]}')
rc, o = k('patch', 'pod', 'guar', '-n', NS, '--subresource=resize', '--type=strategic', '-p', '{"spec":{"containers":[{"name":"c","resources":{"requests":{"cpu":"400m"},"limits":{"cpu":"400m"}}}]}}')
time.sleep(3); p = kj('get', 'pod', 'guar', '-n', NS)
print(f'  requests 与 limits 一起改成 400m(仍是 Guaranteed):退出码 {rc};{o.strip()};spec 里 cpu={p["spec"]["containers"][0]["resources"]["limits"]["cpu"]};qosClass={p["status"]["qosClass"]};容器 cpu.max={cgread(*container_cgroup(p, "c")[:2], "cpu.max")}')
rc, o = k('patch', 'pod', 'best', '-n', NS, '--subresource=resize', '--type=strategic', '-p', '{"spec":{"containers":[{"name":"c","resources":{"requests":{"cpu":"50m"}}}]}}')
print(f'  BestEffort 的 best 想加一个 requests(会变成 Burstable):退出码 {rc};{re.sub(r"^.*Forbidden: ", "Forbidden: ", o.strip())[:200]}')
rmns(NS)
