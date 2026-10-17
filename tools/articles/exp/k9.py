import sys, os, re, time, json, yaml; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k9')
cn, _ = up('main')
NS = ns('k9')
def cm(data): return yaml.dump({'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': 'cfg', 'namespace': NS}, 'data': data})
def ssa(mgr, data, *extra):
    rc, o = k('apply', '--server-side', f'--field-manager={mgr}', '-f', '-', *extra, input=cm(data))
    return rc, o.strip()
def owners():
    j = kj('get', 'cm', 'cfg', '-n', NS, '--show-managed-fields') or {}
    r = {}
    for m in j.get('metadata', {}).get('managedFields', []):
        for f in (m.get('fieldsV1', {}).get('f:data') or {}):
            r.setdefault(f[2:], []).append(f'{m["manager"]}({m["operation"]})')
    return r
def show(label=''):
    d = ko('get', 'cm', 'cfg', '-n', NS, '-o', 'jsonpath={.data}')
    print(f'  {label}data={d};字段所有者:' + '; '.join(f'{f}→{"+".join(v)}' for f, v in sorted(owners().items())))
print(f'集群 {cn};用 ConfigMap cfg 做 Server-Side Apply:每个字段记录“谁拥有它”(metadata.managedFields)')

print('== 一:两个管理者申请同一个字段——冲突')
rc, o = ssa('team-a', {'a': '1', 'shared': 'val-x'}); print(f'  team-a 申请 {{a: 1, shared: val-x}}:退出码 {rc};{o}'); show('    ')
rc, o = ssa('team-b', {'b': '2', 'shared': 'val-y'}); print(f'  team-b 申请 {{b: 2, shared: val-y}}:退出码 {rc};')
print('    ' + o.splitlines()[0] + f'  (后面还有 {len(o.splitlines()) - 1} 行解决办法提示:--force-conflicts / 删掉这些字段 / 改成与现值一致来共同拥有)')
show('    之后 ')

print('== 二:--force-conflicts 抢走所有权;被抢的一方再申请时又会冲突')
rc, o = ssa('team-b', {'b': '2', 'shared': 'val-y'}, '--force-conflicts'); print(f'  team-b 加 --force-conflicts:退出码 {rc};{o}'); show('    ')
rc, o = ssa('team-a', {'a': '1', 'shared': 'val-x'}); print(f'  team-a 再按原样申请:退出码 {rc};' + ' | '.join(l.strip() for l in o.splitlines()[:3])[:260])
rc, o = ssa('team-a', {'a': '1', 'shared': 'val-y'}); print(f'  team-a 改成 shared: val-y(和现值相同)再申请:退出码 {rc};{o}'); show('    ')

print('== 三:共同拥有——值相同就不冲突;申请里不再写某个字段,只有“独占”的字段才会被删掉')
rc, o = ssa('team-a', {'a': '1'}); print(f'  team-a 的申请里去掉 shared:退出码 {rc};{o}'); show('    ')
rc, o = ssa('team-a', {}); print(f'  team-a 的申请里连 a 也去掉:退出码 {rc};{o}'); show('    ')
rc, o = ssa('team-b', {}); print(f'  team-b 的申请也清空:退出码 {rc};{o}'); show('    ')

print('== 四:Update 与 Apply 的冲突——kubectl scale / patch 也会成为字段所有者')
k('delete', 'deploy', 'web', '-n', NS, '--ignore-not-found')
dep = lambda r: yaml.dump({'apiVersion': 'apps/v1', 'kind': 'Deployment', 'metadata': {'name': 'web', 'namespace': NS}, 'spec': {'replicas': r, 'selector': {'matchLabels': {'app': 'web'}}, 'template': {'metadata': {'labels': {'app': 'web'}}, 'spec': {'containers': [{'name': 'c', 'image': 'busybox:1.36', 'command': ['sleep', '3600']}]}}}})
rc, o = k('apply', '--server-side', '--field-manager=deployer', '-f', '-', input=dep(1)); print(f'  deployer 申请 replicas: 1:{o.strip()}')
rc, o = k('scale', 'deploy/web', '-n', NS, '--replicas=3'); print(f'  kubectl scale 到 3:{o.strip()}')
j = kj('get', 'deploy', 'web', '-n', NS, '--show-managed-fields')
for m in j['metadata']['managedFields']:
    f = m.get('fieldsV1', {}).get('f:spec', {})
    print(f'    managedFields:manager={m["manager"]} operation={m["operation"]} subresource={m.get("subresource", "-")} 拥有 spec 下的 {sorted(x[2:] for x in f if x.startswith("f:"))}')
rc, o = k('apply', '--server-side', '--field-manager=deployer', '-f', '-', input=dep(1)); print(f'  deployer 再按 replicas: 1 申请:退出码 {rc};' + ' | '.join(l.strip() for l in o.splitlines()[:3])[:300])
rc, o = k('apply', '--server-side', '--field-manager=deployer', '-f', '-', input=dep(3)); print(f'  deployer 改成 replicas: 3(与现值相同)申请:退出码 {rc};{o.strip()}')
rmns(NS)
