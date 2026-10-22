import sys, os, asyncio; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path = [p for p in sys.path if os.path.basename(p) != 'exp']          # exp/ 里有 v2.py 等文件,会盖住 nacos SDK 的顶层包 v2
from msl import *
from v2.nacos import NacosNamingService, ClientConfigBuilder, RegisterInstanceParam
import urllib.parse, shutil
tee('v50'); reset()
print('注册信息里除了地址还该放什么、怎么隔离不同环境和团队。Nacos 3.2.4(自己起的单机实例,Java 17)的数据模型:namespace(命名空间,隔离环境)→ group(分组)→ service(服务名)→ cluster(集群,如机房)→ instance(实例,带 metadata 和 weight);用 nacos-sdk-python 3.2.0(gRPC)注册,用 HTTP 的 /nacos/v3/client/ns/instance/list 查询。对照:Consul 2.0.4 的 service 的 Tags / Meta / Weights 与过滤表达式')
N = Nacos('v50', 8870, 8871).start(); time.sleep(4)
def reg_all(specs):
    """每个实例用自己的一个 SDK 客户端(一条 gRPC 连接)去注册:Nacos 的临时实例绑定在连接上,同一个连接对同一个服务重复注册只会替换自己上一次的实例(我最初用一个客户端注册了三个,查询只剩最后一个)"""
    async def main():
        out = []
        for s in specs:
            cfg = ClientConfigBuilder().server_address('127.0.0.1:8870').namespace_id(s['ns']).build(); ns = await NacosNamingService.create_naming_service(cfg)
            await ns.register_instance(request=RegisterInstanceParam(service_name=s['svc'], group_name=s['group'], cluster_name=s['cluster'], ip=s['ip'], port=s['port'], weight=s['w'], metadata=s['meta'], ephemeral=True)); out.append(ns)
        return out
    return asyncio.run(main())
specs = [dict(ns='public', group='DEFAULT_GROUP', cluster='bj', svc='web', ip='10.0.0.1', port=8080, w=1.0, meta={'version': 'v1', 'zone': 'a'}),
         dict(ns='public', group='DEFAULT_GROUP', cluster='sh', svc='web', ip='10.0.1.1', port=8080, w=1.0, meta={'version': 'v1', 'zone': 'b'}),
         dict(ns='public', group='DEFAULT_GROUP', cluster='bj', svc='web', ip='10.0.0.2', port=8080, w=4.0, meta={'version': 'v2', 'zone': 'a'}),
         dict(ns='public', group='TEAM_B', cluster='bj', svc='web', ip='10.0.2.1', port=8080, w=1.0, meta={'version': 'v1'}),
         dict(ns='test', group='DEFAULT_GROUP', cluster='bj', svc='web', ip='10.9.0.1', port=8080, w=1.0, meta={'version': 'v1'}),
         dict(ns='test', group='DEFAULT_GROUP', cluster='bj', svc='web', ip='10.9.0.2', port=8080, w=1.0, meta={'version': 'v2'}),
         dict(ns='public', group='DEFAULT_GROUP', cluster='bj', svc='cart', ip='10.0.0.3', port=9090, w=1.0, meta={'version': 'v1'})]
CL = reg_all(specs); time.sleep(1.5)
def query(svc, ns='public', group='DEFAULT_GROUP', clusters=None, healthy=False):
    p = {'serviceName': svc, 'groupName': group, 'namespaceId': ns, 'healthyOnly': 'true' if healthy else 'false'}
    if clusters: p['clusterName'] = clusters
    s, d = N.http('GET', '/nacos/v3/client/ns/instance/list', p); j = json.loads(d); return j.get('data') or []
label = {s['ip']: f"{s['ip']}({s['cluster']},{s['meta']['version']},w={s['w']:g})" for s in specs}

# ============ 一 ============
print('== 一:命名空间 / 分组 / 集群如何隔离与过滤。登记了 7 个实例:public 空间 DEFAULT_GROUP 的 web 有 3 个(bj 集群两个、sh 集群一个)、TEAM_B 分组的 web 有 1 个、public 空间 cart 服务 1 个;test 空间 DEFAULT_GROUP 的 web 有 2 个。用不同的查询参数看各自能看到哪些实例')
qs = [('public · DEFAULT_GROUP · web', dict(svc='web')), ('public · DEFAULT_GROUP · web · clusterName=bj', dict(svc='web', clusters='bj')), ('public · DEFAULT_GROUP · web · clusterName=sh', dict(svc='web', clusters='sh')), ('public · TEAM_B · web', dict(svc='web', group='TEAM_B')), ('test · DEFAULT_GROUP · web', dict(svc='web', ns='test')), ('test · TEAM_B · web', dict(svc='web', ns='test', group='TEAM_B')), ('public · DEFAULT_GROUP · cart', dict(svc='cart')), ('public · 不带 groupName 参数', None)]
rows = []
for name, kw in qs:
    if kw is None:
        s, d = N.http('GET', '/nacos/v3/client/ns/instance/list', {'serviceName': 'web', 'namespaceId': 'public', 'healthyOnly': 'false'}); j = json.loads(d); ins = j.get('data') or []; extra = f'(HTTP {s})'
    else: ins = query(**kw); extra = ''
    rows.append((name, len(ins), ', '.join(label.get(i['ip'], i['ip']) for i in ins) or '(空)', extra))
table(rows, ['查询', '实例数', '看到的实例(地址(集群,版本,权重))', ''])
print('  同一个服务名 web 在不同的 namespace、不同的 group 下是完全不同的服务,互相看不到;cluster 是同一个服务内部的细分(这里按机房),查询时用 clusterName 参数过滤(v3 的 client API;我最初照 v2 的习惯写成 clusters,被服务端静默忽略,三个实例都返回了)。隔离的单位是 (namespace, group, 服务名) 这三元组,客户端配置错了 namespace 或 group,查到的是空列表而不是报错')

# ============ 二 ============
print('== 二:权重和元数据。public · DEFAULT_GROUP · web 下三个实例 10.0.0.1(权重 1)、10.0.1.1(权重 1)、10.0.0.2(权重 4)。客户端按权重加权随机选 10000 次;再按 metadata.version = v2 过滤后选。权重和元数据由注册方带上来,过滤和选择是客户端自己的逻辑')
ins = query('web'); wsum = sum(i['weight'] for i in ins); rng = random.Random(7); cnt = collections.Counter()
for _ in range(10000):
    r = rng.random() * wsum; acc = 0
    for i in ins:
        acc += i['weight']
        if r < acc: cnt[i['ip']] += 1; break
rows = [(label[ip], f'{c}', f'{c / 100:.1f}%', f"{[i for i in ins if i['ip'] == ip][0]['weight'] / wsum:.1%}") for ip, c in sorted(cnt.items())]
table(rows, ['实例', '被选中次数(10000 次)', '占比', '按权重应得的占比'])
v2 = [i for i in ins if i['metadata'].get('version') == 'v2']
print(f'  按 metadata.version = v2 过滤后剩下 {len(v2)} 个:{", ".join(label[i["ip"]] for i in v2)}。权重 4 的实例得到约 4/6 的流量;权重和元数据都是实例注册时带来的字符串/数字,服务端只负责存储和返回,过滤和加权选择要靠客户端(或网关)实现')

# ============ 三 ============
print('== 三:Consul 的对照。Consul 的服务有 Name、Tags(字符串列表)、Meta(键值对)、Weights(Passing / Warning 两个权重);没有 namespace(那是企业版功能),用 Name + Tags 或 Meta 自己区分环境。用一个 Consul 开发模式 agent 登记 web 的三个实例(env=prod 的两个、env=test 的一个),用 filter 表达式、tag 和 DNS SRV 查询')
import subprocess as sp
cdir = TT / 'v50consul'; shutil.rmtree(cdir, ignore_errors=True); cdir.mkdir()
ports = dict(http=free_port(), grpc=free_port(), dns=free_port(), lan=free_port(), wan=free_port(), srv=free_port(), tls=free_port())
cp = sp.Popen(['consul', 'agent', '-dev', f'-http-port={ports["http"]}', f'-grpc-port={ports["grpc"]}', f'-grpc-tls-port={ports["tls"]}', f'-dns-port={ports["dns"]}', f'-serf-lan-port={ports["lan"]}', f'-serf-wan-port={ports["wan"]}', f'-server-port={ports["srv"]}', '-log-level=warn'], stdout=open(cdir / 'c.log', 'w'), stderr=sp.STDOUT, start_new_session=True)
def chttp(method, path, body=None):
    c = http.client.HTTPConnection('127.0.0.1', ports['http'], timeout=5)
    try: c.request(method, path, body=json.dumps(body).encode() if body is not None else None); r = c.getresponse(); return r.status, r.read()
    finally: c.close()
for _ in range(100):
    try:
        if chttp('GET', '/v1/status/leader')[1].strip() not in (b'""', b''): break
    except Exception: pass
    time.sleep(0.2)
for iid, ip, env, ver, w in (('web1', '10.0.0.1', 'prod', 'v1', 1), ('web2', '10.0.0.2', 'prod', 'v2', 5), ('web3', '10.9.0.1', 'test', 'v1', 1)):
    chttp('PUT', '/v1/agent/service/register', {'ID': iid, 'Name': 'web', 'Address': ip, 'Port': 8080, 'Tags': [env, ver], 'Meta': {'env': env, 'version': ver}, 'Weights': {'Passing': w, 'Warning': 1}})
time.sleep(1.0)
rows = []
for name, path in (('全部', '/v1/catalog/service/web'), ('tag=prod', '/v1/catalog/service/web?tag=prod'), ('filter: Meta.env == "prod" and Meta.version == "v2"', '/v1/catalog/service/web?filter=' + urllib.parse.quote('ServiceMeta.env == "prod" and ServiceMeta.version == "v2"')), ('filter: ServiceTags contains "test"', '/v1/catalog/service/web?filter=' + urllib.parse.quote('"test" in ServiceTags'))):
    s, d = chttp('GET', path); arr = json.loads(d) if s == 200 else []
    rows.append((name, len(arr), ', '.join(f"{a['ServiceAddress']}(w={a['ServiceWeights']['Passing']})" for a in arr) if s == 200 else f'HTTP {s}: {d[:80].decode(errors="replace")}'))
table(rows, ['查询', '实例数', '看到的实例(地址(Passing 权重))'])
import socket as _s
def dns_srv(name):
    q = b'\xab\xcd\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00' + b''.join(bytes([len(p)]) + p.encode() for p in name.split('.')) + b'\x00\x00\x21\x00\x01'
    s = _s.socket(_s.AF_INET, _s.SOCK_DGRAM); s.settimeout(2); s.sendto(q, ('127.0.0.1', ports['dns'])); d, _ = s.recvfrom(4096); s.close(); return d
d1 = dns_srv('web.service.consul'); d2 = dns_srv('prod.web.service.consul')
print(f'  Consul 的 DNS 查询:web.service.consul 的 SRV 应答里有 {int.from_bytes(d1[6:8], "big")} 条记录;带 tag 的 prod.web.service.consul(<tag>.<service>.service.consul)有 {int.from_bytes(d2[6:8], "big")} 条。Consul 开源版没有 namespace,环境隔离靠 Tags / Meta 约定加上查询时过滤;Weights 的 Passing / Warning 分别是实例健康检查通过 / 警告时 DNS 应答里使用的权重')
os.killpg(cp.pid, signal.SIGKILL); N.stop()
