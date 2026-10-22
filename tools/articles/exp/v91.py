import sys, os, re, time, json, shutil, pathlib, subprocess, textwrap, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('v91')
cn, _ = up('main'); load('busybox:1.36'); NS = ns('v91')
D = HERE / 'vtmp' / 'v91'; shutil.rmtree(D, ignore_errors=True); (D / 'chart/templates').mkdir(parents=True)
(D / 'chart/Chart.yaml').write_text('apiVersion: v2\nname: shop\nversion: 0.1.0\nappVersion: "1"\n')
(D / 'chart/values.yaml').write_text('replicaCount: 3\nimage: {repository: busybox, tag: "1.36"}\nlogLevel: info\n')
(D / 'chart/templates/deployment.yaml').write_text(textwrap.dedent('''
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: shop
      labels: {app: shop}
    spec:
      replicas: {{ .Values.replicaCount }}
      selector:
        matchLabels: {app: shop}
      template:
        metadata:
          labels: {app: shop}
        spec:
          containers:
          - name: app
            image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
            command: [httpd, -f, -p, "8080"]
            env: [{name: LOG_LEVEL, value: {{ .Values.logLevel | quote }}}]
            readinessProbe: {tcpSocket: {port: 8080}, periodSeconds: 1}
    ''').lstrip('\n'))
def h(*a, timeout=240):
    t = time.perf_counter(); r = subprocess.run(['helm', '--kubeconfig', kcfg(), '-n', NS, *map(str, a)], capture_output=True, text=True, cwd=D, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr).strip(), time.perf_counter() - t
def up_(*a): return h('upgrade', 'shop', 'chart', *a)
def rels():
    rc, o, _ = h('history', 'shop', '-o', 'json'); return json.loads(o) if rc == 0 else []
def hist_txt(): return '; '.join(f'rev{r["revision"]}={r["status"]}' + (f'({r["description"][:40]})' if r['description'] and 'complete' not in r['description'].lower() else '') for r in rels())
def secrets():
    j = kj('get', 'secret', '-n', NS, '-l', 'owner=helm'); return sorted(((s['metadata']['name'], len(s['data']['release'])) for s in (j or {}).get('items', [])), key=lambda x: int(x[0].rsplit('.v', 1)[1]))
def pods():
    j = kj('get', 'pod', '-n', NS, '-l', 'app=shop') or {}; c = collections.Counter()
    for p in j.get('items', []):
        cs = (p['status'].get('containerStatuses') or [{}])[0]; st = list(cs.get('state', {}).keys())[0] if cs.get('state') else '?'
        why = cs.get('state', {}).get(st, {}).get('reason', '') if st != 'running' else ''
        c[(p['spec']['containers'][0]['image'].split(':')[1], 'Ready' if cs.get('ready') else (why or st))] += 1
    return ', '.join(f'{n}×{img}({s})' for (img, s), n in sorted(c.items()))
def reset():
    h('uninstall', 'shop', '--ignore-not-found'); k('delete', 'all,cm', '-n', NS, '--all', '--wait=true', timeout=120); k('delete', 'secret', '-n', NS, '-l', 'owner=helm', '--ignore-not-found')
def replicas(): return int(ko('get', 'deploy', 'shop', '-n', NS, '-o', 'jsonpath={.spec.replicas}'))
print(f'Helm {subprocess.run(["helm", "version", "--short"], capture_output=True, text=True).stdout.strip()},集群 {cn};一个 3 副本的小应用(busybox httpd,readinessProbe 是 tcpSocket 8080),chart 在 vtmp/v91。「坏版本」= 镜像 tag 写成一个不存在的 busybox:1.36-nope(节点拉不到镜像,Pod 一直 ErrImagePull / ImagePullBackOff)')

# ============ 一 ============
print('== 一:Helm 把发布记录存在哪里。install 一次,再 upgrade 三次(改副本数、改日志级别、什么都不改),看 helm history 与集群里带 owner=helm 标签的 Secret')
reset(); rc, o, dt = h('install', 'shop', 'chart', '--wait'); print(f'  install --wait:退出码 {rc},{dt:.1f} s')
for lab, extra in (('副本数 3→4', ['--set', 'replicaCount=4']), ('日志级别 info→debug', ['--set', 'replicaCount=4', '--set', 'logLevel=debug']), ('什么都不改', ['--set', 'replicaCount=4', '--set', 'logLevel=debug'])):
    rc, o, dt = up_(*extra); print(f'  upgrade({lab}):退出码 {rc},{dt:.1f} s')
print(f'  helm history:{hist_txt()}')
print('  集群里的 Secret(名字,release 字段 base64 之后的字符数):' + '; '.join(f'{n}={b}' for n, b in secrets()))
import base64, gzip
sec = kj('get', 'secret', 'sh.helm.release.v1.shop.v4', '-n', NS); raw = base64.b64decode(base64.b64decode(sec['data']['release'])); rel = json.loads(gzip.decompress(raw))
print(f'  解开 v4 这个 Secret(base64 → base64 → gzip → JSON):解压前 {len(raw)} 字节,解压后 {len(gzip.decompress(raw))} 字节;顶层键 {sorted(rel)};info.status = {rel["info"]["status"]};manifest 字段 {len(rel["manifest"])} 个字符,config(用户给的 values)= {rel.get("config")}')
print('  每次 upgrade(包括什么都没改的那次)都会产生一个新的 revision,存成一个叫 sh.helm.release.v1.<名字>.v<编号> 的 Secret,里面是压缩过的整个 release(chart、values、渲染出的清单)')

# ============ 二 ============
print('== 二:历史会被裁剪。helm upgrade --help 里 --history-max 的默认值,以及在一个新的 release 上连续 upgrade 14 次(共 15 个 revision)后,helm history 与 Secret 里还剩几个')
rc, o, _ = h('upgrade', '--help'); print('  ' + [l.strip() for l in o.splitlines() if '--history-max' in l][0][:160])
reset(); h('install', 'shop', 'chart', '--wait')
for i in range(14): up_('--set', f'replicaCount={3 + (i % 2)}')
hs = rels(); sc = secrets(); print(f'  15 个 revision 之后:helm history 里 {len(hs)} 个(编号 {hs[0]["revision"]} 到 {hs[-1]["revision"]}),Secret {len(sc)} 个(最老的是 {sc[0][0].rsplit(".", 1)[1]})')
reset(); h('install', 'shop', 'chart', '--wait')
for i in range(5): up_('--set', f'replicaCount={3 + (i % 2)}', '--history-max', '3')
hs = rels(); print(f'  设 --history-max 3 之后连续 5 次 upgrade:helm history 里 {len(hs)} 个(编号 {hs[0]["revision"]} 到 {hs[-1]["revision"]})')
print('  默认只保留最近的 10 个 revision,更老的发布记录(和能回滚到的版本)被丢掉')

# ============ 三 ============
print('== 三:upgrade 到一个坏版本会怎样。每种情况都从一个健康的 3 副本 release(revision 1)开始,upgrade 到坏镜像。(a)默认(不加 --wait);(b)--wait --timeout 30s;(c)--rollback-on-failure --timeout 30s(Helm 4 里原来的 --atomic)')
rows = []
for lab, extra in (('(a)默认,不加 --wait', []), ('(b)--wait --timeout 30s', ['--wait', '--timeout', '30s']), ('(c)--rollback-on-failure --timeout 30s', ['--rollback-on-failure', '--timeout', '30s'])):
    reset(); h('install', 'shop', 'chart', '--wait'); rc, o, dt = up_('--set', 'image.tag=1.36-nope', *extra); time.sleep(3)
    st = [r for r in rels()][-1]['status']; rows.append((lab, rc, f'{dt:.1f}', st, hist_txt(), pods(), o.splitlines()[-1][:110] if rc else '-'))
print(table([['场景', '退出码', 'upgrade 耗时(s)', '最新 revision 的状态', 'helm history', '3 秒后的 Pod', '最后一行输出']] + [list(map(str, r)) for r in rows]))
print('  默认的 upgrade 提交清单就返回,不等 Pod 起来:退出码 0,release 是 deployed,新 Pod 却起不来(maxUnavailable 默认 25% 取整为 0,旧 Pod 还在服务,Deployment 的滚动卡住);加 --wait 能发现它,退出码非 0,release 变成 failed,但不会自己回滚,旧 Pod 照常在;--rollback-on-failure 在等待超时后自动回滚')

# ============ 四 ============
print('== 四:helm rollback。install(副本 2,日志 info)→ upgrade(副本 4,日志 debug)→ upgrade 到坏镜像(带 --wait,失败)→ helm rollback 到 revision 2 / 1。看 revision 编号怎么走、回滚后的副本数和日志级别、耗时')
reset(); h('install', 'shop', 'chart', '--set', 'replicaCount=2', '--wait'); up_('--set', 'replicaCount=4', '--set', 'logLevel=debug', '--wait'); rc, o, dt = up_('--set', 'replicaCount=4', '--set', 'logLevel=debug', '--set', 'image.tag=1.36-nope', '--wait', '--timeout', '20s')
print(f'  坏镜像 upgrade --wait:退出码 {rc};helm history:{hist_txt()}')
rc, o, dt = h('rollback', 'shop', '2', '--wait'); lv = ko('get', 'deploy', 'shop', '-n', NS, '-o', 'jsonpath={.spec.template.spec.containers[0].env[0].value}')
print(f'  helm rollback shop 2 --wait:退出码 {rc},{dt:.1f} s;输出 {o.splitlines()[-1][:60]};回滚后副本数 {replicas()},日志级别 {lv},镜像 tag {ko("get", "deploy", "shop", "-n", NS, "-o", "jsonpath={.spec.template.spec.containers[0].image}").split(":")[1]};helm history:{hist_txt()}')
rc, o, dt = h('rollback', 'shop', '1', '--wait'); lv = ko('get', 'deploy', 'shop', '-n', NS, '-o', 'jsonpath={.spec.template.spec.containers[0].env[0].value}')
print(f'  再 helm rollback shop 1 --wait:退出码 {rc};回滚后副本数 {replicas()},日志级别 {lv};helm history:{hist_txt()}')
print('  回滚不是 “回到过去”,而是用旧 revision 的清单再做一次新的 revision(编号继续往上走),旧的记录都还在')

# ============ 五 ============
print('== 五:有人用 kubectl 手工改了线上。install 副本 3 → kubectl scale 到 7 → (a)upgrade 只改日志级别(副本数仍是 3);(b)upgrade 改副本数为 5;(c)helm rollback 回上一个 revision。每步之后读副本数')
reset(); h('install', 'shop', 'chart', '--wait'); k('scale', 'deploy/shop', '-n', NS, '--replicas=7'); time.sleep(1); a0 = replicas()
rc, o, _ = up_('--set', 'logLevel=debug'); a1 = replicas(); print(f'  手工 kubectl scale 之后副本数 {a0};(a)helm upgrade 只改日志级别(退出码 {rc}):副本数 {a1}' + ('' if rc == 0 else f';{o.splitlines()[-1][:160]}'))
rc, o, _ = up_('--set', 'logLevel=debug', '--set', 'replicaCount=5'); a2 = replicas(); print(f'  (b)helm upgrade 改 replicaCount=5(退出码 {rc}):副本数 {a2}' + ('' if rc == 0 else f';{o.splitlines()[-1][:160]}'))
rr = {n: re.search(r'replicas: (\d+)', h('get', 'manifest', 'shop', '--revision', str(n))[1]).group(1) for n in (1, 2, 3)}
k('scale', 'deploy/shop', '-n', NS, '--replicas=9'); time.sleep(1); a3 = replicas(); rc, o, _ = h('rollback', 'shop'); a4 = replicas(); print(f'  再手工 scale 到 {a3},(c)helm rollback(不带编号,回到上一个 revision,退出码 {rc}):副本数 {a4};各 revision 的清单里 replicas:{rr}' + ('' if rc == 0 else f';{o.splitlines()[-1][:160]}'))
fm = ko('get', 'deploy', 'shop', '-n', NS, '--show-managed-fields', '-o', 'jsonpath={range .metadata.managedFields[*]}{.manager}/{.operation} {end}'); print(f'  Deployment 的 managedFields 里的管理者(manager/operation):{fm}')
reset(); h('install', 'shop', 'chart', '--wait'); k('scale', 'deploy/shop', '-n', NS, '--replicas=7'); time.sleep(1)
rc, o, _ = up_('--set', 'logLevel=debug', '--force-conflicts'); print(f'  (d)手工 scale 到 7 之后 helm upgrade 只改日志级别并加 --force-conflicts(退出码 {rc}):副本数 {replicas()}')
print('  Helm 4 默认用服务端应用(server-side apply):helm 作为字段管理者 "helm" 提交清单,kubectl scale 改过的字段属于另一个管理者,冲突时默认拒绝并报错;--force-conflicts 让 helm 抢回这些字段的所有权,清单里写的是 3,所以副本数回到 3')
reset(); rc, o, _ = h('install', 'shop', 'chart', '--wait', '--server-side=false'); k('scale', 'deploy/shop', '-n', NS, '--replicas=7'); k('annotate', 'deploy/shop', '-n', NS, 'note=hand'); time.sleep(1)
rc1, o1, _ = up_('--set', 'logLevel=debug', '--server-side=false'); r1 = replicas(); an = ko('get', 'deploy', 'shop', '-n', NS, '-o', 'jsonpath={.metadata.annotations.note}'); rc2, o2, _ = up_('--set', 'logLevel=debug', '--set', 'replicaCount=5', '--server-side=false'); r2 = replicas(); k('scale', 'deploy/shop', '-n', NS, '--replicas=9'); time.sleep(1); rc3, o3, _ = h('rollback', 'shop', '1', '--server-side=false'); r3 = replicas()
print(f'  (e)改用客户端三方合并(--server-side=false)重来一遍:手工 scale 到 7 → upgrade 只改日志级别(退出码 {rc1}):副本数 {r1},手工加的注解 note = {an or "(没了)"};upgrade 改 replicaCount=5(退出码 {rc2}):副本数 {r2};再手工 scale 到 9 → helm rollback 1(退出码 {rc3}):副本数 {r3}')
print('  客户端三方合并下,清单里写了的字段(replicas: 3)会被覆盖回清单的值,即使这个字段在两个 revision 之间没有变;清单里没有写的字段(手工加的注解)被保留。所以手工改过的副本数在下一次 helm upgrade 时被悄悄改回去,不报错;服务端应用则是报冲突、拒绝')
k('delete', 'ns', NS, '--wait=false')
print('说明(哪些是测到的,哪些没有测)\n  每个场景只跑了一次;耗时含 helm 进程本身;没有测:helm hooks(pre-upgrade / post-upgrade Job)、数据库迁移与回滚的配合、CRD、有状态应用与 PVC、--reuse-values 的陷阱、helm 3 的行为(这里只用 4.3.1,它的 --atomic 在 4 里改名 --rollback-on-failure)、更大的 release(Secret 有 1 MiB 的体积限制,没有逼近它)')
