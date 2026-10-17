import sys, os, re, time, json, ssl, http.client, threading, urllib.parse, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k17')
cn, _ = up('main')
NS = ns('k17')
k('delete', 'flowschema', 'k17-fs', '--ignore-not-found'); k('delete', 'prioritylevelconfiguration', 'k17-tiny', '--ignore-not-found')
k('create', 'sa', 'hammer', '-n', NS)
k('delete', 'clusterrolebinding', 'k17-hammer-view', '--ignore-not-found'); k('create', 'clusterrolebinding', 'k17-hammer-view', '--clusterrole=view', f'--serviceaccount={NS}:hammer')
tok = ko('create', 'token', 'hammer', '-n', NS, '--duration=1h')
srv = urllib.parse.urlparse(ko('config', 'view', '--minify', '-o', 'jsonpath={.clusters[0].cluster.server}'))
FS = {i['metadata']['uid']: i for i in kj('get', 'flowschemas')['items']}
PL = {i['metadata']['uid']: i for i in kj('get', 'prioritylevelconfigurations')['items']}
def req(path, token=None):
    c = http.client.HTTPSConnection(srv.hostname, srv.port, context=ssl._create_unverified_context(), timeout=30)
    h = {'Authorization': 'Bearer ' + token} if token else {}
    c.request('GET', path, headers=h); r = c.getresponse(); body = r.read()
    out = (r.status, {k_.lower(): v for k_, v in r.getheaders()}, body); c.close(); return out
def who(headers):
    return (FS.get(headers.get('x-kubernetes-pf-flowschema-uid'), {}).get('metadata', {}).get('name', '?'), PL.get(headers.get('x-kubernetes-pf-prioritylevel-uid'), {}).get('metadata', {}).get('name', '?'))
print(f'集群 {cn};API Priority and Fairness(APF):每个请求先按 FlowSchema 归类,再进入对应 PriorityLevel 的并发份额和队列;被限流时返回 429')

print('== 一:集群里默认的 PriorityLevelConfiguration(并发份额)与 FlowSchema 的数量')
rc, o = k('get', '--raw', '/metrics', raw=True)
seats = {}
for l in o.splitlines():
    m = re.match(r'apiserver_flowcontrol_nominal_limit_seats\{priority_level="([^"]+)"\} (\S+)', l)
    if m: seats[m.group(1)] = int(float(m.group(2)))
rows = []
for p in sorted(PL.values(), key=lambda x: x['metadata']['name']):
    s = p['spec']; lim = s.get('limited') or {}
    rows.append((p['metadata']['name'], s['type'], lim.get('nominalConcurrencyShares', '-'), (lim.get('limitResponse') or {}).get('type', '-'), (lim.get('limitResponse', {}).get('queuing') or {}).get('queues', '-'), seats.get(p['metadata']['name'], '-')))
print('  ' + table([['优先级名称', '类型', '并发份额', '超限时', '队列数', '并发席位(seats)']] + [list(map(str, r)) for r in rows]).replace('\n', '\n  '))
print(f'  FlowSchema 共 {len(FS)} 个;其中 matchingPrecedence 最小(最先匹配)的前 4 个:' + ', '.join(f'{f["metadata"]["name"]}({f["spec"]["matchingPrecedence"]})→{f["spec"]["priorityLevelConfiguration"]["name"]}' for f in sorted(FS.values(), key=lambda x: x['spec']['matchingPrecedence'])[:4]))

print('== 二:不同的身份被归到不同的 FlowSchema / 优先级(用响应头 X-Kubernetes-PF-FlowSchema-UID / PriorityLevel-UID 反查)')
rc, o = k('get', '--raw', '/api/v1/namespaces/default', '-v=8', raw=True)
hd = {}
for l in o.splitlines():
    m = re.search(r'(X-Kubernetes-Pf-(?:Flowschema|Prioritylevel)-Uid):\s*(\S+)', l, re.I)
    if m: hd[m.group(1).lower()] = m.group(2)
who_ = ko('auth', 'whoami', '-o', 'jsonpath={.status.userInfo.username}|{.status.userInfo.groups}')
print(f'  kubectl(客户端证书,身份 {who_}):FlowSchema={who(hd)[0]} PriorityLevel={who(hd)[1]}')
st, h, b = req('/version'); print(f'  匿名访问 /version:HTTP {st};FlowSchema={who(h)[0]} PriorityLevel={who(h)[1]}')
st, h, b = req('/api/v1/namespaces/default/pods', tok); print(f'  ServiceAccount k17/hammer(绑定了 view)请求 pods(HTTP {st}):FlowSchema={who(h)[0]} PriorityLevel={who(h)[1]}')
st, h, b = req('/api/v1/namespaces/default/pods', 'bad-token'); print(f'  无效令牌:HTTP {st};响应头里 {"有" if "x-kubernetes-pf-flowschema-uid" in h else "没有"} FlowSchema(认证失败的请求在进入 APF 之前就被拒了)')

def hammer(token, threads=80, secs=5, path='/api/v1/pods'):
    res = []; stop = time.time() + secs; lock = threading.Lock(); first429 = []
    def w():
        c = http.client.HTTPSConnection(srv.hostname, srv.port, context=ssl._create_unverified_context(), timeout=60)
        while time.time() < stop:
            t0 = time.time()
            try:
                c.request('GET', path, headers={'Authorization': 'Bearer ' + token}); r = c.getresponse(); body = r.read(); st = r.status
                if st == 429 and not first429: first429.append((dict((k_.lower(), v) for k_, v in r.getheaders()), body[:300]))
            except Exception: st = -1; c = http.client.HTTPSConnection(srv.hostname, srv.port, context=ssl._create_unverified_context(), timeout=60)
            with lock: res.append((st, (time.time() - t0) * 1000))
    ts_ = [threading.Thread(target=w) for _ in range(threads)]
    [t.start() for t in ts_]; [t.join() for t in ts_]
    return res, first429
def mval(pat, **lab):
    rc, o = k('get', '--raw', '/metrics', raw=True); t = 0
    for l in o.splitlines():
        if l.startswith(pat + '{') and all(f'{a}="{b}"' in l for a, b in lab.items()): t += float(l.rsplit(' ', 1)[1])
    return t
def summ(res, secs):
    codes = {}
    for st, _ in res: codes[st] = codes.get(st, 0) + 1
    lat = sorted(l for st, l in res if st == 200)
    p = lambda q: lat[min(len(lat) - 1, int(len(lat) * q))] if lat else 0
    return f'共 {len(res)} 个请求({len(res) / secs:.0f}/秒),状态码 {dict(sorted(codes.items()))};成功请求的延迟 p50={p(0.5):.0f} ms p95={p(0.95):.0f} ms 最大={lat[-1] if lat else 0:.0f} ms'

print('== 三:自己建一个只有 1 份并发份额、超限直接拒绝的优先级,把 hammer 压进去')
y = f'''
apiVersion: flowcontrol.apiserver.k8s.io/v1
kind: PriorityLevelConfiguration
metadata: {{name: k17-tiny}}
spec:
  type: Limited
  limited:
    nominalConcurrencyShares: 1
    lendablePercent: 0
    limitResponse: {{type: Reject}}
---
apiVersion: flowcontrol.apiserver.k8s.io/v1
kind: FlowSchema
metadata: {{name: k17-fs}}
spec:
  matchingPrecedence: 100
  priorityLevelConfiguration: {{name: k17-tiny}}
  distinguisherMethod: {{type: ByUser}}
  rules:
  - subjects: [{{kind: ServiceAccount, serviceAccount: {{name: hammer, namespace: {NS}}}}}]
    resourceRules: [{{verbs: ["*"], apiGroups: ["*"], resources: ["*"], clusterScope: true, namespaces: ["*"]}}]
'''
rc, o = apply(y); assert rc == 0, o
time.sleep(3)
PL = {i['metadata']['uid']: i for i in kj('get', 'prioritylevelconfigurations')['items']}; FS = {i['metadata']['uid']: i for i in kj('get', 'flowschemas')['items']}
rc, o = k('get', '--raw', '/metrics', raw=True)
seat = next((int(float(l.rsplit(' ', 1)[1])) for l in o.splitlines() if l.startswith('apiserver_flowcontrol_nominal_limit_seats{') and 'k17-tiny' in l), None)
st, h, b = req('/api/v1/namespaces/default/pods', tok)
print(f'  创建 PriorityLevelConfiguration k17-tiny(份额 1,limitResponse=Reject)和 FlowSchema k17-fs(matchingPrecedence=100,匹配 SA hammer);k17-tiny 得到的并发席位 nominal_limit_seats={seat}')
print(f'  hammer 再请求一次:FlowSchema={who(h)[0]} PriorityLevel={who(h)[1]}(原来是 service-accounts / workload-low,因为 100 比默认的更靠前)')
rj0 = mval('apiserver_flowcontrol_rejected_requests_total', priority_level='k17-tiny'); res, f429 = hammer(tok, 80, 5)
print(f'  80 个线程连续请求 5 秒(GET /api/v1/pods):{summ(res, 5)}')
if f429:
    hh, bb = f429[0]; print(f'  第一个 429 的响应头 Retry-After={hh.get("retry-after")};x-kubernetes-pf-flowschema-uid → {who(hh)[0]};响应体:{bb.decode()[:230]}')
print(f'  apiserver_flowcontrol_rejected_requests_total{{priority_level="k17-tiny"}} 增加了 {mval("apiserver_flowcontrol_rejected_requests_total", priority_level="k17-tiny") - rj0:.0f}(reason=concurrency-limit)')

print('== 四:同样的压力,把超限处理改成排队(Queue)——不再返回 429,但等待变长')
y2 = y.replace('limitResponse: {type: Reject}', 'limitResponse: {type: Queue, queuing: {queues: 4, queueLengthLimit: 100, handSize: 2}}')
rc, o = apply(y2); assert rc == 0, o
time.sleep(3)
rj1 = mval('apiserver_flowcontrol_rejected_requests_total', priority_level='k17-tiny'); w0 = mval('apiserver_flowcontrol_request_wait_duration_seconds_count', priority_level='k17-tiny', execute='true'); res, f429 = hammer(tok, 80, 5)
print(f'  limitResponse=Queue(queues=4,queueLengthLimit=100,handSize=2),同样 80 线程 5 秒:{summ(res, 5)}')
print(f'  这一轮 rejected 增加了 {mval("apiserver_flowcontrol_rejected_requests_total", priority_level="k17-tiny") - rj1:.0f};排过队后执行的请求(request_wait_duration_seconds_count{{execute="true"}})增加了 {mval("apiserver_flowcontrol_request_wait_duration_seconds_count", priority_level="k17-tiny", execute="true") - w0:.0f}')
k('delete', 'clusterrolebinding', 'k17-hammer-view', '--ignore-not-found')
k('delete', 'flowschema', 'k17-fs'); k('delete', 'prioritylevelconfiguration', 'k17-tiny'); rmns(NS)
