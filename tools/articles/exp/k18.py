import sys, os, re, time, json, shutil, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k18')
cn, dt_up = up('audit', cfg=open(KT / 'audit' / 'kind.yaml').read())
NODE = f'{cn}-control-plane'
NS = ns('k18')
def events():
    rc, o = sh('docker', 'exec', NODE, 'cat', '/var/log/kubernetes/audit.log', raw=True)
    r = []
    for l in o.splitlines():
        try: r.append(json.loads(l))
        except Exception: pass
    return r
def mine(since_n, user='kubernetes-admin'):
    return [e for e in events()[since_n:] if e.get('user', {}).get('username') == user]
def brief(e):
    ref = e.get('objectRef') or {}
    return f'stage={e["stage"]:<16} level={e["level"]:<16} verb={e["verb"]:<7} uri={e["requestURI"][:70]} code={(e.get("responseStatus") or {}).get("code", "-")} requestObject={"有" if "requestObject" in e else "无"} responseObject={"有" if "responseObject" in e else "无"}'
print(f'集群 {cn}(单节点,apiserver 带 --audit-policy-file 与 --audit-log-path,日志文件在节点里的 /var/log/kubernetes/audit.log);审计策略按顺序匹配,第一条匹配的规则决定记录级别')
print('  策略里的规则(按顺序):' + ' | '.join(['None:健康检查/version', 'None:系统组件', 'Metadata:secrets', 'RequestResponse:k18 的 configmaps', 'Request:k18 的 pods(omit RequestReceived)', 'Metadata:其余(omit RequestReceived)']))

print('== 一:一次 kubectl create configmap 在审计日志里留下什么(用 Audit-Id 把响应头和日志对上)')
n0 = len(events())
rc, o = k('create', 'cm', 'c1', '-n', NS, '--from-literal=password=hunter2', '-v=8', raw=True)
ids = re.findall(r'Audit-Id:\s*([0-9a-f-]{36})', o)
time.sleep(1.5)
ev = [e for e in events()[n0:] if e['auditID'] in ids and e['verb'] == 'create']
aid = ev[0]['auditID'] if ev else None
print(f'  kubectl -v=8 的响应头里有 Audit-Id:{aid};日志里这个 auditID 共 {len(ev)} 条:')
for e in ev: print('    ' + brief(e))
e = next((x for x in ev if x['stage'] == 'ResponseComplete'), None)
if e:
    print(f'  ResponseComplete 的关键字段:user.username={e["user"]["username"]};user.groups={e["user"]["groups"]};userAgent={e["userAgent"].split(" ")[0]};sourceIPs={e["sourceIPs"]}')
    print(f'    objectRef={json.dumps(e["objectRef"], ensure_ascii=False)};responseStatus.code={e["responseStatus"]["code"]}')
    print(f'    annotations={json.dumps(e.get("annotations"), ensure_ascii=False)}')
    print(f'    requestObject.data={e["requestObject"].get("data")}(明文口令出现在了审计日志里)')
k('create', 'secret', 'generic', 's1', '-n', NS, '--from-literal=password=hunter2'); time.sleep(1.5)
rc, o = sh('docker', 'exec', NODE, 'sh', '-c', "grep -c hunter2 /var/log/kubernetes/audit.log; grep '\"resource\":\"secrets\"' /var/log/kubernetes/audit.log | grep -c hunter2", raw=True)
cm_hits, sec_hits = o.split()[:2]
print(f'  同样的口令 hunter2 在日志文件里出现 {cm_hits} 行,其中属于 secrets 的有 {sec_hits} 行(Secret 的规则是 Metadata,只记元数据)')

print('== 二:三种级别——同样是“创建一个对象”,日志里的内容不一样')
n0 = len(events())
k('create', 'cm', 'c2', '-n', NS, '--from-literal=a=1')
k('apply', '-f', '-', input=f'apiVersion: v1\nkind: Pod\nmetadata: {{name: p1, namespace: {NS}}}\nspec:\n  containers: [{{name: c, image: busybox:1.36, command: [sleep, "3600"]}}]\n')
k('create', 'ns', 'k18-meta')
time.sleep(1.5)
for e in mine(n0):
    if e['verb'] == 'create' and (e.get('objectRef') or {}).get('resource') in ('configmaps', 'pods', 'namespaces'):
        print(f'  创建 {e["objectRef"]["resource"]:<11} → ' + brief(e))
k('delete', 'ns', 'k18-meta', '--wait=false')

print('== 三:一条 kubectl 命令发出多少个请求——对比冷缓存和热缓存')
cdir = KT / 'k18cache'; shutil.rmtree(cdir, ignore_errors=True)
def run_get():
    n0 = len(events()); env = dict(os.environ, KUBECACHEDIR=str(cdir))
    subprocess.run(['kubectl', '--kubeconfig', kcfg(), 'get', 'pods', '-n', NS], capture_output=True, env=env); time.sleep(1.5)
    ev = [e for e in mine(n0) if e['stage'] == 'ResponseComplete']
    return ev
cold = run_get()
print(f'  冷缓存(发现缓存目录是空的)kubectl get pods -n k18:审计日志里 {len(cold)} 条请求,其中 GET 发现类接口 {sum(1 for e in cold if e["requestURI"].startswith(("/api", "/openapi")) and "pods" not in e["requestURI"])} 条;真正列出 pods 的 {sum(1 for e in cold if "/namespaces/k18/pods" in e["requestURI"])} 条')
for e in cold[:6]: print(f'    {e["verb"]} {e["requestURI"][:85]}')
print(f'    …(共 {len(cold)} 条)')
hot = run_get()
print(f'  热缓存(紧接着再跑一次)kubectl get pods -n k18:{len(hot)} 条请求:' + ' | '.join(f'{e["verb"]} {e["requestURI"][:70]}' for e in hot))
pod_ev = next((e for e in hot if "/namespaces/k18/pods" in e["requestURI"]), None)
if pod_ev: print(f'  那条列出 pods 的请求:level={pod_ev["level"]}(k18 的 pods 规则是 Request,但 get/list 没有请求体,所以 requestObject={"有" if "requestObject" in pod_ev else "无"})')

print('== 四:被拒绝的请求也在日志里——授权决定、被模拟的用户、匿名请求')
k('create', 'sa', 'nobody', '-n', NS)
n0 = len(events())
rc, o = k('get', 'pods', '-n', NS, '--as', f'system:serviceaccount:{NS}:nobody'); print(f'  kubectl get pods --as system:serviceaccount:{NS}:nobody:{o.strip().splitlines()[0][:200]}')
srv = ko('config', 'view', '--minify', '-o', 'jsonpath={.clusters[0].cluster.server}')
subprocess.run(['curl', '-sk', f'{srv}/api/v1/namespaces/{NS}/pods'], capture_output=True)
time.sleep(1.5)
for e in events()[n0:]:
    if e['stage'] == 'ResponseComplete' and (e.get('responseStatus') or {}).get('code') == 403:
        print(f'  403:user={e["user"]["username"]};impersonatedUser={(e.get("impersonatedUser") or {}).get("username", "-")};code={e["responseStatus"]["code"]};decision={e.get("annotations", {}).get("authorization.k8s.io/decision")};reason={e.get("annotations", {}).get("authorization.k8s.io/reason", "(空)")[:100]!r}')
k('delete', 'cm', 'c1', 'c2', '-n', NS); down('audit')
