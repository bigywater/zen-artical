import sys, os, time, json, re, threading, statistics, random, urllib.parse; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
from kazoo.recipe.watchers import ChildrenWatch, DataWatch
from kazoo.exceptions import NoNodeError
tee('z89'); R = {}
n = Node('z89', 7300, xmx=512, conf={'tickTime': 1000, 'maxClientCnxns': 500}).start(); adm = client('127.0.0.1:7300')
S_, M_ = 1000, 5
print(f'== 一:布局对比:{S_} 个服务 × 每个 {M_} 个实例。分层 /h/<服务>/<实例>  vs  平铺 /f/<服务>#<实例>(5000 个节点在同一个目录下)')
adm.ensure_path('/h'); adm.ensure_path('/f'); t0 = time.time()
for s in range(S_):
    adm.ensure_path(f'/h/svc{s:04d}')
    for m in range(M_): adm.create_async(f'/h/svc{s:04d}/inst{m}', b'x'); adm.create_async(f'/f/svc{s:04d}#inst{m}', b'x')
time.sleep(3); print(f'  建节点:分层 /h 下每个服务 {len(adm.get_children("/h/svc0042"))} 个实例(共 {S_} 个服务目录);平铺 /f 下 {len(adm.get_children("/f"))} 个节点')
px = Proxy(7310, 7300).start(); c1 = client('127.0.0.1:7310'); b0 = px.bytes_down; c1.get_children('/h/svc0042'); bh = px.bytes_down - b0; b0 = px.bytes_down; c1.get_children('/f'); bf = px.bytes_down - b0
print(f'  消费者想知道 svc0042 的实例列表:分层 get_children 返回 {bh} 字节;平铺要拉整个目录 {bf} 字节')
R['list_bytes'] = dict(h=bh, f=bf)
cnt = dict(h=0, f=0); ChildrenWatch(c1, '/h/svc0042', lambda k: cnt.__setitem__('h', cnt['h'] + 1)); ChildrenWatch(c1, '/f', lambda k: cnt.__setitem__('f', cnt['f'] + 1)); time.sleep(0.5); cnt.update(h=0, f=0)
t1 = time.time(); changes = 100
for i in range(changes):
    s = random.randrange(S_)
    adm.create(f'/h/svc{s:04d}/tmp{i}', b'x', ephemeral=False); adm.delete(f'/h/svc{s:04d}/tmp{i}'); adm.create(f'/f/svc{s:04d}#tmp{i}', b'x'); adm.delete(f'/f/svc{s:04d}#tmp{i}')
time.sleep(0.5)
print(f'  随机改 {changes} 次不同服务的实例列表(每次一建一删):订阅 svc0042 的分层消费者回调 {cnt["h"]} 次;订阅整个平铺目录的消费者回调 {cnt["f"]} 次(每次回调都要重新拉 {bf} 字节)')
R['callbacks'] = dict(h=cnt['h'], f=cnt['f'], changes=changes)
print()
print('== 二:实例信息里有 / : ? 之类的字符(比如 dubbo://10.0.0.1:20880/com.foo.Bar?weight=100)不能直接当节点名')
raw = 'dubbo://10.0.0.1:20880/com.foo.Bar?weight=100'; adm.ensure_path('/reg/prov')
try: adm.create('/reg/prov/' + raw, b''); r = '成功'
except Exception as e: r = type(e).__name__
print(f'  直接 create /reg/prov/{raw} → {r}(/ 被当成层级分隔符,试图在不存在的 dubbo:/10.0.0.1:20880/... 下建节点)')
enc = urllib.parse.quote(raw, safe=''); adm.create('/reg/prov/' + enc, b''); print(f'  URL 编码后 create 成功:/reg/prov/{enc}')
print('  读回列表并解码:', [urllib.parse.unquote(x) for x in adm.get_children('/reg/prov')])
R['enc'] = dict(raw=raw, err=r, enc=enc)
print()
print('== 三:实例的权重等元信息放在哪?放在节点数据里 vs 编码进节点名:一个消费者订阅一个服务的 200 个实例,服务端要维护多少个 watch')
c1.stop(); time.sleep(0.5); adm.ensure_path('/m1'); adm.ensure_path('/m2')
for i in range(200): adm.create(f'/m1/i{i:03d}', json.dumps({'w': 100}).encode()); adm.create(f'/m2/i{i:03d}%3Fw%3D100', b'')
def wch(): return int(kv(four(7300, 'mntr'))['zk_watch_count'])
base = wch(); print(f'  (开始前服务端上的 watch 总数 = {base})'); c2 = client('127.0.0.1:7300')
cc = []; ChildrenWatch(c2, '/m2', lambda k: cc.append(len(k))); time.sleep(0.3); cc.clear(); w_name = wch() - base
c3 = client('127.0.0.1:7300'); got = []
def dw(i): DataWatch(c3, f'/m1/i{i:03d}', lambda d, s: got.append(1))
for i in range(200): dw(i)
ChildrenWatch(c3, '/m1', lambda k: None); time.sleep(0.5); w_data = wch() - base - w_name
adm.set('/m1/i005', json.dumps({'w': 10}).encode()); time.sleep(0.3)
print(f'  元信息编码进节点名(只有目录上的 1 个 children watch):服务端为该消费者维护 {w_name} 个 watch;元信息放节点数据(每个实例一个 DataWatch + 目录一个 ChildrenWatch):{w_data} 个 watch')
adm.delete('/m2/i005%3Fw%3D100'); adm.create('/m2/i005%3Fw%3D10', b''); time.sleep(0.5)
print(f'  改一个实例的权重:数据方式下消费者收到 {len(got) - 200} 次回调(只针对那个实例);名字方式要删旧节点、建新节点,消费者的 children 回调 {len(cc)} 次,每次回调后要重新读整个 200 项的目录')
R['watch'] = dict(name=w_name, data=w_data)
for x in (c2, c3, adm): x.stop()
n.stop(); save('z89', R); os._exit(0)
