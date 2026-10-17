import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k88')
cn, _ = up('main'); wait_nodes_ready()
NS = ns('k88')
def short(o, n=2, w=360): return [re.sub(r'\s+', ' ', l)[:w] for l in o.strip().splitlines() if l.strip()][:n]
CRD = '''apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata: {name: ranges.k88.example.com}
spec:
  group: k88.example.com
  scope: Namespaced
  names: {plural: ranges, singular: range, kind: Range}
  versions:
  - name: v1
    served: true
    storage: true
    schema:
      openAPIV3Schema:
        type: object
        properties:
          spec:
            type: object
            x-kubernetes-validations:
            - rule: "self.min <= self.max"
              message: "min 不能大于 max"
              reason: FieldValueInvalid
              fieldPath: ".max"
            - rule: "!has(self.mode) || self.mode != 'strict' || self.max <= 100"
              messageExpression: "'strict 模式下 max 不能超过 100(mode=' + self.mode + ')'"
            required: [min, max]
            properties:
              min: {type: integer}
              max: {type: integer}
              mode: {type: string, maxLength: 10}
              owner:
                type: string
                maxLength: 20
                x-kubernetes-validations:
                - rule: "self == oldSelf"
                  message: "owner 创建后不可修改"
              tier:
                type: string
                maxLength: 20
                x-kubernetes-validations:
                - rule: "oldSelf != 'prod' || self == 'prod'"
                  message: "prod 不能降级"
'''
def rng(name, **kw):
    spec = {'min': 1, 'max': 10}; spec.update(kw); return json.dumps({'apiVersion': 'k88.example.com/v1', 'kind': 'Range', 'metadata': {'name': name, 'namespace': NS}, 'spec': spec})
print(f'集群 {cn};CRD 的 OpenAPI schema 里可以写 x-kubernetes-validations:用 CEL 表达式校验字段、跨字段关系、以及更新前后的变化(self / oldSelf),在 API Server 内执行')
k('apply', '-f', '-', input=CRD); until(lambda: k('get', 'ranges.k88.example.com', '-n', NS)[0] == 0, 30, 0.5)

print('== 一:跨字段规则与消息')
rc, o = k('apply', '-f', '-', input=rng('ok')); print(f'  min=1 max=10:退出码 {rc};{short(o, 1)}')
rc, o = k('apply', '-f', '-', input=rng('bad', min=20, max=10)); print(f'  min=20 max=10:退出码 {rc};{short(o, 2, 420)}')
rc, o = k('apply', '-f', '-', input=rng('strict', mode='strict', max=500)); print(f'  mode=strict max=500(带 messageExpression 的规则):退出码 {rc};{short(o, 2, 420)}')
rc, o = k('apply', '-f', '-', input=rng('both', min=900, max=500, mode='strict')); print(f'  两条规则同时违反:{short(o, 3, 420)}')
rc, o = k('apply', '-f', '-', input=rng('nomode', max=500)); print(f'  不写 mode(规则里用 has(self.mode) 保护):退出码 {rc};{short(o, 1)}')

print('== 二:迁移规则(transition rule)——用 oldSelf 比较更新前后')
k('apply', '-f', '-', input=rng('imm', owner='alice', tier='dev')); 
rc, o = k('patch', 'ranges.k88.example.com', 'imm', '-n', NS, '--type=merge', '-p', '{"spec":{"owner":"bob"}}'); print(f'  把 owner 从 alice 改成 bob:退出码 {rc};{short(o, 1, 420)}')
rc, o = k('patch', 'ranges.k88.example.com', 'imm', '-n', NS, '--type=merge', '-p', '{"spec":{"max":20}}'); print(f'  只改 max(owner 没变):退出码 {rc};{short(o, 1)}')
rc, o = k('patch', 'ranges.k88.example.com', 'imm', '-n', NS, '--type=merge', '-p', '{"spec":{"tier":"prod"}}'); print(f'  tier dev → prod:退出码 {rc};{short(o, 1)}')
rc, o = k('patch', 'ranges.k88.example.com', 'imm', '-n', NS, '--type=merge', '-p', '{"spec":{"tier":"dev"}}'); print(f'  tier prod → dev:退出码 {rc};{short(o, 1, 420)}')
k('apply', '-f', '-', input=rng('noowner')); rc, o = k('patch', 'ranges.k88.example.com', 'noowner', '-n', NS, '--type=merge', '-p', '{"spec":{"owner":"carol"}}'); print(f'  创建时没有 owner,之后第一次设置 owner(oldSelf 不存在,规则不执行):退出码 {rc};{short(o, 1)}')

print('== 三:成本限制——没有上限的字段会让 CRD 本身被拒')
BAD = '''apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata: {name: namesets.k88.example.com}
spec:
  group: k88.example.com
  scope: Namespaced
  names: {plural: namesets, singular: nameset, kind: NameSet}
  versions:
  - name: v1
    served: true
    storage: true
    schema:
      openAPIV3Schema:
        type: object
        properties:
          spec:
            type: object
            properties:
              names:
                type: array
                items: {type: string}
                x-kubernetes-validations:
                - rule: "self.all(x, self.exists_one(y, x == y))"
                  message: "names 里有重复"
'''
rc, o = k('apply', '-f', '-', input=BAD); print(f'  list 没有 maxItems、string 没有 maxLength,规则 self.all(x, self.exists_one(y, x == y)):退出码 {rc}')
for l in short(o, 3, 520): print('    ' + l)
FIX = BAD.replace('items: {type: string}', 'maxItems: 20\n                items: {type: string, maxLength: 20}')
rc, o = k('apply', '-f', '-', input=FIX); print(f'  加上 maxItems: 20 和 maxLength: 20:退出码 {rc};{short(o, 1)}')
until(lambda: k('get', 'namesets.k88.example.com', '-n', NS)[0] == 0, 30, 0.5)
rc, o = k('apply', '-f', '-', input=json.dumps({'apiVersion': 'k88.example.com/v1', 'kind': 'NameSet', 'metadata': {'name': 'dup', 'namespace': NS}, 'spec': {'names': ['a', 'b', 'a']}})); print(f'  names: [a, b, a]:退出码 {rc};{short(o, 1, 420)}')
rc, o = k('apply', '-f', '-', input=json.dumps({'apiVersion': 'k88.example.com/v1', 'kind': 'NameSet', 'metadata': {'name': 'toolong', 'namespace': NS}, 'spec': {'names': [str(i) for i in range(25)]}})); print(f'  25 个元素(超过 maxItems 20):{short(o, 2, 360)}')
CRD2 = CRD.replace("messageExpression: \"'strict 模式下 max 不能超过 100(mode=' + self.mode + ')'\"", "messageExpression: \"'当前 max=' + string(self.max)\"").replace('name: ranges.k88.example.com', 'name: ranges2.k88.example.com').replace('plural: ranges, singular: range, kind: Range', 'plural: ranges2, singular: range2, kind: Range2')
rc, o = k('apply', '-f', '-', '--dry-run=server', input=CRD2); print(f'  另一个意外:messageExpression 里写 string(self.max)(把整数转字符串拼进消息):退出码 {rc};{short(o, 2, 330)}')
k('delete', 'crd', 'ranges.k88.example.com', 'namesets.k88.example.com', '--wait=false'); k('delete', 'ns', NS, '--wait=false')
