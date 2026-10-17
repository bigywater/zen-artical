import sys, os, re, time, json, base64, secrets, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k59')
cn, dt_up = up('enc', cfg=config(workers=0)); wait_nodes_ready()
NODE = f'{cn}-control-plane'
NS = ns('k59')
def etcdctl(*a):
    return k('exec', '-n', 'kube-system', f'etcd-{cn}-control-plane', '--', 'etcdctl', '--endpoints=https://127.0.0.1:2379', '--cacert=/etc/kubernetes/pki/etcd/ca.crt', '--cert=/etc/kubernetes/pki/etcd/server.crt', '--key=/etc/kubernetes/pki/etcd/server.key', *a, raw=True)
def raw(kind, name, ns_=None):
    key = f'/registry/{kind}/{ns_ + "/" if ns_ else ""}{name}'
    rc, o = etcdctl('get', key, '-w', 'json'); return base64.b64decode(json.loads(o)['kvs'][0]['value'])
def show(label, kind, name):
    r = raw(kind, name, NS); head = r[:r.index(b':', 20) + 1] if r.startswith(b'k8s:enc:') else r[:4]
    hd = r[:44] if r.startswith(b'k8s:enc:') else r[:4]
    print(f'  {label}:etcd 值 {len(r)} 字节,开头 {hd!r};能直接找到明文 hunter2:{b"hunter2" in r}')
def ready(t=180):
    return until(lambda: k('get', '--raw', '/readyz')[1].strip() == 'ok', t, 1)
def sec(name, v='hunter2'): k('create', 'secret', 'generic', name, '-n', NS, f'--from-literal=password={v}')
K1 = base64.b64encode(secrets.token_bytes(32)).decode(); K2 = base64.b64encode(secrets.token_bytes(32)).decode()
def encconf(keys, ident=True):
    ks = ''.join(f'      - name: {n}\n        secret: {v}\n' for n, v in keys)
    return f'''apiVersion: apiserver.config.k8s.io/v1
kind: EncryptionConfiguration
resources:
- resources: [secrets]
  providers:
{('  - aescbc:\\n      keys:\\n' + ks) if keys else ''}{'  - identity: {}' + chr(10) if ident else ''}'''.replace('\\n', '\n')
def put_conf(text):
    p = KT / 'enc.yaml'; p.write_text(text); sh('docker', 'cp', str(p), f'{NODE}:/etc/kubernetes/enc/enc.yaml')
print(f'集群 {cn}(单节点,控制面),先不开启加密,写入一个 Secret 之后再给 kube-apiserver 加 --encryption-provider-config')
sec('before')
show('开启之前写入的 Secret before', 'secrets', 'before')

print('== 一:开启加密——新写入的变密文,旧的仍是明文')
sh('docker', 'exec', NODE, 'mkdir', '-p', '/etc/kubernetes/enc'); put_conf(encconf([('key1', K1)]))
rc, o = sh('docker', 'exec', NODE, 'cat', '/etc/kubernetes/manifests/kube-apiserver.yaml', raw=True); m = o
m2 = m.replace('    - kube-apiserver\n', '    - kube-apiserver\n    - --encryption-provider-config=/etc/kubernetes/enc/enc.yaml\n', 1)
m2 = m2.replace('    volumeMounts:\n', '    volumeMounts:\n    - mountPath: /etc/kubernetes/enc\n      name: enc\n      readOnly: true\n', 1)
m2 = m2.replace('  volumes:\n', '  volumes:\n  - hostPath:\n      path: /etc/kubernetes/enc\n      type: DirectoryOrCreate\n    name: enc\n', 1)
assert m2 != m
p = KT / 'kube-apiserver.yaml'; p.write_text(m2); t0 = time.time()
sh('docker', 'cp', str(p), f'{NODE}:/root/kube-apiserver.yaml'); sh('docker', 'exec', NODE, 'sh', '-c', 'cp /root/kube-apiserver.yaml /etc/kubernetes/manifests/kube-apiserver.yaml')
def restarted():
    try:
        pod = kj('get', 'pod', '-n', 'kube-system', f'kube-apiserver-{NODE}')
        st = pod['status']['containerStatuses'][0]['state'].get('running', {}).get('startedAt')
        flag = any('encryption-provider-config' in a for a in pod['spec']['containers'][0]['command'])
        return flag and st and datetime.datetime.fromisoformat(st.replace('Z', '+00:00')).timestamp() > t0 and k('get', '--raw', '/readyz')[1].strip() == 'ok'
    except Exception: return False
import datetime
v, dt = until(restarted, 180, 1); print(f'  给 kube-apiserver 静态 Pod 加上 --encryption-provider-config(AES-CBC 的 key1 + identity 兜底),等 apiserver 重启:{time.time() - t0:.0f} 秒后新的 apiserver 容器就绪')
sec('after')
show('开启之后新建的 Secret after', 'secrets', 'after')
show('开启之前建的 Secret before(没动过)', 'secrets', 'before')
print(f'  kubectl 读 before / after 都正常:{base64.b64decode(kj("get", "secret", "before", "-n", NS)["data"]["password"]).decode()} / {base64.b64decode(kj("get", "secret", "after", "-n", NS)["data"]["password"]).decode()}(apiserver 读时按前缀选解密方式)')
k('create', 'configmap', 'cm', '-n', NS, '--from-literal=password=hunter2'); r = raw('configmaps', 'cm', NS); print(f'  同时间创建的 ConfigMap:etcd 值能找到明文:{b"hunter2" in r}(配置里只列了 secrets,其他资源不加密)')

print('== 二:让旧数据也变密文——把它们读出来再写一遍')
rc, o = k('get', 'secret', 'before', '-n', NS, '-o', 'json'); v0 = json.loads(o)['metadata']['resourceVersion']
rc, o = k('get', 'secrets', '-n', NS, '-o', 'json'); rc2, o2 = k('replace', '-f', '-', input=o)
show('kubectl get secrets -o json | kubectl replace -f - 之后的 before', 'secrets', 'before')
print(f'  resourceVersion {v0} → {kj("get", "secret", "before", "-n", NS)["metadata"]["resourceVersion"]}(replace 是一次真实写入)')

print('== 三:轮换密钥——先加新 key,再换主 key,最后才能删旧 key')
def restart_apiserver():
    t0 = time.time(); cid = nx(NODE, "crictl ps --name kube-apiserver -q")[1].strip().splitlines()[0]; nx(NODE, f'crictl stop {cid}')
    def back():
        try: return k('get', '--raw', '/readyz')[1].strip() == 'ok' and nx(NODE, "crictl ps --name kube-apiserver -q")[1].strip().splitlines()[0] != cid
        except Exception: return False
    until(back, 120, 1); return time.time() - t0
def apply_conf(text, probe, wait=150):
    """写入新配置,先等 apiserver 自动重新加载(wait 秒),没生效再重启 apiserver。返回 (自动生效秒数或 None, 重启耗时或 None)"""
    put_conf(text); t0 = time.time(); v, dt = until(probe, wait, 3)
    if v: return round(dt), None
    rs = restart_apiserver(); v2, _ = until(probe, 60, 2); return None, round(rs)
def readable(name): return k('get', 'secret', name, '-n', NS, '-o', 'jsonpath={.data.password}')
cnt = [0]
def newsec_has(keyname):
    def f():
        cnt[0] += 1; n = f'rot-{cnt[0]}'; sec(n); return f':{keyname}:'.encode() in raw('secrets', n, NS)[:40]
    return f
put_conf(encconf([('key1', K1), ('key2', K2)])); time.sleep(5)
sec('rot1'); print(f'  步骤 1:配置里 key1、key2 都列出来,key1 在最前(只是让 apiserver 能解 key2):新建的 rot1 开头 {raw("secrets", "rot1", NS)[:24]!r}(仍是 key1 加密)')
auto, rs = apply_conf(encconf([('key2', K2), ('key1', K1)]), newsec_has('key2'))
print(f'  步骤 2:把 key2 放到最前并写回配置文件:{"apiserver 自动重新加载,%s 秒后新写入的 Secret 用 key2 加密" % auto if auto is not None else "150 秒内 apiserver 没有自动重新加载;重启 apiserver 之后新写入的 Secret 才用 key2" % rs}')
show('before(key1 写的)', 'secrets', 'before')
print(f'    列表里还保留着 key1:before 仍能读:{base64.b64decode(readable("before")[1]).decode()!r}')
auto, rs = apply_conf(encconf([('key2', K2)]), lambda: readable('before')[0] != 0)
rc, o = readable('before'); print(f'  步骤 3(错误示范):在重写旧数据之前就把 key1 从配置里删掉({"自动重新加载,%s 秒后生效" % auto if auto is not None else "需要重启 apiserver 才生效"}):读 before → 退出码 {rc};{o.strip()[:220]}')
rc, o = readable('rot1'); print(f'    key1 写的 rot1 同样读不出来:退出码 {rc};key2 写的最新一个 Secret 仍可读:退出码 {readable(f"rot-{cnt[0]}")[0]}')
rc, o = k('get', 'secrets', '-n', NS); print(f'    kubectl get secrets -n {NS}(列表里有读不出来的对象):退出码 {rc};{o.strip().splitlines()[-1][:200]}')
auto, rs = apply_conf(encconf([('key2', K2), ('key1', K1)]), lambda: readable('before')[0] == 0)
print(f'  把 key1 加回去({"自动重新加载,%s 秒后" % auto if auto is not None else "重启 apiserver 之后"})读 before:{base64.b64decode(readable("before")[1]).decode()!r}(数据没丢,只是暂时解不开)')
k('get', 'secrets', '-n', NS, '-o', 'json'); rc, o = k('get', 'secrets', '-n', NS, '-o', 'json'); rc2, o2 = k('replace', '-f', '-', input=o)
show('把所有 Secret 重写一遍之后的 before', 'secrets', 'before'); print(f'    现在 before 的前缀是 key2:{b":key2:" in raw("secrets", "before", NS)[:40]},可以放心从配置里删掉 key1')
k('delete', 'ns', NS, '--wait=false')
