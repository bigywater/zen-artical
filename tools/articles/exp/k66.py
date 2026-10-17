import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k66')
def kcfg_mode(mode): return f'kind: Cluster\napiVersion: kind.x-k8s.io/v1alpha4\nnetworking:\n  kubeProxyMode: "{mode}"\nnodes:\n- role: control-plane\n- role: worker\n'
def setup(NS):
    k('apply', '-f', '-', input=f'''apiVersion: apps/v1
kind: Deployment
metadata: {{name: web, namespace: {NS}}}
spec:
  replicas: 3
  selector: {{matchLabels: {{app: web}}}}
  template:
    metadata: {{labels: {{app: web}}}}
    spec:
      terminationGracePeriodSeconds: 0
      containers:
      - name: c
        image: busybox:1.36
        command: [sh, -c, "mkdir -p /www; echo $HOSTNAME > /www/index.html; exec httpd -f -p 80 -h /www"]
        readinessProbe: {{httpGet: {{path: /, port: 80}}, periodSeconds: 1}}
---
apiVersion: v1
kind: Service
metadata: {{name: web, namespace: {NS}}}
spec: {{selector: {{app: web}}, ports: [{{port: 80}}]}}
---
apiVersion: v1
kind: Pod
metadata: {{name: cli, namespace: {NS}}}
spec:
  terminationGracePeriodSeconds: 0
  containers: [{{name: c, image: busybox:1.36, command: [sleep, "3600"]}}]
''')
    k('rollout', 'status', 'deploy/web', '-n', NS, '--timeout=120s'); until(lambda: kj('get', 'pod', 'cli', '-n', NS)['status'].get('phase') == 'Running', 60, 0.3); time.sleep(3)
    return kj('get', 'svc', 'web', '-n', NS)['spec']['clusterIP'], {p['status']['podIP']: p['metadata']['name'] for p in kj('get', 'pods', '-n', NS, '-l', 'app=web')['items']}
def spread(NS, cip, n=300):
    rc, o = k('exec', 'cli', '-n', NS, '--', 'sh', '-c', f'for i in $(seq {n}); do wget -qO- -T 2 http://{cip}:80; done | sort | uniq -c')
    return sorted(int(l.split()[0]) for l in o.strip().splitlines())
def many(NS, n):
    docs = ''.join(f'apiVersion: v1\nkind: Service\nmetadata: {{name: m{i}, namespace: {NS}}}\nspec: {{selector: {{app: web}}, ports: [{{port: 80}}]}}\n---\n' for i in range(n))
    return docs
RES = {}
def reach_time(NS, nm, t0, tmax=180):
    c = kj('get', 'svc', nm, '-n', NS)['spec']['clusterIP']; n = 0
    while time.time() - t0 < tmax:
        r = k('exec', 'cli', '-n', NS, '--', 'sh', '-c', f'wget -qO- -T 1 http://{c}:80 2>&1 | head -1')[1].strip(); n += 1
        if r.startswith('web-'): return round(time.time() - t0, 1)
        time.sleep(0.5)
    return None
def timeline(fn, target, tmax=300):
    t0 = time.time(); marks = []; nxt = 5; last = None
    while time.time() - t0 < tmax:
        c = fn(); el = time.time() - t0
        if c >= target: return round(el, 1), marks + [(round(el), c)]
        if el >= nxt: marks.append((round(el), c)); nxt += 15
        time.sleep(1)
    return None, marks + [(round(time.time() - t0), fn())]
print('kube-proxy 有三种后端:iptables(默认)、ipvs、nftables。本文用 kind 的 networking.kubeProxyMode 各起一个集群,对比同一个 Service 在内核里的样子')

print('== 一:ipvs 模式——Service 是内核 IPVS 的虚拟服务器')
cn, _ = up('ipvs', cfg=kcfg_mode('ipvs')); wait_nodes_ready(); load('busybox:1.36')
mode = k('get', 'cm', 'kube-proxy', '-n', 'kube-system', '-o', 'jsonpath={.data.config\\.conf}')[1]; MODE = re.search(r"mode: (\w+)", mode).group(1); print(f'  集群 {cn}:kube-proxy 配置 mode={MODE}')
NS = ns('k66'); cip, pods = setup(NS); W = 'kx-ipvs-worker'
hx = ''.join(f'{int(x):02X}' for x in cip.split('.')); print(f'  Service web 的 ClusterIP {cip}(十六进制 {hx}),3 个后端 Pod IP 末尾 {sorted(i.split(".", 2)[2] for i in pods)}')
rc, o = nx(W, f'cat /proc/net/ip_vs 2>&1 | grep -A3 "^TCP  {hx}:0050"'); print(f'  /proc/net/ip_vs 里这个 Service 的条目(0050 是端口 80,调度器 rr = 轮询;Masq = NAT 转发;后端地址也是十六进制):'); [print('    ' + l) for l in o.strip().splitlines() if l.strip()]
rc, o = nx(W, 'ip -4 addr show kube-ipvs0 2>&1 | grep -c "inet "'); rc2, o2 = nx(W, 'ip -d link show kube-ipvs0 2>&1 | head -3'); print(f'  节点上多了一个 dummy 网卡 kube-ipvs0,上面挂着所有 Service 的 ClusterIP:{o.strip()} 个地址;类型:{" ".join(o2.split())[:100]}')
rc, o = nx(W, 'iptables-save -t nat 2>/dev/null | grep -c KUBE-SEP'); print(f'  iptables nat 表里 KUBE-SEP 链数:{o.strip()}(ipvs 模式下 DNAT 不再靠 iptables 链)')
sp = spread(NS, cip); print(f'  300 个新连接在三个后端的分布:{sp}(IPVS 默认调度器 rr 轮询,几乎完全均匀)')
RES['ipvs_sched'] = nx(W, 'cat /proc/net/ip_vs | grep -m1 -A1 "^TCP"')[1].strip().splitlines()[0][-20:]
def ipvs_count():
    rc, o = nx(W, 'ip -4 addr show kube-ipvs0 | grep -c "inet "'); return int(o.strip() or 0)
base_ip = ipvs_count(); t0 = time.time(); k('apply', '-f', '-', input=many(NS, 300))
dt, marks = timeline(lambda: ipvs_count() - base_ip, 300); RES['ipvs_dt'] = dt
def reach(NS, names):
    out = []
    for nm in names:
        c = kj('get', 'svc', nm, '-n', NS)['spec']['clusterIP']; r = k('exec', 'cli', '-n', NS, '--', 'sh', '-c', f'wget -qO- -T 3 http://{c}:80 2>&1 | head -1')[1].strip()
        out.append((nm, 'ok' if r.startswith('web-') else r[:40]))
    return out
print(f'  再创建 300 个 Service(同一组后端),kube-ipvs0 网卡上新增的 ClusterIP 数(秒, 数量)的变化:{marks};{"全部 300 个到齐用了 %s 秒" % dt if dt else "300 秒内没有到齐"}')
rt = reach_time(NS, 'm299', t0); print(f'  最后一个 Service m299 从 apply 起到真的能访问(wget 返回后端主机名)用了 {rt} 秒')
rc, o = nx(W, 'iptables-save 2>/dev/null | wc -l'); RES['ipvs_ipt'] = int(o.strip().splitlines()[0]); print(f'  此时 iptables-save 总行数:{RES["ipvs_ipt"]}(规则数基本不随 Service 数增长)')
down('ipvs')

print('== 二:nftables 模式——一张 kube-proxy 表,Service 在 map 里')
cn, _ = up('nft', cfg=kcfg_mode('nftables')); wait_nodes_ready(); load('busybox:1.36')
mode = k('get', 'cm', 'kube-proxy', '-n', 'kube-system', '-o', 'jsonpath={.data.config\\.conf}')[1]; MODE = re.search(r"mode: (\w+)", mode).group(1); print(f'  集群 {cn}:kube-proxy 配置 mode={MODE}')
NS = ns('k66'); cip, pods = setup(NS); W = 'kx-nft-worker'
rc, o = nx(W, 'nft list tables 2>&1'); print(f'  nft list tables:{o.strip().splitlines()}')
rc, o = nx(W, 'nft list table ip kube-proxy 2>&1'); txt = o
svc_lines = [l.strip() for l in txt.splitlines() if cip in l]; print(f'  含 ClusterIP {cip} 的行:'); [print('    ' + l[:200]) for l in svc_lines]
m = re.search(r'(service-\w+-k66/web/tcp/)', txt); sc = [l for l in txt.splitlines() if 'k66/web' in l and 'chain' in l][:4]
chains = re.findall(r'chain ((?:service|endpoint)-\S*k66/web\S*) \{', txt); print(f'  和 web 有关的链:{[c[:46] for c in chains]}')
for ch in chains[:1]:
    body = re.search(rf'chain {re.escape(ch)} \{{(.*?)\n\t\}}', txt, re.S); print(f'    chain {ch[:44]}:' + ' ; '.join(x.strip()[:110] for x in body.group(1).strip().splitlines()) if body else '')
sp = spread(NS, cip); print(f'  300 个新连接在三个后端的分布:{sp}(随机)')
t0 = time.time(); k('apply', '-f', '-', input=many(NS, 300))
def nft_count():
    rc, o = nx(W, 'nft list table ip kube-proxy 2>/dev/null | grep -c "chain service-.*k66/m[0-9]*/tcp/"'); return int(o.strip() or 0)
rt = reach_time(NS, 'm299', t0)
dt, marks = timeline(nft_count, 300); rc, o = nx(W, 'nft list table ip kube-proxy 2>/dev/null | wc -l'); RES['nft_lines'] = int(o.strip().splitlines()[0]); RES['nft_dt'] = dt
print(f'  最后一个 Service m299 从 apply 起到真的能访问(wget 返回后端主机名)用了 {rt} 秒')
print(f'  再创建 300 个 Service,kube-proxy 表里新 Service 数(秒, 数量)的变化:{marks};{"全部 300 个到齐用了 %s 秒" % dt if dt else "300 秒内没有到齐"};kube-proxy 表现在共 {RES["nft_lines"]} 行')
down('nft')

print('== 三:同样 300 个 Service,iptables 模式的规则量')
cn, _ = up('main'); NS = ns('k66i'); load('busybox:1.36'); cip, pods = setup(NS); W = 'kx-main-worker'
rc, o = nx(W, 'iptables-save 2>/dev/null | wc -l'); base = int(o.strip().splitlines()[0])
t0 = time.time(); k('apply', '-f', '-', input=many(NS, 300))
def ipt_count():
    rc, o = nx(W, 'iptables-save -t nat 2>/dev/null | grep -c "k66i/m[0-9]* cluster IP"'); return int(o.strip() or 0)
rt = reach_time(NS, 'm299', t0)
dt, marks = timeline(ipt_count, 300); rc, o = nx(W, 'iptables-save 2>/dev/null | wc -l'); n1 = int(o.strip().splitlines()[0])
print(f'  iptables 模式(集群 {cn};最后一个 Service m299 从 apply 起到真的能访问用了 {rt} 秒):新 Service 入口规则数(秒, 数量)的变化:{marks};{"全部 300 个到齐用了 %s 秒" % dt if dt else "300 秒内没有到齐"};iptables-save 总行数 {base} → {n1}(+{n1 - base},约 {(n1 - base) / 300:.1f} 行/Service,每个 Service 有 3 个后端)')
print(f'  对比:ipvs 模式 iptables 总行数 {RES["ipvs_ipt"]};nftables 模式 kube-proxy 表 {RES["nft_lines"]} 行(用 map,查找不是线性的)')
k('delete', 'ns', NS, '--wait=false')
