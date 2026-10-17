import sys, os, re, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k7')
cn, _ = up('main')
NS = ns('k7')
P = f'/api/v1/namespaces/{NS}/configmaps'
mk = lambda n, extra='': k('create', 'cm', n, '-n', NS, '--from-literal=v=1')
rv = lambda n: ko('get', 'cm', n, '-n', NS, '-o', 'jsonpath={.metadata.resourceVersion}')
mk('a'); mk('b'); r_a_b = rv('b')
k('patch', 'cm', 'a', '-n', NS, '--type=merge', '-p', '{"data":{"v":"2"}}'); k('delete', 'cm', 'b', '-n', NS); mk('c'); k('patch', 'cm', 'c', '-n', NS, '--type=merge', '-p', '{"data":{"v":"2"}}')
r_now = ko('get', '--raw', P).split('"resourceVersion":"')[1].split('"')[0]
print(f'集群 {cn};命名空间 {NS}:依次 创建 a、创建 b(rv={r_a_b})、修改 a、删除 b、创建 c、修改 c,当前 list 的 resourceVersion={r_now}')

print('== 一:从某个 resourceVersion 开始 watch——只会收到它之后发生的事件')
ev = watch_events(f'{P}?resourceVersion={r_a_b}', secs=2)
print(f'  watch?resourceVersion={r_a_b}(b 创建时的版本)收到 {len(ev)} 个事件:' + fmt_ev(ev))
ev = watch_events(f'{P}?resourceVersion={r_now}', secs=2)
print(f'  watch?resourceVersion={r_now}(当前版本)收到 {len(ev)} 个事件')
def ops(): k('create', 'cm', 'live', '-n', NS, '--from-literal=v=1'); k('delete', 'cm', 'live', '-n', NS)
ev = watch_events(f'{P}?resourceVersion={r_now}', ops=ops, secs=3)
print(f'  同样从 {r_now} 开始,watch 期间创建再删除 live:' + fmt_ev(ev))

print('== 二:不指定版本(或 0)——先把现有对象当作 ADDED 事件发一遍,再接实时事件')
ev = watch_events(P, secs=2); print(f'  不带 resourceVersion:{fmt_ev(ev)}')
ev = watch_events(P + '?resourceVersion=0', secs=2); print(f'  resourceVersion=0:{fmt_ev(ev)}')
ev = watch_events(P + '?sendInitialEvents=true&resourceVersionMatch=NotOlderThan&allowWatchBookmarks=true', secs=2)
print(f'  sendInitialEvents=true(流式 list):{fmt_ev(ev)}')
for t, n, r, e in ev:
    if t == 'BOOKMARK': print(f'    BOOKMARK 的注解:{e["object"]["metadata"].get("annotations")}')
print('  (b 在 resourceVersion=0 的结果里不存在:被删除的对象不会以事件的形式“补发”)')

print('== 三:版本太旧——apiserver 的 watch 缓存装不下那么久远的事件时,watch 得到 410 Gone')
def etcdctl(*a):
    return k('exec', '-n', 'kube-system', f'etcd-{cn}-control-plane', '--', 'etcdctl', '--endpoints=https://127.0.0.1:2379', '--cacert=/etc/kubernetes/pki/etcd/ca.crt', '--cert=/etc/kubernetes/pki/etcd/server.crt', '--key=/etc/kubernetes/pki/etcd/server.key', *a, raw=True)
k('create', 'cm', 'burst', '-n', NS, '--from-literal=i=0')
r_old = rv('burst'); t_start = time.time()
dt = burst(1200, NS)
rc, o = etcdctl('endpoint', 'status', '-w', 'json')
rev = json.loads(o)[0]['Status']['header']['revision']
rc, o = etcdctl('compact', str(rev))
print(f'  记下 burst 的 resourceVersion={r_old};再写 1200 次({dt:.0f} 秒);手动压缩 etcd 到 revision {rev}({o.strip()})')
ev = watch_events(f'{P}?resourceVersion={r_old}', secs=3)
print(f'  压缩之后从 {r_old} 开始 watch:收到 {len(ev)} 个事件,第一个是 {ev[0][0]} rv={ev[0][2]}——压缩没有让它失效,事件是从 apiserver 的 watch 缓存里补发的')
tot = 1200; expired = None
while tot < 9000 and not expired:
    burst(1000, NS); tot += 1000
    ev = watch_events(f'{P}?resourceVersion={r_old}', secs=2)
    e0 = ev[0] if ev else None
    if e0 and e0[0] == 'ERROR': expired = (tot, e0)
    print(f'  累计写入 {tot} 次(距 {r_old} 已过去 {time.time() - t_start:.0f} 秒):watch 收到 {len(ev)} 个事件,第一个是 {e0[0] if e0 else None}')
if expired:
    print('  出错时服务端发来的事件:' + json.dumps(expired[1][3], ensure_ascii=False))
cur = json.loads(ko('get', '--raw', P))['metadata']['resourceVersion']
ev = watch_events(f'{P}?resourceVersion={cur}', ops=lambda: k('patch', 'cm', 'burst', '-n', NS, '--type=merge', '-p', '{"data":{"i":"x"}}'), secs=2)
print(f'  恢复办法:重新 list 得到 resourceVersion={cur},再从它 watch:' + fmt_ev(ev))

print('== 四:带选择器的 watch——对象的标签变化会表现成 ADDED / DELETED')
k('create', 'cm', 'sel', '-n', NS, '--from-literal=v=1'); k('label', 'cm', 'sel', '-n', NS, 'app=x')
def ops4():
    k('label', 'cm', 'sel', '-n', NS, 'app=y', '--overwrite'); time.sleep(0.3)
    k('label', 'cm', 'sel', '-n', NS, 'app=x', '--overwrite'); time.sleep(0.3)
    k('patch', 'cm', 'sel', '-n', NS, '--type=merge', '-p', '{"data":{"v":"2"}}'); time.sleep(0.3)
    k('delete', 'cm', 'sel', '-n', NS)
ev = watch_events(f'{P}?labelSelector=app%3Dx&resourceVersion=0', ops=ops4, secs=4)
print('  watch?labelSelector=app=x 的事件序列(对象 sel 先后:标签改成 app=y → 改回 app=x → 改 data → 删除):')
for t, n, r, e in ev: print(f'    {t:<9} {n} rv={r}')
rmns(NS)
