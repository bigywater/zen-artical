import sys, os, re, time, json, yaml, base64; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k19')
cn, _ = up('main')
NS = ns('k19')
SAD = '/var/run/secrets/kubernetes.io/serviceaccount'
def pod(name, extra_spec='', vol=''):
    return f'''apiVersion: v1
kind: Pod
metadata: {{name: {name}, namespace: {NS}}}
spec:
  terminationGracePeriodSeconds: 0
{extra_spec}  containers: [{{name: c, image: busybox:1.36, command: [sleep, "3600"]{vol}}}]
'''
def ready(n): return until(lambda: ko('get', 'pod', n, '-n', NS, '-o', 'jsonpath={.status.phase}') == 'Running', 90)
def tokfile(n, path=SAD + '/token'): return ko('exec', n, '-n', NS, '--', 'cat', path)
print(f'集群 {cn};Pod 里的令牌:自动挂载的 kube-api-access-xxxxx 是一个 projected 卷,令牌由 kubelet 通过 TokenRequest 取来,绑定到这个 Pod')
k('apply', '-f', '-', input=pod('app')); ready('app')

print('== 一:Pod 里那个令牌的内容——解开 JWT')
t1 = tokfile('app'); c1 = jwt_claims(t1)
kc = c1['kubernetes.io']
fl_ = ko('get', 'pod', f'kube-apiserver-{cn}-control-plane', '-n', 'kube-system', '-o', 'jsonpath={.spec.containers[0].command}')
sa_flags = [x for x in json.loads(fl_) if 'service-account' in x]
print(f'  kube-apiserver 启动参数里与 ServiceAccount 有关的:{sa_flags}(没有设置 --service-account-extend-token-expiration 和 --service-account-max-token-expiration,用默认值)')
print(f'  卷里的文件:' + ko('exec', 'app', '-n', NS, '--', 'ls', '-la', SAD).replace('\n', ' | ')[:330])
print(f'  claims:iss={c1["iss"]};aud={c1["aud"]};sub={c1["sub"]}')
print(f'    iat→exp 有效期 {c1["exp"] - c1["iat"]} 秒({(c1["exp"] - c1["iat"]) / 86400:.0f} 天),而卷里声明的 expirationSeconds=3607(kubelet 按它的 80% 刷新);nbf-iat={c1["nbf"] - c1["iat"]}')
print(f'    kubernetes.io 里:namespace={kc["namespace"]};serviceaccount={kc["serviceaccount"]["name"]};pod={kc["pod"]["name"]};node={kc["node"]["name"]};有 jti:{"jti" in c1}')
st, ui = whoami(t1); print(f'  拿这个令牌调用 SelfSubjectReview:HTTP {st};username={ui["username"]};groups={ui["groups"]};extra 里的键:{sorted(ui.get("extra", {}))}')

print('== 二:没有令牌的世界——不会再自动生成长期有效的 Secret 令牌;手工建的 Secret 令牌是另一种东西')
print(f'  kubectl get secret -n {NS}(只有一个默认 SA 在用,Pod 已 Running):{k("get", "secret", "-n", NS)[1].strip()}')
k('apply', '-f', '-', input=f'apiVersion: v1\nkind: Secret\nmetadata:\n  name: legacy\n  namespace: {NS}\n  annotations: {{kubernetes.io/service-account.name: default}}\ntype: kubernetes.io/service-account-token\n')
v, dt = until(lambda: ko('get', 'secret', 'legacy', '-n', NS, '-o', 'jsonpath={.data.token}'), 20, 0.2)
lt = base64.b64decode(v).decode() if v else ''
lc = jwt_claims(lt)
print(f'  手工创建 type=kubernetes.io/service-account-token 的 Secret 后 {dt:.1f} 秒,token 控制器填上了令牌;claims 的键:{sorted(lc)}')
print(f'    有 exp 吗:{"exp" in lc};kubernetes.io/serviceaccount/secret.name={lc.get("kubernetes.io/serviceaccount/secret.name")};有 Pod 或 Node 绑定吗:{"pod" in lc.get("kubernetes.io", {})}')
st, ui = whoami(lt); print(f'    用它调用:HTTP {st};username={ui["username"] if isinstance(ui, dict) else ui}')
k('delete', 'secret', 'legacy', '-n', NS)
t0 = time.time(); last_ok = None; st = None
while time.time() - t0 < 60:
    st, _ = whoami(lt)
    if st == 201: last_ok = time.time() - t0
    else: break
    time.sleep(1)
print(f'    删掉这个 Secret 之后:同一个令牌在 {last_ok:.0f} 秒内仍通过认证,第 {time.time() - t0:.0f} 秒起 HTTP {st}(旧式令牌依赖对应的 Secret 存在,但认证结果有短暂缓存)')

print('== 三:不要令牌——automountServiceAccountToken')
k('create', 'sa', 'nomount', '-n', NS); k('patch', 'sa', 'nomount', '-n', NS, '-p', '{"automountServiceAccountToken":false}')
k('apply', '-f', '-', input=pod('p-sa-off', '  serviceAccountName: nomount\n')); ready('p-sa-off')
k('apply', '-f', '-', input=pod('p-pod-off', '  automountServiceAccountToken: false\n')); ready('p-pod-off')
k('apply', '-f', '-', input=pod('p-override', '  serviceAccountName: nomount\n  automountServiceAccountToken: true\n')); ready('p-override')
for n, d in (('app', '默认 SA,什么都没设'), ('p-sa-off', 'SA 上设了 automountServiceAccountToken: false'), ('p-pod-off', 'Pod 上设了 false'), ('p-override', 'SA 为 false、Pod 上设为 true')):
    rc, o = k('exec', n, '-n', NS, '--', 'ls', SAD); print(f'  {n}({d}):' + o.strip().replace('\n', ' '))
    vols = [v for v in (kj('get', 'pod', n, '-n', NS)['spec'].get('volumes') or [])]
    print(f'    spec.volumes 里的名字:{[v["name"] for v in vols]}')

print('== 四:令牌是会换的——kubelet 在有效期用掉 80% 时刷新(用最短的 600 秒有效期观察)')
k('apply', '-f', '-', input=pod('rot', '', ', volumeMounts: [{name: t, mountPath: /tok}]').replace('containers:', 'volumes:\n  - name: t\n    projected:\n      sources:\n      - serviceAccountToken: {path: token, expirationSeconds: 600, audience: rotate-test}\n  containers:')); ready('rot')
seen = []; t0 = time.time()
while time.time() - t0 < 560:
    try:
        c = jwt_claims(tokfile('rot', '/tok/token'))
        if not seen or seen[-1][1] != c['iat']: seen.append((time.time() - t0, c['iat'], c['exp'], ko('exec', 'rot', '-n', NS, '--', 'readlink', '/tok/..data')))
    except Exception: pass
    time.sleep(10)
print(f'  Pod rot 里 projected 令牌设 expirationSeconds=600、audience=rotate-test;每 10 秒读一次文件,共观察 {time.time() - t0:.0f} 秒,令牌(按 iat 区分)出现了 {len(seen)} 个版本:')
for i, (t, iat, exp, link) in enumerate(seen): print(f'    第 {t:>4.0f} 秒:iat={iat} exp={exp}(有效期 {exp - iat} 秒);..data → {link}')
if len(seen) > 1: print(f'  第二个令牌出现在第 {seen[1][0]:.0f} 秒,约为 600 秒有效期的 {seen[1][0] / 600 * 100:.0f}%')
k('delete', 'pod', 'app', 'rot', 'p-sa-off', 'p-pod-off', 'p-override', '-n', NS, '--wait=false'); rmns(NS)
