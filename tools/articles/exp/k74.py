import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k74')
cn, _ = up('main'); wait_nodes_ready()
load('busybox:1.36')
W = 'kx-main-worker'; CP = 'kx-main-control-plane'
def cr(node, c): return nx(node, c)[1].strip()
nx(W, 'rm -f /etc/kubernetes/manifests/hello.yaml /etc/kubernetes/manifests/bad.yaml'); until(lambda: not kj('get', 'pods', '-n', 'default', '-l', 'app=hello-static')['items'], 60, 0.5); time.sleep(2)
print(f'集群 {cn};静态 Pod 由节点上的 kubelet 直接从本地文件创建,不经过调度器,API Server 里只有一个只读的“镜像 Pod”(mirror pod)')

print('== 一:控制面组件就是静态 Pod')
print(f'  kubelet 配置 staticPodPath:{cr(CP, "grep staticPodPath /var/lib/kubelet/config.yaml")}')
print(f'  控制面节点 /etc/kubernetes/manifests/:{cr(CP, "ls /etc/kubernetes/manifests/").split()}')
print(f'  worker 节点 /etc/kubernetes/manifests/:{cr(W, "ls /etc/kubernetes/manifests/ 2>&1").split() or "(空)"}')
pods = kj('get', 'pods', '-n', 'kube-system')['items']; static = [p['metadata']['name'] for p in pods if p['metadata'].get('annotations', {}).get('kubernetes.io/config.source') == 'file']
print(f'  kube-system 里 config.source=file 的 Pod:{static}')
p = kj('get', 'pod', f'kube-apiserver-{CP}', '-n', 'kube-system'); md = p['metadata']
print(f'  kube-apiserver-{CP} 的元数据:annotations 里 config.source={md["annotations"].get("kubernetes.io/config.source")},config.mirror=<hash>:{"kubernetes.io/config.mirror" in md["annotations"]};ownerReferences={[(o["kind"], o["name"]) for o in md.get("ownerReferences", [])]};spec.nodeName={p["spec"]["nodeName"]}')

print('== 二:往 worker 的目录里放一个文件')
MAN = '''apiVersion: v1
kind: Pod
metadata: {name: hello-static, namespace: default, labels: {app: hello-static}}
spec:
  terminationGracePeriodSeconds: 0
  containers:
  - {name: c, image: busybox:1.36, command: [sh, -c, "echo v1; sleep 3600"], imagePullPolicy: IfNotPresent}
'''
nx(W, f"cat > /etc/kubernetes/manifests/hello.yaml <<'EOF'\n{MAN}EOF"); t0 = time.time()
v, dt = until(lambda: kj('get', 'pod', f'hello-static-{W}', '-n', 'default')['status'].get('phase') == 'Running', 90, 0.5)
mp = kj('get', 'pod', f'hello-static-{W}', '-n', 'default')
print(f'  放入 hello.yaml 后 {dt:.1f} 秒,API 里出现镜像 Pod {mp["metadata"]["name"]}(名字 = 文件里的 name + "-" + 节点名),phase=Running;uid={mp["metadata"]["uid"][:8]}…')
print(f'  它的 ownerReferences={[(o["kind"], o["name"]) for o in mp["metadata"].get("ownerReferences", [])]};annotations 里 config.source={mp["metadata"]["annotations"].get("kubernetes.io/config.source")};tolerations={[ (t.get("key"), t.get("operator"), t.get("effect")) for t in mp["spec"].get("tolerations", [])][:2]}')
uid1 = mp['metadata']['uid']
k('delete', 'pod', f'hello-static-{W}', '-n', 'default', '--wait=true', timeout=60)
t0 = time.time(); v, dt = until(lambda: (kj('get', 'pod', f'hello-static-{W}', '-n', 'default') or {'metadata': {'uid': uid1}})['metadata']['uid'] != uid1, 300, 1)
c = cr(W, "crictl ps --name '^c$' -q | wc -l")
print(f'  kubectl delete 掉这个镜像 Pod:{dt:.0f} 秒后又出现了(新的镜像 Pod uid={((kj("get", "pod", f"hello-static-{W}", "-n", "default") or {}).get("metadata", {}).get("uid") or "?")[:8]}…;kubelet 周期性发现缺少镜像 Pod 并重建);节点上的容器一直在跑(crictl ps 里 {c} 个)——删的只是 API 里的影子')

print('== 三:改文件 = 重建;删文件 = 删除')
nx(W, "sed -i 's/echo v1/echo v2/' /etc/kubernetes/manifests/hello.yaml"); t0 = time.time()
v, dt = until(lambda: 'echo v2' in json.dumps(kj('get', 'pod', f'hello-static-{W}', '-n', 'default')['spec']['containers'][0]['command']), 60, 0.3)
mp2 = kj('get', 'pod', f'hello-static-{W}', '-n', 'default'); v2, dt2 = until(lambda: kj('get', 'pod', f'hello-static-{W}', '-n', 'default')['status'].get('phase') == 'Running', 60, 0.3)
print(f'  把 echo v1 改成 echo v2:{dt:.1f} 秒后 API 里的 Pod spec 已是 v2;{dt2:.1f} 秒内重新 Running;restartCount={mp2["status"].get("containerStatuses", [{}])[0].get("restartCount")}')
t0 = time.time(); nx(W, 'rm /etc/kubernetes/manifests/hello.yaml')
def gone():
    rc, o = k('get', 'pod', f'hello-static-{W}', '-n', 'default'); return rc != 0
v, dt = until(gone, 60, 0.3); print(f'  删除 hello.yaml 后 {dt:.1f} 秒,镜像 Pod 从 API 消失;节点上容器 {cr(W, "crictl ps --name ^c$ -q | wc -l")} 个')

print('== 四:静态 Pod 不能引用 API 对象')
MAN2 = MAN.replace('hello-static', 'bad-static').replace('imagePullPolicy: IfNotPresent}', 'imagePullPolicy: IfNotPresent, envFrom: [{configMapRef: {name: nothing}}]}')
nx(W, f"cat > /etc/kubernetes/manifests/bad.yaml <<'EOF'\n{MAN2}EOF"); time.sleep(10)
rc, o = k('get', 'pod', f'bad-static-{W}', '-n', 'default'); print(f'  静态 Pod 的容器里引用 ConfigMap(envFrom.configMapRef):kubectl get 退出码 {rc};{o.strip().splitlines()[-1][:120] if rc == 0 else o.strip()[:120]}')
rc, o = nx(W, "journalctl -u kubelet --no-pager --since '-30s' 2>&1 | grep -i 'bad.yaml' | grep -i 'may not' | head -2 | cut -c1-400"); print(f'  kubelet 日志:{[x[x.index("err="):][:200] for x in o.strip().splitlines()[:1]] or "(没有找到相关日志)"}')
rc, o = nx(W, "crictl pods --name bad-static -q | wc -l"); print(f'  节点上有 bad-static 的沙箱吗:{o.strip()} 个')
nx(W, 'rm -f /etc/kubernetes/manifests/bad.yaml'); time.sleep(3)
