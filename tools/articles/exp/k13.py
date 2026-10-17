import sys, os, re, time, json, threading, yaml; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k13')
cn, _ = up('main')
NS = ns('k13'); NS2 = ns('k13-other')
def mk(name, owner=None, uid=None, block=True, fins=(), ns_=None, extra_owner_ns=None):
    md = {'name': name, 'namespace': ns_ or NS}
    if owner: md['ownerReferences'] = [{'apiVersion': 'v1', 'kind': 'ConfigMap', 'name': owner, 'uid': uid, 'blockOwnerDeletion': block}]
    if fins: md['finalizers'] = list(fins)
    return k('create', '-f', '-', input=yaml.dump({'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': md, 'data': {'v': '1'}}))
uid = lambda n, ns_=None: ko('get', 'cm', n, '-n', ns_ or NS, '-o', 'jsonpath={.metadata.uid}')
exists = lambda n, ns_=None: bool(ko('get', 'cm', n, '-n', ns_ or NS, '-o', 'name'))
def gone_after(n, ns_=None, timeout=30):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if not exists(n, ns_): return time.time() - t0
        time.sleep(0.05)
    return None
print(f'集群 {cn};用 ConfigMap 做“所有者—从属”:从属对象的 metadata.ownerReferences 指向所有者的 uid;垃圾回收器(在 kube-controller-manager 里)据此级联删除')

print('== 一:--cascade=background(默认)——所有者立刻没了,从属稍后被垃圾回收器删掉')
mk('owner1'); mk('child1', 'owner1', uid('owner1')); mk('child1b', 'owner1', uid('owner1'))
t0 = time.time(); rc, o = k('delete', 'cm', 'owner1', '-n', NS, '--cascade=background'); dt = time.time() - t0
print(f'  kubectl delete cm owner1 --cascade=background:{o.strip()};耗时 {dt*1000:.0f} ms;owner1 还在吗:{exists("owner1")}')
g1, g2 = gone_after('child1'), gone_after('child1b')
print(f'  从属 child1、child1b 分别在 {g1*1000:.0f} ms、{g2*1000:.0f} ms 后消失' if g1 is not None and g2 is not None else '  从属没有消失')

print('== 二:--cascade=foreground——所有者先被标记删除,等 blockOwnerDeletion 的从属都没了才消失')
mk('owner2'); u = uid('owner2')
mk('slow', 'owner2', u, block=True, fins=('example.com/slow',)); mk('fast', 'owner2', u, block=True); mk('noblock', 'owner2', u, block=False, fins=('example.com/slow',))
t0 = time.time(); k('delete', 'cm', 'owner2', '-n', NS, '--cascade=foreground', '--wait=false')
time.sleep(1.5)
m = (kj('get', 'cm', 'owner2', '-n', NS) or {}).get('metadata', {})
print(f'  1.5 秒后:owner2 还在吗 {exists("owner2")};deletionTimestamp={"有" if m.get("deletionTimestamp") else "无"};finalizers={m.get("finalizers")}')
print(f'  从属:fast(blockOwnerDeletion=true,无 finalizer)还在吗 {exists("fast")};slow(blockOwnerDeletion=true,带 finalizer)还在吗 {exists("slow")};noblock(blockOwnerDeletion=false,带 finalizer)还在吗 {exists("noblock")}')
t0 = time.time(); k('patch', 'cm', 'slow', '-n', NS, '--type=merge', '-p', '{"metadata":{"finalizers":null}}')
g = gone_after('owner2'); print(f'  只摘掉 slow(blockOwnerDeletion=true)的 finalizer:owner2 在 {g*1000:.0f} ms 后消失;此时 noblock(blockOwnerDeletion=false,finalizer 还在)还在吗 {exists("noblock")}' if g is not None else '  owner2 没有消失')
k('patch', 'cm', 'noblock', '-n', NS, '--type=merge', '-p', '{"metadata":{"finalizers":null}}')

print('== 三:--cascade=orphan——从属留下来,ownerReferences 被摘掉')
mk('owner3'); mk('child3', 'owner3', uid('owner3'))
print(f'  删除前 child3 的 ownerReferences:{json.dumps(kj("get", "cm", "child3", "-n", NS)["metadata"].get("ownerReferences"), ensure_ascii=False)}')
rc, o = k('delete', 'cm', 'owner3', '-n', NS, '--cascade=orphan'); print(f'  kubectl delete cm owner3 --cascade=orphan:{o.strip()}')
time.sleep(2)
print(f'  之后 child3 还在吗 {exists("child3")};ownerReferences={kj("get", "cm", "child3", "-n", NS)["metadata"].get("ownerReferences")}')

print('== 四:所有者找不到时——没有这个所有者,或者所有者在别的命名空间')
mk('ghost', 'nobody', '00000000-0000-0000-0000-000000000000')
g = gone_after('ghost', timeout=40); print(f'  ownerReferences 指向不存在的所有者(随便写的 uid):从属 ghost {"在 %.0f 毫秒后被垃圾回收器删掉" % (g * 1000) if g is not None else "40 秒内没有被删"}')
mk('owner4', ns_=NS2); u4 = uid('owner4', NS2); mk('child4', 'owner4', u4)    # child4 在 k13,所有者在 k13-other
g = gone_after('child4', timeout=40); print(f'  所有者 owner4 在 k13-other 里真实存在,从属 child4 在 k13:{"在 %.0f 毫秒后被删掉" % (g * 1000) if g is not None else "40 秒内没有被删"}(跨命名空间的 ownerReferences 不被支持,所有者按“不存在”处理)')
rc, o = k('get', 'events', '-n', NS, '--field-selector', 'involvedObject.name=child4', '-o', 'custom-columns=REASON:.reason,MESSAGE:.message', raw=False)
print('  相关事件:' + ' | '.join(l.strip()[:190] for l in o.splitlines()[:3]))
rmns(NS); rmns(NS2)
