import sys, os, re, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
import kweb
tee('k2')
cn, _ = up('main')
for n in ('k2', 'k2-app', 'k2-other'): ns(n)
k('label', 'ns', 'k2-app', 'k2-test=true', '--overwrite')
ca = kweb.deploy('hook', 'k2')
print(f'集群 {cn};webhook 服务 hook.k2.svc(python 标准库 HTTPS 服务,按路径决定行为,每个请求一行 JSON 日志);只对带 k2-test=true 标签的命名空间 k2-app 生效')


def wh(kind, cfg, hook, path, policy='Fail', timeout=10, ops='["CREATE","UPDATE"]', extra=''):
    y = f'''
apiVersion: admissionregistration.k8s.io/v1
kind: {kind}WebhookConfiguration
metadata: {{name: {cfg}}}
webhooks:
- name: {hook}.k2.example.com
  admissionReviewVersions: ["v1"]
  sideEffects: None
  failurePolicy: {policy}
  timeoutSeconds: {timeout}
  namespaceSelector: {{matchLabels: {{k2-test: "true"}}}}
  rules: [{{apiGroups: [""], apiVersions: ["v1"], operations: {ops}, resources: ["configmaps"]}}]
{extra}
  clientConfig:
    caBundle: {ca}
    service: {{namespace: k2, name: hook, path: {path}}}
'''
    rc, o = apply(y); assert rc == 0, o


def nlog(): return len(kweb.hook_logs('hook', 'k2'))
def newlogs(n0): return kweb.hook_logs('hook', 'k2')[n0:]
def cm(name, ns_='k2-app', labels=''):
    return f'apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: {name}\n  namespace: {ns_}\n' + (f'  labels: {{{labels}}}\n' if labels else '') + 'data: {a: "1"}\n'
def timed_create(y, *extra):
    t0 = time.time(); rc, o = k('create', '-f', '-', *extra, input=y); return rc, o.strip().replace('\n', ' '), time.time() - t0


print('== 一:两个变更 webhook + 一个校验 webhook:调用顺序,以及校验 webhook 看到的是变更之后的对象')
wh('Mutating', 'b-second', 'b', '/mutate/b'); wh('Mutating', 'a-first', 'a', '/mutate/a')    # 先创建 b-second,再创建 a-first
wh('Validating', 'v-check', 'v', '/validate')
time.sleep(2)
n0 = nlog(); rc, o, dt = timed_create(cm('c1'))
time.sleep(1)
ann = ko('get', 'cm', 'c1', '-n', 'k2-app', '-o', 'jsonpath={.metadata.annotations.order}')
print(f'  配置创建顺序:b-second(Mutating)→ a-first(Mutating)→ v-check(Validating);创建 ConfigMap c1:退出码 {rc},耗时 {dt*1000:.0f} ms')
for i, l in enumerate(newlogs(n0)): print(f'    webhook 收到第 {i+1} 个请求:{l["path"]:<11} 操作={l["op"]} 看到的 order 注解={l["order"]!r}')
print(f'  c1 最终的 order 注解:{ann!r}')
rc, o, dt = timed_create(cm('c2', labels='deny: "true"'))
print(f'  创建带 deny=true 的 c2:退出码 {rc};{o}')
print(f'  kubectl get cm c2:{k("get", "cm", "c2", "-n", "k2-app")[1].strip()}')

print('== 二:webhook 服务不可用时,failurePolicy 决定放行还是拒绝')
for n in ('b-second', 'a-first'): k('delete', 'mutatingwebhookconfiguration', n)
k('delete', 'validatingwebhookconfiguration', 'v-check')
res = []
wh('Validating', 'fp-fail', 'fpf', '/validate', policy='Fail', extra='  objectSelector: {matchLabels: {pol: "fail"}}')
wh('Validating', 'fp-ignore', 'fpi', '/validate', policy='Ignore', extra='  objectSelector: {matchLabels: {pol: "ignore"}}')
time.sleep(2)
rc, o, dt = timed_create(cm('p0', labels='pol: "fail"')); print(f'  服务正常,failurePolicy=Fail:退出码 {rc};耗时 {dt*1000:.0f} ms;{o}')
kweb.scale('hook', 'k2', 0); time.sleep(1)
rc, o, dt = timed_create(cm('p1', labels='pol: "fail"')); print(f'  服务停掉,failurePolicy=Fail:退出码 {rc};耗时 {dt*1000:.0f} ms;{o[:330]}')
rc, o, dt = timed_create(cm('p2', labels='pol: "ignore"')); print(f'  服务停掉,failurePolicy=Ignore:退出码 {rc};耗时 {dt*1000:.0f} ms;{o}')
print(f'  kubectl get cm -n k2-app p1 p2:' + k('get', 'cm', 'p1', 'p2', '-n', 'k2-app')[1].replace('\n', ' | '))
kweb.scale('hook', 'k2', 1)

print('== 三:webhook 处理得太慢:timeoutSeconds 与 failurePolicy(服务端每次睡 4 秒)')
for n in ('fp-fail', 'fp-ignore'): k('delete', 'validatingwebhookconfiguration', n)
wh('Validating', 't1', 't1', '/slow', policy='Fail', timeout=1, extra='  objectSelector: {matchLabels: {tm: "t1"}}')
wh('Validating', 't2', 't2', '/slow', policy='Ignore', timeout=1, extra='  objectSelector: {matchLabels: {tm: "t2"}}')
wh('Validating', 't3', 't3', '/slow', policy='Fail', timeout=10, extra='  objectSelector: {matchLabels: {tm: "t3"}}')
time.sleep(2)
for lab, name, desc in (('t1', 's1', 'timeoutSeconds=1,Fail'), ('t2', 's2', 'timeoutSeconds=1,Ignore'), ('t3', 's3', 'timeoutSeconds=10,Fail')):
    rc, o, dt = timed_create(cm(name, labels=f'tm: "{lab}"'))
    print(f'  {desc}:退出码 {rc};耗时 {dt:.2f} s;{o[:260]}')

print('== 四:哪些请求不会调用 webhook(用 webhook 服务的日志数出调用次数)')
for n in ('t1', 't2', 't3'): k('delete', 'validatingwebhookconfiguration', n)
extra = '''  objectSelector: {matchExpressions: [{key: skip, operator: DoesNotExist}]}
  matchConditions:
  - name: not-skip-prefix
    expression: '!object.metadata.name.startsWith("skip-")\''''
wh('Validating', 'v-final', 'vf', '/validate', ops='["CREATE"]', extra=extra)
time.sleep(2)
def case(label, fn):
    n0 = nlog(); fn(); time.sleep(0.8); L = newlogs(n0)
    print(f'  {label}:webhook 被调用 {len(L)} 次' + (f'(dryRun={L[0]["dry"]})' if L else ''))
case('在 k2-app 创建普通 ConfigMap(规则命中)', lambda: k('create', '-f', '-', input=cm('n1')))
case('在没有 k2-test 标签的 k2-other 创建(namespaceSelector 不命中)', lambda: k('create', '-f', '-', input=cm('n2', 'k2-other')))
case('创建带 skip 标签的对象(objectSelector 不命中)', lambda: k('create', '-f', '-', input=cm('n3', labels='skip: "1"')))
case('创建名字以 skip- 开头的对象(matchConditions 的 CEL 为 false)', lambda: k('create', '-f', '-', input=cm('skip-n4')))
case('更新已有对象 n1(规则里只有 CREATE)', lambda: k('patch', 'cm', 'n1', '-n', 'k2-app', '--type=merge', '-p', '{"data":{"a":"2"}}'))
case('--dry-run=server 创建(sideEffects: None)', lambda: k('create', '-f', '-', '--dry-run=server', input=cm('n5')))
for n in ('v-final',): k('delete', 'validatingwebhookconfiguration', n)
for n in ('k2', 'k2-app', 'k2-other'): rmns(n)
