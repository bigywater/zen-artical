import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k64')
cn, _ = up('main'); wait_nodes_ready()
load('busybox:1.36')
NS = ns('k64')
rc, o = k('get', 'cm', 'coredns', '-n', 'kube-system', '-o', 'jsonpath={.data.Corefile}'); ORIG = o
def rel_counts():
    return {p['metadata']['name']: k('logs', '-n', 'kube-system', p['metadata']['name'], raw=True)[1].count('Reloading complete') for p in kj('get', 'pods', '-n', 'kube-system', '-l', 'k8s-app=kube-dns')['items']}
BASE = rel_counts()
assert '\n    log' not in ORIG and 'log\n' not in ORIG.split('errors')[1][:10] or True
new = ORIG.replace('errors\n', 'errors\n    log\n', 1) if '\n    log\n' not in ORIG else ORIG
cm = kj('get', 'cm', 'coredns', '-n', 'kube-system'); cm['data']['Corefile'] = new
for f in ('resourceVersion', 'uid', 'creationTimestamp'): cm['metadata'].pop(f, None)
k('apply', '-f', '-', input=json.dumps(cm))
def pod(name, dns=''):
    return f'apiVersion: v1\nkind: Pod\nmetadata: {{name: {name}, namespace: {NS}}}\nspec:\n  terminationGracePeriodSeconds: 0\n{dns}  containers: [{{name: c, image: busybox:1.36, command: [sleep, "3600"]}}]\n'
k('apply', '-f', '-', input=pod('cli') + '---\n' + pod('cli1', '  dnsConfig:\n    options: [{name: ndots, value: "1"}]\n') + '---\napiVersion: v1\nkind: Service\nmetadata: {name: s1, namespace: ' + NS + '}\nspec: {ports: [{port: 80}]}\n')
until(lambda: all(kj('get', 'pod', n, '-n', NS)['status'].get('phase') == 'Running' for n in ('cli', 'cli1')), 60, 0.3)
ips = {n: kj('get', 'pod', n, '-n', NS)['status']['podIP'] for n in ('cli', 'cli1')}
print(f'集群 {cn};在 CoreDNS 的 Corefile 里临时加上 log 插件,直接看每条查询(client、类型、名字、结果)')
print('  Pod 里的 /etc/resolv.conf:' + k('exec', 'cli', '-n', NS, '--', 'cat', '/etc/resolv.conf')[1].replace('\n', ' | '))
print('  等 CoreDNS 重新加载 Corefile(reload 插件,最长约 30 秒)……')
def logs(since):
    rc, o = k('logs', '-n', 'kube-system', '-l', 'k8s-app=kube-dns', '--since-time', since, '--tail=-1', '--timestamps', raw=True); return o
def reloaded():
    cur = rel_counts(); return len(cur) >= 2 and all(cur.get(p_, 0) > BASE.get(p_, 0) for p_ in BASE)
t_apply = time.time(); v, dt = until(reloaded, 150, 3); time.sleep(3); print(f'  {dt:.0f} 秒后两个 CoreDNS 副本都重新加载完 Corefile(日志里出现 Reloading complete)')
LINE = re.compile(r'\[INFO\] ([\d.]+):\d+ - \d+ "(\w+) IN (\S+) (\w+) \d+ \w+ \d+" (\w+)')
def queries(since, client):
    out = []
    for l in logs(since).splitlines():
        m = LINE.search(l)
        if m and m.group(1) == client: out.append((l.split()[0], m.group(2), m.group(3).rstrip('.'), m.group(5)))
    return [x[1:] for x in sorted(out)]
def run(pod_, cmd, label):
    time.sleep(1.2); since = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f') + 'Z'
    rc, o = k('exec', pod_, '-n', NS, '--', 'sh', '-c', cmd); time.sleep(3)
    q = queries(since, ips[pod_]); seq = []
    for t, n, r in q:
        if not seq or seq[-1][0] != n: seq.append([n, r, 0])
        seq[-1][2] += 1
    print(f'  {label}:共 {len(q)} 条 DNS 请求(A 与 AAAA 各算一条),按时间顺序的名字:'); [print(f'    {n:46} {r:9} ×{c}') for n, r, c in seq]
    return q, o

print('== 一:ndots:5 时查询一个外部域名 example.com')
q, o = run('cli', 'wget -q -T 3 -O /dev/null http://example.com 2>&1; echo done', 'wget http://example.com(ndots:5)')
names = []
for t, n, r in q:
    if n not in names: names.append(n)
print(f'  不同的名字依次是:{names};NXDOMAIN 的有 {sum(1 for t, n, r in q if r == "NXDOMAIN")} 条,最终成功的 {sum(1 for t, n, r in q if r == "NOERROR")} 条')

print('== 二:名字末尾加点——绝对域名,不走 search')
q, o = run('cli', 'wget -q -T 3 -O /dev/null http://example.com. 2>&1; echo done', 'wget http://example.com.')
print(f'  对比:{len(q)} 条(带点) vs 上面的 {len(queries("1970-01-01T00:00:00Z", "0")) if False else ""}'.rstrip(' vs 上面的 ') )

print('== 三:调低 ndots——包含点数 ≥ ndots 的名字先按绝对域名查')
q, o = run('cli1', 'wget -q -T 3 -O /dev/null http://example.com 2>&1; echo done', 'Pod cli1(dnsConfig ndots:1)访问 example.com')
q, o = run('cli1', f'wget -q -T 3 -O /dev/null http://s1.{NS} 2>&1; echo done', f'Pod cli1(ndots:1)访问集群内的 s1.{NS}(只有 1 个点,≥ 1)')

print('== 四:访问集群内 Service 时,写法不同,查询次数不同')
for nm in ('s1', f's1.{NS}', f's1.{NS}.svc', f's1.{NS}.svc.cluster.local'):
    q, o = run('cli', f'wget -q -T 2 -O /dev/null http://{nm} 2>&1; echo done', f'cli(ndots:5)访问 {nm}')
# restore
cm = kj('get', 'cm', 'coredns', '-n', 'kube-system'); cm['data']['Corefile'] = ORIG
for f in ('resourceVersion', 'uid', 'creationTimestamp'): cm['metadata'].pop(f, None)
k('apply', '-f', '-', input=json.dumps(cm)); k('delete', 'ns', NS, '--wait=false')
