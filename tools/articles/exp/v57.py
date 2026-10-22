import sys, os, asyncio; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path = [p for p in sys.path if os.path.basename(p) != 'exp']          # exp/ 里有 v2.py 等文件,会盖住 nacos SDK 的顶层包 v2
from msl import *
from etcdt import Etcd, b64
import shutil, hashlib, base64 as b64mod, urllib.parse
from v2.nacos import NacosConfigService, ClientConfigBuilder, ConfigParam
tee('v57'); reset()
print('配置的版本与回滚。Nacos 3.2.4(自己起的单机实例,Java 17)的配置历史与回滚、删除后恢复、并发编辑时的 CAS;对照 etcd 3.7.2 的 revision(带压缩)和 Consul 2.0.4 的 KV(是否有历史)。Nacos 的发布、历史、删除用管理 API(/nacos/v3/admin/cs/…),CAS 用 nacos-sdk-python 3.2.0')
shutil.rmtree(TT / 'nacos_v57', ignore_errors=True)
N = Nacos('v57', 8854, 8855).start(); time.sleep(4)
md5 = lambda s: hashlib.md5(s.encode()).hexdigest()
def pub(did, content, **kw):
    s, d = N.http('POST', '/nacos/v3/admin/cs/config', body={'dataId': did, 'groupName': 'DEFAULT_GROUP', 'content': content, 'type': 'text', **kw}, timeout=10.0); return s, json.loads(d)
def cur(did):
    s, d = N.http('GET', '/nacos/v3/admin/cs/config', {'dataId': did, 'groupName': 'DEFAULT_GROUP'}, timeout=10.0); j = json.loads(d)
    return (j['data'] or {}).get('content') if s == 200 and j.get('code') == 0 else f'(HTTP {s} code {j.get("code")})'
def hist(did):
    s, d = N.http('GET', '/nacos/v3/admin/cs/history/list', {'dataId': did, 'groupName': 'DEFAULT_GROUP', 'pageNo': 1, 'pageSize': 50}, timeout=10.0)
    items = json.loads(d)['data']['pageItems']; out = []
    for it in items:
        s2, d2 = N.http('GET', '/nacos/v3/admin/cs/history', {'dataId': did, 'groupName': 'DEFAULT_GROUP', 'nid': it['id']}, timeout=10.0); full = json.loads(d2)['data']
        out.append((int(it['id']), it['opType'].strip(), it['modifyTime'], full.get('content')))
    return out

# ============ 一 ============
print('== 一:Nacos 的历史版本到底存了什么。对 rb 依次发布 v1 到 v6(间隔 0.3 s),取历史列表和每条历史的内容,再取当前内容')
for i in range(1, 7): assert pub('rb', f'v{i}')[0] == 200; time.sleep(0.3)
H = sorted(hist('rb')); t0 = H[0][2]
table([(i, op, f'{(t - t0) / 1000:.1f}', repr(c)) for i, op, t, c in H], ['历史条目 id', 'opType', '修改时间(相对第一条,s)', '这条历史里的内容'])
print(f'  当前内容:{cur("rb")!r};历史共 {len(H)} 条,发布了 6 次。每条历史里放的是那次修改“之前”的内容,所以最新的一版(当前内容)不在历史列表里,要回滚到某个旧版本,取的是比它晚一条的历史')

# ============ 二 ============
print('== 二:回滚。想回到 v3:找到历史里内容是 v3 的那一条,把它的内容重新发布。看回滚之后的当前内容、它的 md5 是不是和当初 v3 的 md5 一样,以及历史里多了什么;再“撤销回滚”(回到回滚之前的 v6)')
n_before = len(H); target = next(e for e in H if e[3] == 'v3')
s, j = pub('rb', target[3]); H2 = sorted(hist('rb')); c = cur('rb')
newest = H2[-1]
print(f'  回滚(重新发布历史 id {target[0]} 的内容):HTTP {s};当前内容 {c!r},md5 与 v3 原来的 md5 {"相同" if md5(c) == md5("v3") else "不同"};历史从 {n_before} 条变成 {len(H2)} 条,最新一条(id {newest[0]})存的内容是 {newest[3]!r}')
s, j = pub('rb', newest[3]); c2 = cur('rb')
print(f'  用最新一条历史的内容再发布一次(撤销回滚):当前内容 {c2!r};历史现在 {len(hist("rb"))} 条')

# ============ 三 ============
print('== 三:删除之后。对 gone 发布 g1、g2,然后删除这个配置;查当前内容、历史列表(是否多了删除记录,删除记录里存的内容);再用历史把配置恢复')
pub('gone', 'g1'); time.sleep(0.2); pub('gone', 'g2'); time.sleep(0.2)
s, d = N.http('DELETE', '/nacos/v3/admin/cs/config', {'dataId': 'gone', 'groupName': 'DEFAULT_GROUP'}, timeout=10.0)
G = sorted(hist('gone')); print(f'  DELETE:HTTP {s} {d.decode()[:60]};删除之后当前内容:{cur("gone")}')
table([(i, op, repr(c)) for i, op, t, c in G], ['历史条目 id', 'opType', '这条历史里的内容'])
dent = [e for e in G if e[1] == 'D'][-1]; s, j = pub('gone', dent[3]); print(f'  用删除记录里的内容重新发布:HTTP {s};当前内容 {cur("gone")!r}(删除之前最后一版是 g2)')

# ============ 四 ============
print('== 四:并发编辑。配置内容是两行 “a: 1” 和 “b: 1”。编辑者 1 把 a 改成 2,编辑者 2 把 b 改成 2;两人都是先读到原来的内容再各自修改并发布。(a)都不带 CAS;(b)编辑者 2 发布时带上自己读到内容的 md5 作为 cas_md5(SDK),被拒绝后重新读取、合并、再带新的 md5 发布')
async def edit_demo():
    cs = await NacosConfigService.create_config_service(ClientConfigBuilder().server_address('127.0.0.1:8854').build())
    base = 'a: 1\nb: 1'
    out = {}
    async def p(did, content, cas=''):
        try: return await cs.publish_config(ConfigParam(data_id=did, group='DEFAULT_GROUP', content=content, cas_md5=cas, type='text'))
        except Exception as e: return f'{type(e).__name__}: {str(e)[:90]}'
    # 读一律走管理 API(权威);SDK 的 get_config 在刚发布之后会读到空串或旧内容,下面单独记一笔
    await p('ed_a', base); r1 = cur('ed_a'); r2 = r1
    out['a_pub1'] = await p('ed_a', r1.replace('a: 1', 'a: 2')); out['a_pub2'] = await p('ed_a', r2.replace('b: 1', 'b: 2')); out['a_final'] = cur('ed_a')
    await p('ed_b', base); r1 = cur('ed_b'); r2 = r1; m0 = md5(r2)
    out['b_pub1'] = await p('ed_b', r1.replace('a: 1', 'a: 2'), md5(r1)); out['b_pub2'] = await p('ed_b', r2.replace('b: 1', 'b: 2'), m0)
    mid = cur('ed_b'); out['b_mid'] = mid
    out['b_pub3'] = await p('ed_b', mid.replace('b: 1', 'b: 2'), md5(mid)); out['b_final'] = cur('ed_b')
    await p('ed_c', 'c0'); g0 = await cs.get_config(ConfigParam(data_id='ed_c', group='DEFAULT_GROUP')); await asyncio.sleep(1.5); g1 = await cs.get_config(ConfigParam(data_id='ed_c', group='DEFAULT_GROUP'))
    await p('ed_c', 'c1', md5('c0')); h0 = await cs.get_config(ConfigParam(data_id='ed_c', group='DEFAULT_GROUP')); await asyncio.sleep(1.5); h1 = await cs.get_config(ConfigParam(data_id='ed_c', group='DEFAULT_GROUP'))
    out['sdk_get'] = (g0, g1, h0, h1)
    await cs.shutdown(); return out
o = asyncio.run(edit_demo())
table([('(a)不带 CAS', '编辑者 1 发布', repr(o['a_pub1']), ''), ('(a)不带 CAS', '编辑者 2 发布', repr(o['a_pub2']), f'最终内容 {o["a_final"]!r}'),
       ('(b)带 cas_md5', '编辑者 1 发布(md5 与当前一致)', repr(o['b_pub1']), ''), ('(b)带 cas_md5', '编辑者 2 发布(md5 已过期)', repr(o['b_pub2']), ''),
       ('(b)带 cas_md5', '编辑者 2 重新读取、合并、再发布', repr(o['b_pub3']), f'最终内容 {o["b_final"]!r}')], ['场景', '操作', 'publish_config 返回', '备注'])
g0, g1, h0, h1 = o['sdk_get']
print(f'  另一个观察:用 SDK 发布 c0 后立刻 get_config 得到 {g0!r},1.5 s 后得到 {g1!r};再用 SDK(带 cas_md5)发布 c1,立刻 get_config 得到 {h0!r},1.5 s 后得到 {h1!r}。所以上面的读取都走管理 API')
s, j = pub('cas_http', 'x'); s2, j2 = pub('cas_http', 'y', casMd5='deadbeef')
print(f'  顺带一个观察:管理 API 的 POST 带 casMd5=deadbeef(明显不对的 md5)发布,返回 HTTP {s2} {j2};当前内容 {cur("cas_http")!r}。这个参数名在这个版本的管理 API 上没有起作用(我没有查正确的参数名),要用 CAS 就走 SDK')
N.stop()

# ============ 五 ============
print('== 五:etcd 和 Consul 的对照。etcd 的每次写入都有全局递增的 revision,旧 revision 可以读,直到被 compaction 压缩掉;Consul 的 KV 这里只测:带一个旧的 ModifyIndex 去读,会得到什么。单节点 etcd:对 /cfg 写 v1 到 v5,按旧 revision 读,然后 compact,再按旧 revision 读;Consul:写 v1、v2,然后按旧索引读')
shutil.rmtree(TT / 'etcd_v57_0', ignore_errors=True); E = Etcd('v57', n=1).start()
dec = lambda s: b64mod.b64decode(s).decode()
revs = []
for i in range(1, 6): revs.append(int(E.call(0, '/v3/kv/put', {'key': b64('/cfg'), 'value': b64(f'v{i}')})[1]['header']['revision']))
def rd(rev=None):
    body = {'key': b64('/cfg')}
    if rev: body['revision'] = str(rev)
    s, d = E.call(0, '/v3/kv/range', body); 
    return (s, dec(d['kvs'][0]['value']) if d.get('kvs') else None, d.get('message') or d.get('error') or '')
kv = E.call(0, '/v3/kv/range', {'key': b64('/cfg')})[1]['kvs'][0]
rows = [(f'按 revision {revs[1]} 读(未压缩)', rd(revs[1])[1] or rd(revs[1])[2])]
E.call(0, '/v3/kv/compaction', {'revision': str(revs[4]), 'physical': True}); time.sleep(0.3)
s, v, m = rd(revs[1]); rows.append((f'compact 到 revision {revs[4]} 之后,按 revision {revs[1]} 读', f'HTTP {s} {v if v else m[:70]}'))
s, v, m = rd(revs[4]); rows.append((f'compact 之后,按 revision {revs[4]} 读', f'HTTP {s} {v if v else m[:70]}'))
table(rows, ['操作', '结果'])
print(f'  key 的元数据:version={kv["version"]}(这个 key 被写了几次),create_revision={kv["create_revision"]},mod_revision={kv["mod_revision"]}(全局 revision);五次写入的 revision:{revs}')
E.kill_node(0)
shutil.rmtree(TT / 'v57c_0', ignore_errors=True); CC = ConsulCluster('v57c', 1).start()
CC.http(0, 'PUT', '/v1/kv/k', b'v1'); s, d = CC.http(0, 'GET', '/v1/kv/k'); m1 = json.loads(d)[0]['ModifyIndex']; CC.http(0, 'PUT', '/v1/kv/k', b'v2')
t0 = time.perf_counter(); c = http.client.HTTPConnection('127.0.0.1', CC.ports[0]['http'], timeout=10); c.request('GET', f'/v1/kv/k?index={m1 - 1}&wait=2s'); r = c.getresponse(); dd = r.read(); dt = time.perf_counter() - t0; c.close()
j = json.loads(dd)[0]
print(f'  Consul:写了 v1(ModifyIndex {m1})和 v2;用 index={m1 - 1}(早于 v1 的修改)读,{dt * 1000:.0f} ms 后返回的是 ModifyIndex {j["ModifyIndex"]} 的值 {b64mod.b64decode(j["Value"]).decode()!r};也就是说带旧索引读(blocking query 的 index 参数)得到的是当前值,不是旧版本。我没有在文档或其他接口里找按旧版本读的办法(没有穷尽)')
CC.stop_all()
print('ERRORS', dict(ERRORS))
