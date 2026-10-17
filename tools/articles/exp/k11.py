import sys, os, re, time, json, yaml; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k11')
cn, _ = up('main')
NS = ns('k11')
LA = 'kubectl.kubernetes.io/last-applied-configuration'
def cm(data, name='cfg', extra=None):
    d = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': name, 'namespace': NS}, 'data': data}
    if extra: d['metadata'].update(extra)
    return yaml.dump(d)
def live(name='cfg'): return json.loads(ko('get', 'cm', name, '-n', NS, '-o', 'jsonpath={.data}') or '{}')
def last(name='cfg'):
    a = ko('get', 'cm', name, '-n', NS, '-o', 'json'); j = json.loads(a)['metadata'].get('annotations', {}).get(LA)
    return json.loads(j).get('data') if j else None
print(f'集群 {cn};客户端 apply(kubectl apply)靠 metadata.annotations 里的 {LA} 做“三方合并”')

print('== 一:三个输入——上次 apply 的、这次的、集群里现在的')
rc, o = k('apply', '-f', '-', input=cm({'a': '1', 'b': '2'})); print(f'  第一次 apply {{a: 1, b: 2}}:{o.strip()}')
print(f'  last-applied 注解里的 data:{last()};集群里:{live()}')
k('patch', 'cm', 'cfg', '-n', NS, '--type=merge', '-p', '{"data":{"c":"3","a":"hand-edited"}}')
print(f'  有人手工 patch 了 {{c: 3, a: hand-edited}} 之后:集群里 {live()};last-applied 仍是 {last()}')
rc, o = k('apply', '-f', '-', input=cm({'a': '10'})); print(f'  再 apply {{a: 10}}(去掉了 b):{o.strip()}')
print(f'  结果:集群里 {live()};last-applied 现在是 {last()}')
print('    解读:a 被改成 10(新的赢);b 在上次 apply 里有、这次没有 → 被删除;c 不在任何一次 apply 里 → 保留')

print('== 二:没有 last-applied 注解的对象(kubectl create 出来的)')
k('create', '-f', '-', input=cm({'x': '1', 'k2': '2'}, 'made'))
print(f'  kubectl create 出来的 made:last-applied={last("made")}')
rc, o = k('apply', '-f', '-', input=cm({'x': '1'}, 'made')); print(f'  去掉 k2 再 apply:退出码 {rc};{o.strip()[:200].replace(chr(10), " | ")}')
print(f'  结果:集群里 {live("made")}(k2 没有被删,因为没有“上次”可比);last-applied 现在是 {last("made")}')

print('== 三:--server-side 不用这个注解')
rc, o = k('apply', '--server-side', '-f', '-', input=cm({'p': '1'}, 'ss')); print(f'  server-side apply:{o.strip()};last-applied 注解:{last("ss")}')

print('== 四:注解有大小上限——大的 ConfigMap 能 create,却 apply 不了')
big = {'blob': 'x' * 270000}
rc, o = k('create', '-f', '-', input=cm(big, 'big')); print(f'  kubectl create 一个 data 约 270000 字节的 ConfigMap:退出码 {rc};{o.strip()[:100]}')
rc, o = k('apply', '-f', '-', input=cm(big, 'big2')); print(f'  kubectl apply 同样大小:退出码 {rc};{re.sub(r"x{50,}", "x…", o.strip())[:300]}')
rc, o = k('apply', '--server-side', '-f', '-', input=cm(big, 'big3')); print(f'  kubectl apply --server-side 同样大小:退出码 {rc};{o.strip()[:100]}')
rmns(NS)
