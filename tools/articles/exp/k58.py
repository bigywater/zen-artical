import sys, os, re, time, json, base64, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k58')
cn, _ = up('main')
load('busybox:1.36')
NS = ns('k58')
def etcdctl(*a):
    return k('exec', '-n', 'kube-system', f'etcd-{cn}-control-plane', '--', 'etcdctl', '--endpoints=https://127.0.0.1:2379', '--cacert=/etc/kubernetes/pki/etcd/ca.crt', '--cert=/etc/kubernetes/pki/etcd/server.crt', '--key=/etc/kubernetes/pki/etcd/server.key', *a, raw=True)
print(f'集群 {cn};Secret 和 ConfigMap 在存储上几乎没有区别:data 里的值是 base64 编码(不是加密),落到 etcd 时默认也是明文')

print('== 一:base64 只是编码')
k('create', 'secret', 'generic', 'db', '-n', NS, '--from-literal=password=s3cr3t-Pa55')
d = kj('get', 'secret', 'db', '-n', NS)
print(f'  kubectl get secret db -o json 里 data.password={d["data"]["password"]!r}')
print(f'  base64 -d 之后={base64.b64decode(d["data"]["password"]).decode()!r}(任何能 get 这个 Secret 的人都能做)')
rc, o = k('describe', 'secret', 'db', '-n', NS); print('  kubectl describe secret db 的 Data 部分:' + ' | '.join(l.strip() for l in o.splitlines()[-4:] if l.strip()))
k('apply', '-f', '-', input=f'apiVersion: v1\nkind: Secret\nmetadata: {{name: sd, namespace: {NS}}}\nstringData: {{token: plain-text-in-yaml}}\n')
d = kj('get', 'secret', 'sd', '-n', NS); print(f'  用 stringData 写入明文:服务端存成 data.token={d["data"]["token"]!r}(= {base64.b64decode(d["data"]["token"]).decode()!r});返回的对象里 stringData={d.get("stringData", "(没有)")}')
k('apply', '-f', '-', input=f'apiVersion: v1\nkind: Secret\nmetadata: {{name: sd, namespace: {NS}}}\ndata: {{bad: "not base64!!"}}\n')
rc, o = k('apply', '-f', '-', input=f'apiVersion: v1\nkind: Secret\nmetadata: {{name: sd2, namespace: {NS}}}\ndata: {{bad: "not base64!!"}}\n'); print(f'  data 里写不是 base64 的值:退出码 {rc};{o.strip().splitlines()[0][:200] if o.strip() else ""}')
rc, o = k('get', 'secret', 'db', '-n', NS, '-o', 'jsonpath={.data.password}'); print(f'  Secret 有 type 字段:db 的 type={kj("get", "secret", "db", "-n", NS)["type"]}')

print('== 二:etcd 里存的是什么')
key = f'/registry/secrets/{NS}/db'
rc, o = etcdctl('get', key, '-w', 'json'); j = json.loads(o); raw = base64.b64decode(j['kvs'][0]['value'])
print(f'  etcd key {key}:值共 {len(raw)} 字节,开头 {raw[:12]!r}(k8s\\x00 是 protobuf 存储格式的魔数)')
print(f'  值里能直接找到 password 明文 s3cr3t-Pa55:{b"s3cr3t-Pa55" in raw};能找到 base64 形式 {d["data"].get("x", base64.b64encode(b"s3cr3t-Pa55").decode())}:{base64.b64encode(b"s3cr3t-Pa55") in raw}(etcd 里直接存原始字节,不再 base64)')
txt = ''.join(chr(b) if 32 <= b < 127 else '.' for b in raw); print(f'  把值里的不可见字节换成点:{txt[:130]}')
rc, o = etcdctl('get', f'/registry/configmaps/{NS}/x', '-w', 'json')
k('create', 'configmap', 'cm', '-n', NS, '--from-literal=password=s3cr3t-Pa55'); rc, o = etcdctl('get', f'/registry/configmaps/{NS}/cm', '-w', 'json'); rawc = base64.b64decode(json.loads(o)['kvs'][0]['value'])
print(f'  同样内容放进 ConfigMap:etcd 值开头 {rawc[:12]!r},也能直接找到明文:{b"s3cr3t-Pa55" in rawc}(两者存储方式一样,Secret 没有额外保护)')

print('== 三:谁能读到 Secret 的值')
k('create', 'sa', 'lister', '-n', NS); k('create', 'role', 'only-list', '-n', NS, '--verb=list', '--resource=secrets'); k('create', 'rolebinding', 'only-list', '-n', NS, '--role=only-list', f'--serviceaccount={NS}:lister')
tok = ko('create', 'token', 'lister', '-n', NS)
code, body = api('GET', f'/api/v1/namespaces/{NS}/secrets/db', tok); print(f'  只有 list 权限的 ServiceAccount:GET 单个 Secret → HTTP {code}')
code, body = api('GET', f'/api/v1/namespaces/{NS}/secrets', tok); vals = {i['metadata']['name']: base64.b64decode(i['data'].get('password', i['data'].get('token', ''))).decode() for i in body['items']}
print(f'    LIST 全部 Secret → HTTP {code};响应里带完整的 data:{vals}(list 的权限等于读全部值)')
rc, o = k('auth', 'can-i', 'get', 'secrets', '-n', NS, f'--as=system:serviceaccount:{NS}:lister'); print(f'    kubectl auth can-i get secrets --as=…lister → {o.strip()}')
rc, o = k('auth', 'can-i', 'list', 'secrets', '-n', NS, f'--as=system:serviceaccount:{NS}:lister'); print(f'    kubectl auth can-i list secrets --as=…lister → {o.strip()}')

print('== 四:挂进 Pod 之后——卷是 tmpfs,环境变量会进入进程环境')
k('apply', '-f', '-', input=f'''apiVersion: v1
kind: Pod
metadata: {{name: use, namespace: {NS}}}
spec:
  terminationGracePeriodSeconds: 0
  containers:
  - name: c
    image: busybox:1.36
    command: [sleep, "3600"]
    env: [{{name: PW, valueFrom: {{secretKeyRef: {{name: db, key: password}}}}}}]
    volumeMounts: [{{name: s, mountPath: /etc/s, readOnly: true}}]
  volumes: [{{name: s, secret: {{secretName: db}}}}]
''')
until(lambda: kj('get', 'pod', 'use', '-n', NS)['status'].get('containerStatuses', [{}])[0].get('state', {}).get('running'), 60, 0.3)
def ex(c): return k('exec', 'use', '-n', NS, '--', 'sh', '-c', c)[1].strip()
print(f'  容器里 /etc/s 的挂载:{ex("grep ' /etc/s ' /proc/mounts")}(tmpfs,不落节点磁盘)')
print(f'  /etc/s/password={ex("cat /etc/s/password")!r};环境变量 PW={ex("echo $PW")!r};/proc/1/environ 里能看到:{"PW=s3cr3t-Pa55" in ex("cat /proc/1/environ | tr '\\\\000' '\\\\n'")}')
p = kj('get', 'pod', 'use', '-n', NS); print(f'  kubectl get pod -o yaml 里 env 只写引用:{p["spec"]["containers"][0]["env"]}(值不在 Pod 对象里)')
k('delete', 'pod', 'use', '-n', NS, '--wait=true', timeout=60)
