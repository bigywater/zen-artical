import sys, os, re, time, json, threading, yaml; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k12')
cn, _ = up('main')
NS = ns('k12')
FIN = 'example.com/block'
def mk(name, fins=(FIN,)):
    y = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': name, 'namespace': NS, 'finalizers': list(fins)}, 'data': {'v': '1'}}
    return k('create', '-f', '-', input=yaml.dump(y))
meta = lambda n: (kj('get', 'cm', n, '-n', NS) or {}).get('metadata', {})
print(f'集群 {cn};用 ConfigMap 演示:metadata.finalizers 里写了 {FIN} 的对象,删除请求不会立刻删掉它')

print('== 一:对带 finalizer 的对象执行删除——它还在,只是被标记为“正在删除”')
mk('a')
t0 = time.time(); rc, o = k('delete', 'cm', 'a', '-n', NS, '--wait=false'); dt = time.time() - t0
print(f'  kubectl delete cm a --wait=false:退出码 {rc};{o.strip()};耗时 {dt*1000:.0f} ms')
m = meta('a')
print(f'  之后 kubectl get cm a 仍然能读到;deletionTimestamp={m.get("deletionTimestamp")} deletionGracePeriodSeconds={m.get("deletionGracePeriodSeconds")} finalizers={m.get("finalizers")}')
print(f'  data 还在:{ko("get", "cm", "a", "-n", NS, "-o", "jsonpath={.data}")}')

print('== 二:“正在删除”的对象还能做什么')
rc, o = k('patch', 'cm', 'a', '-n', NS, '--type=merge', '-p', '{"data":{"v":"2"}}'); print(f'  改 data:退出码 {rc};{o.strip()};data={ko("get", "cm", "a", "-n", NS, "-o", "jsonpath={.data}")}')
rc, o = k('patch', 'cm', 'a', '-n', NS, '--type=merge', '-p', '{"metadata":{"finalizers":["example.com/block","example.com/another"]}}'); print(f'  再加一个 finalizer:退出码 {rc};{re.sub(r"^.*is invalid: ", "", o.strip())[:200]}')
ts0 = meta('a').get('deletionTimestamp')
k('delete', 'cm', 'a', '-n', NS, '--wait=false'); ts1 = meta('a').get('deletionTimestamp')
print(f'  再删一次:deletionTimestamp {ts0} → {ts1}(没有变化:{ts0 == ts1})')
rc, o = k('patch', 'cm', 'a', '-n', NS, '--type=json', '-p', '[{"op":"remove","path":"/metadata/deletionTimestamp"}]'); print(f'  想撤销删除(删掉 deletionTimestamp):退出码 {rc};{o.strip()[:140]}')
rc, o = k('create', 'cm', 'a', '-n', NS, '--from-literal=v=3'); print(f'  同名重建:{o.strip()}')

print('== 三:移除 finalizer 之后对象才真正消失——kubectl delete 默认会一直等')
mk('b')
def controller():
    time.sleep(4)
    k('patch', 'cm', 'b', '-n', NS, '--type=merge', '-p', '{"metadata":{"finalizers":null}}')
th = threading.Thread(target=controller); th.start()
t0 = time.time(); rc, o = k('delete', 'cm', 'b', '-n', NS, timeout=60); dt = time.time() - t0; th.join()
print(f'  kubectl delete cm b(默认 --wait=true),4 秒后由“控制器”摘掉 finalizer:退出码 {rc};{o.strip()};总共等了 {dt:.1f} 秒')
print(f'  kubectl get cm b:{k("get", "cm", "b", "-n", NS)[1].strip()}')
mk('c', fins=(FIN, 'example.com/second'))
k('delete', 'cm', 'c', '-n', NS, '--wait=false')
k('patch', 'cm', 'c', '-n', NS, '--type=json', '-p', '[{"op":"remove","path":"/metadata/finalizers/0"}]')
print(f'  有两个 finalizer 时只摘掉一个:对象还在吗 {bool(meta("c"))};剩下 {meta("c").get("finalizers")}')
k('patch', 'cm', 'c', '-n', NS, '--type=json', '-p', '[{"op":"remove","path":"/metadata/finalizers/0"}]')
print(f'  再摘掉最后一个:对象还在吗 {bool(meta("c"))}')

print('== 四:内置的 finalizer——PVC 被 Pod 使用时删不掉')
k('apply', '-f', '-', input=f'''apiVersion: v1
kind: PersistentVolumeClaim
metadata: {{name: data, namespace: {NS}}}
spec: {{accessModes: [ReadWriteOnce], resources: {{requests: {{storage: 10Mi}}}}}}
---
apiVersion: v1
kind: Pod
metadata: {{name: user, namespace: {NS}}}
spec:
  terminationGracePeriodSeconds: 0
  containers: [{{name: c, image: busybox:1.36, command: [sleep, "3600"], volumeMounts: [{{name: d, mountPath: /d}}]}}]
  volumes: [{{name: d, persistentVolumeClaim: {{claimName: data}}}}]
''')
v, dt = until(lambda: ko('get', 'pod', 'user', '-n', NS, '-o', 'jsonpath={.status.phase}') == 'Running', 90)
pv = lambda: kj('get', 'pvc', 'data', '-n', NS)
print(f'  Pod user 已经 Running、PVC data 已经被它使用:phase={pv()["status"]["phase"]} finalizers={pv()["metadata"].get("finalizers")}')
k('delete', 'pvc', 'data', '-n', NS, '--wait=false')
p = pv(); print(f'  kubectl delete pvc data 之后:仍然存在,phase={p["status"]["phase"]} deletionTimestamp={"有" if p["metadata"].get("deletionTimestamp") else "无"} finalizers={p["metadata"].get("finalizers")}')
t0 = time.time(); k('delete', 'pod', 'user', '-n', NS, '--wait=true', timeout=60)
v, dt2 = until(lambda: not pv(), 30)
print(f'  删除用它的 Pod 之后:PVC {"消失了" if v else "还在"}(Pod 删除完成后又过了约 {dt2:.1f} 秒)')
k('patch', 'cm', 'a', '-n', NS, '--type=merge', '-p', '{"metadata":{"finalizers":null}}')   # 收尾:摘掉实验里故意留下的 finalizer,否则命名空间会卡在 Terminating
rmns(NS)
