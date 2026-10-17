import sys, os, re, time, json, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k41')
cn, dt_up = up('sched', cfg=config(workers=4))
load('busybox:1.36'); wait_nodes_ready()
NODES = ['kx-sched-worker', 'kx-sched-worker2', 'kx-sched-worker3', 'kx-sched-worker4']
NS = ns('k41')
def pod(name, spec_extra='', res=''):
    return f'apiVersion: v1\nkind: Pod\nmetadata: {{name: {name}, namespace: {NS}}}\nspec:\n  terminationGracePeriodSeconds: 0\n{spec_extra}  containers:\n  - name: c\n    image: busybox:1.36\n    command: [sleep, "3600"]\n{res}'
def where(n): p = kj('get', 'pod', n, '-n', NS); return (p['spec'].get('nodeName') or '(未调度)').replace('kx-sched-', ''), p
def reason(p):
    c = [x for x in p['status'].get('conditions', []) if x['type'] == 'PodScheduled']
    return (c[0].get('message') or '')[:170] if c and c[0]['status'] != 'True' else ''
print(f'集群 {cn}(1 控制面 + 4 个 worker)')
print('== 一:节点上本来就有的标签')
n = kj('get', 'node', NODES[0]); print(f'  worker 的标签({len(n["metadata"]["labels"])} 个):')
for k_, v in sorted(n['metadata']['labels'].items()): print(f'    {k_}={v}')
cpn = kj('get', 'node', 'kx-sched-control-plane'); print(f'  控制面比 worker 多的标签:{sorted(set(cpn["metadata"]["labels"]) - set(n["metadata"]["labels"]))}')

print('== 二:nodeSelector——多个键之间是 AND;没有匹配的节点就 Pending,打上标签立刻调度')
for nd, d in ((NODES[1], 'ssd'), (NODES[2], 'ssd'), (NODES[3], 'hdd')): k('label', 'node', nd, f'disk={d}', '--overwrite')
k('label', 'node', NODES[2], 'gpu=yes', '--overwrite')
for nm, sel in (('on-ssd', '{disk: ssd}'), ('on-ssd-gpu', '{disk: ssd, gpu: "yes"}'), ('on-nvme', '{disk: nvme}')): k('apply', '-f', '-', input=pod(nm, f'  nodeSelector: {sel}\n'))
time.sleep(5)
for nm, sel in (('on-ssd', 'disk=ssd(worker2、worker3 有)'), ('on-ssd-gpu', 'disk=ssd 且 gpu=yes(只有 worker3 同时有)'), ('on-nvme', 'disk=nvme(没有任何节点有)')):
    w, p = where(nm); print(f'  {nm:<11} nodeSelector {sel}:{w}' + (f';{reason(p)}' if reason(p) else ''))
t0 = time.time(); k('label', 'node', NODES[0], 'disk=nvme', '--overwrite')
v, dt = until(lambda: where('on-nvme')[0] != '(未调度)', 20, 0.1)
print(f'  给 worker 打上 disk=nvme 之后:on-nvme 在 {dt:.1f} 秒内被调度到 {where("on-nvme")[0]}(调度器监听节点变化,不用重建 Pod)')
k('label', 'node', NODES[0], 'disk-')
k('label', 'node', NODES[2], 'disk=hdd', '--overwrite'); time.sleep(2)
w, p = where('on-ssd'); print(f'  把 worker3 的 disk 改成 hdd 之后:已经调度的 on-ssd 在 {w}(标签变了也不会被赶走)')
k('delete', 'pod', '--all', '-n', NS, '--wait=true', timeout=60)

print('== 三:nodeName 绕过调度器——kubelet 只做最后的准入检查')
k('apply', '-f', '-', input=pod('fixed', f'  nodeName: {NODES[0]}\n')); time.sleep(4); w, p = where('fixed'); print(f'  nodeName 直接指定:{w};phase={p["status"]["phase"]};事件里有 Scheduled 吗:{any(e["reason"] == "Scheduled" for e in kj("get", "events", "-n", NS, "--field-selector", "involvedObject.name=fixed")["items"])}(没有经过调度器)')
k('cordon', NODES[0]); k('apply', '-f', '-', input=pod('on-cordoned', f'  nodeName: {NODES[0]}\n')); k('apply', '-f', '-', input=pod('sched-cordoned', f'  nodeSelector: {{kubernetes.io/hostname: {NODES[0]}}}\n')); time.sleep(5)
for nm, d in (('on-cordoned', 'nodeName 指向已经 cordon 的节点'), ('sched-cordoned', 'nodeSelector 指向已经 cordon 的节点')):
    w, p = where(nm); print(f'  {d}:{w};phase={p["status"]["phase"]}' + (f';{reason(p)}' if reason(p) else ''))
k('uncordon', NODES[0])
k('apply', '-f', '-', input=pod('too-big', f'  nodeName: {NODES[0]}\n', '    resources: {requests: {cpu: "100"}}\n')); time.sleep(5)
p = kj('get', 'pod', 'too-big', '-n', NS)
print(f'  nodeName 指向的节点放不下(请求 100 核):phase={p["status"]["phase"]};reason={p["status"].get("reason")};message={p["status"].get("message", "")[:200]}')
k('delete', 'pod', '--all', '-n', NS, '--wait=true', timeout=60)

print('== 四:看 Pending 的原因——scheduler 把每类淘汰的节点数写进 PodScheduled 条件')
k('cordon', NODES[3])
cases = (('need-label', '  nodeSelector: {no-such: label}\n', ''), ('need-cpu', '', '    resources: {requests: {cpu: "100"}}\n'), ('need-mem', '', '    resources: {requests: {memory: 1000Gi}}\n'), ('need-eph', '', '    resources: {requests: {ephemeral-storage: 1000Gi}}\n'), ('on-cordon', f'  nodeSelector: {{kubernetes.io/hostname: {NODES[3]}}}\n', ''), ('need-cp', '  nodeSelector: {node-role.kubernetes.io/control-plane: ""}\n', ''))
for nm, se, rs in cases: k('apply', '-f', '-', input=pod(nm, se, rs))
time.sleep(6)
for nm, se, rs in cases:
    w, p = where(nm); print(f'  {nm:<10} {(se + rs).strip().replace(chr(10), " ")[:60]:<62} → {reason(p)[:150]}')
k('uncordon', NODES[3])
for nd in NODES: k('label', 'node', nd, 'disk-', 'gpu-')
rmns(NS)
