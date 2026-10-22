import sys, os, re, time, json, shutil, pathlib, subprocess, statistics, collections, textwrap; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
import yaml
tee('v90')
cn, _ = up('main'); load('busybox:1.36'); NS = ns('v90')
D = HERE / 'vtmp' / 'v90'; shutil.rmtree(D, ignore_errors=True); D.mkdir(parents=True)
def W(path, text):
    p = D / path; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(textwrap.dedent(text).lstrip('\n'))
# ---------------- Helm chart ----------------
W('chart/Chart.yaml', '''
    apiVersion: v2
    name: shop
    version: 0.1.0
    appVersion: "1"
    ''')
W('chart/values.yaml', '''
    replicaCount: 1
    image: {repository: busybox, tag: "1.36"}
    resources: {}
    env: {LOG_LEVEL: info}
    podAnnotations: {}
    checksumConfig: false
    ingress: {enabled: false, host: ""}
    ''')
W('chart/templates/deployment.yaml', '''
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
          {{- if or .Values.podAnnotations .Values.checksumConfig }}
          annotations:
            {{- if .Values.checksumConfig }}
            checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
            {{- end }}
            {{- with .Values.podAnnotations }}
            {{- toYaml . | nindent 8 }}
            {{- end }}
          {{- end }}
        spec:
          containers:
          - name: app
            image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
            command: [sleep, "3600"]
            envFrom:
            - configMapRef: {name: shop-config}
            {{- with .Values.resources }}
            resources:
              {{- toYaml . | nindent 10 }}
            {{- end }}
    ''')
W('chart/templates/configmap.yaml', '''
    apiVersion: v1
    kind: ConfigMap
    metadata:
      name: shop-config
      labels: {app: shop}
    data:
      {{- range $k, $v := .Values.env }}
      {{ $k }}: {{ $v | quote }}
      {{- end }}
    ''')
W('chart/templates/service.yaml', '''
    apiVersion: v1
    kind: Service
    metadata:
      name: shop
      labels: {app: shop}
    spec:
      selector: {app: shop}
      ports: [{port: 80}]
    ''')
W('chart/templates/ingress.yaml', '''
    {{- if .Values.ingress.enabled }}
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    metadata:
      name: shop
      labels: {app: shop}
    spec:
      rules:
      - host: {{ .Values.ingress.host | quote }}
        http:
          paths:
          - {path: /, pathType: Prefix, backend: {service: {name: shop, port: {number: 80}}}}
    {{- end }}
    ''')
W('values-dev.yaml', '''
    replicaCount: 1
    env: {LOG_LEVEL: debug}
    ''')
W('values-staging.yaml', '''
    replicaCount: 2
    image: {tag: "1.36.1"}
    resources: {requests: {cpu: 50m, memory: 32Mi}}
    ingress: {enabled: true, host: staging.shop.local}
    ''')
W('values-prod.yaml', '''
    replicaCount: 5
    image: {tag: "1.36.1"}
    resources: {requests: {cpu: 200m, memory: 128Mi}, limits: {memory: 256Mi}}
    env: {LOG_LEVEL: warn}
    ingress: {enabled: true, host: shop.local}
    ''')
# ---------------- Kustomize ----------------
W('kz/base/deployment.yaml', '''
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: shop
      labels: {app: shop}
    spec:
      replicas: 1
      selector:
        matchLabels: {app: shop}
      template:
        metadata:
          labels: {app: shop}
        spec:
          containers:
          - name: app
            image: busybox:1.36
            command: [sleep, "3600"]
            envFrom:
            - configMapRef: {name: shop-config}
    ''')
W('kz/base/service.yaml', '''
    apiVersion: v1
    kind: Service
    metadata:
      name: shop
      labels: {app: shop}
    spec:
      selector: {app: shop}
      ports: [{port: 80}]
    ''')
W('kz/base/configmap.yaml', '''
    apiVersion: v1
    kind: ConfigMap
    metadata:
      name: shop-config
      labels: {app: shop}
    data:
      LOG_LEVEL: "info"
    ''')
W('kz/base/kustomization.yaml', '''
    resources: [deployment.yaml, service.yaml, configmap.yaml]
    ''')
def ingress(host): return f'''
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    metadata:
      name: shop
      labels: {{app: shop}}
    spec:
      rules:
      - host: "{host}"
        http:
          paths:
          - {{path: /, pathType: Prefix, backend: {{service: {{name: shop, port: {{number: 80}}}}}}}}
    '''
W('kz/overlays/dev/kustomization.yaml', '''
    resources: [../../base]
    patches:
    - target: {kind: ConfigMap, name: shop-config}
      patch: |-
        - {op: replace, path: /data/LOG_LEVEL, value: debug}
    ''')
W('kz/overlays/staging/ingress.yaml', ingress('staging.shop.local'))
W('kz/overlays/staging/kustomization.yaml', '''
    resources: [../../base, ingress.yaml]
    replicas: [{name: shop, count: 2}]
    images: [{name: busybox, newTag: "1.36.1"}]
    patches:
    - target: {kind: Deployment, name: shop}
      patch: |-
        - op: add
          path: /spec/template/spec/containers/0/resources
          value: {requests: {cpu: 50m, memory: 32Mi}}
    ''')
W('kz/overlays/prod/ingress.yaml', ingress('shop.local'))
W('kz/overlays/prod/kustomization.yaml', '''
    resources: [../../base, ingress.yaml]
    replicas: [{name: shop, count: 5}]
    images: [{name: busybox, newTag: "1.36.1"}]
    patches:
    - target: {kind: Deployment, name: shop}
      patch: |-
        - op: add
          path: /spec/template/spec/containers/0/resources
          value: {requests: {cpu: 200m, memory: 128Mi}, limits: {memory: 256Mi}}
    - target: {kind: ConfigMap, name: shop-config}
      patch: |-
        - {op: replace, path: /data/LOG_LEVEL, value: warn}
    ''')
def run(*a, **kw):
    r = subprocess.run(list(map(str, a)), capture_output=True, text=True, cwd=D, **kw); return r.returncode, r.stdout, r.stderr
def helm(env, *extra, chart='chart'):
    args = ['helm', 'template', 'shop', chart] + (['-f', f'values-{env}.yaml'] if env else []) + list(extra); return run(*args)
def kz(env, d=None): return run('kubectl', 'kustomize', d or f'kz/overlays/{env}')
def docs(text): return {(d['kind'], d['metadata']['name']): d for d in yaml.safe_load_all(text) if d}
def diff(a, b, path=''):
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k_ in sorted(set(a) | set(b)):
            if k_ not in a: out.append(f'{path}/{k_}: 只在第二个里')
            elif k_ not in b: out.append(f'{path}/{k_}: 只在第一个里')
            else: out += diff(a[k_], b[k_], f'{path}/{k_}')
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)): out += diff(x, y, f'{path}[{i}]')
    elif a != b: out.append(f'{path}: {a!r} ≠ {b!r}')
    return out
def lines(paths): return sum(1 for p in paths for l in p.read_text().splitlines() if l.strip() and not l.strip().startswith('#'))
print(f'Helm {subprocess.run(["helm", "version", "--short"], capture_output=True, text=True).stdout.strip()},kubectl 内置的 Kustomize({run("kubectl", "version", "--client")[1].split("Kustomize Version: ")[-1].strip()});集群 {cn} 只在第六节用。同一个小应用 shop(Deployment + ConfigMap + Service,staging 和 prod 多一个 Ingress),三个环境 dev / staging / prod 的差别:副本数、镜像 tag、资源、日志级别、是否有 Ingress 与主机名。Helm 写成一个 chart 加三个 values 文件,Kustomize 写成 base 加三个 overlay')

# ============ 一 ============
print('== 一:同样的三个环境,两种写法渲染出来的资源一样吗?把 helm template 与 kubectl kustomize 的输出按 (kind, name) 解析成对象再逐字段比较,另外数配置文件的有效行数(不含空行和注释)')
rows = []
for e in ('dev', 'staging', 'prod'):
    h = docs(helm(e)[1]); z = docs(kz(e)[1]); d = []
    for key in sorted(set(h) | set(z)):
        if key not in h: d.append(f'{key}: 只在 Kustomize 里')
        elif key not in z: d.append(f'{key}: 只在 Helm 里')
        else: d += [f'{key[0]}/{key[1]}{x}' for x in diff(h[key], z[key])]
    rows.append((e, len(h), len(z), len(d), '; '.join(d)[:150] or '-'))
print(table([['环境', 'Helm 的资源数', 'Kustomize 的资源数', '逐字段不同的地方', '详情']] + [list(map(str, r)) for r in rows]))
hl = lines([p for p in (D / 'chart').rglob('*') if p.is_file()]); hv = lines(sorted(D.glob('values-*.yaml'))); kb = lines(sorted((D / 'kz/base').glob('*'))); ko_ = lines([p for p in (D / 'kz/overlays').rglob('*.yaml')])
print(f'  配置行数:Helm chart(Chart.yaml + values.yaml + 4 个模板){hl} 行 + 三个环境的 values 文件 {hv} 行 = {hl + hv} 行;Kustomize base {kb} 行 + 三个 overlay {ko_} 行 = {kb + ko_} 行。两种写法渲染出的资源逐字段相同(上表),所以差别不在结果,在于怎么表达差异;行数只是这个小例子的数字,不能推广')

# ============ 二 ============
print('== 二:渲染一次要多久。prod 环境,各跑 30 次取中位数和 p90(进程启动含在内)')
def timeit(fn, n=30):
    ts = []
    for _ in range(n): t = time.perf_counter(); fn(); ts.append((time.perf_counter() - t) * 1000)
    ts.sort(); return statistics.median(ts), ts[int(n * 0.9) - 1]
for name, fn in (('helm template', lambda: helm('prod')), ('kubectl kustomize', lambda: kz('prod'))):
    m, p = timeit(fn); print(f'  {name}:中位数 {m:.0f} ms,p90 {p:.0f} ms')
print('  两者都在几十毫秒量级(进程启动占大头),发布流程里这点时间可以忽略;差别不在速度')

# ============ 三 ============
print('== 三:要改一个 chart 作者没做成 value 的字段。需求:给 prod 的 Pod 加 terminationGracePeriodSeconds: 45。Helm 这边试 --set terminationGracePeriodSeconds=45 和 --set-string 同名(chart 模板里没有这个字段);Kustomize 这边在 prod overlay 里加一条 JSON patch')
for flag in ('--set', '--set-string'):
    rc, o, e = helm('prod', flag, 'terminationGracePeriodSeconds=45'); d = docs(o)[('Deployment', 'shop')]['spec']['template']['spec']
    print(f'  Helm {flag} terminationGracePeriodSeconds=45:退出码 {rc},渲染出的 Pod spec 里 terminationGracePeriodSeconds = {d.get("terminationGracePeriodSeconds", "(没有这个字段)")}')
shutil.copytree(D / 'kz/overlays/prod', D / 'kz/overlays/prod2'); (D / 'kz/overlays/prod2/kustomization.yaml').write_text((D / 'kz/overlays/prod2/kustomization.yaml').read_text().replace('resources: [../../base, ingress.yaml]', 'resources: [../../base, ingress.yaml]').replace('patches:\n', 'patches:\n- target: {kind: Deployment, name: shop}\n  patch: |-\n    - {op: add, path: /spec/template/spec/terminationGracePeriodSeconds, value: 45}\n', 1)); (D / 'kz/overlays/prod2/kustomization.yaml').write_text((D / 'kz/overlays/prod2/kustomization.yaml').read_text().replace('../../base', '../../base'))
rc, o, e = run('kubectl', 'kustomize', 'kz/overlays/prod2'); 
rc, o, e = kz(None, 'kz/overlays/prod2'); d = docs(o)[('Deployment', 'shop')]['spec']['template']['spec']
print(f'  Kustomize 加一条 JSON patch:退出码 {rc},渲染出的 Pod spec 里 terminationGracePeriodSeconds = {d.get("terminationGracePeriodSeconds", "(没有这个字段)")}')
print('  Helm 的 --set 对模板里没有引用的键没有任何作用,而且不报错;chart 里没做成 value 的字段,使用者只能改模板(fork)或者在渲染结果上再处理。Kustomize 的补丁可以改任意字段,不需要上游预先留口子')

# ============ 四 ============
print('== 四:类型陷阱。镜像 tag 是 1.10。Helm:--set image.tag=1.10、--set-string image.tag=1.10、values 文件里 tag: 1.10(不加引号)、tag: "1.10"(加引号);Kustomize:images 的 newTag 写 1.10 与 "1.10"')
rows = []
def img(o): return docs(o)[('Deployment', 'shop')]['spec']['template']['spec']['containers'][0]['image']
for name, extra in (('helm --set image.tag=1.10', ['--set', 'image.tag=1.10']), ('helm --set-string image.tag=1.10', ['--set-string', 'image.tag=1.10'])):
    rc, o, e = helm(None, *extra); rows.append((name, rc, img(o) if rc == 0 else e.strip()[:100]))
for name, txt in (('values 文件 tag: 1.10(不加引号)', 'image: {tag: 1.10}\n'), ('values 文件 tag: "1.10"', 'image: {tag: "1.10"}\n')):
    (D / 'v-tmp.yaml').write_text(txt); rc, o, e = run('helm', 'template', 'shop', 'chart', '-f', 'v-tmp.yaml'); rows.append((name, rc, img(o) if rc == 0 else e.strip()[:100]))
for name, tag in (('Kustomize newTag: 1.10(不加引号)', '1.10'), ('Kustomize newTag: "1.10"', '"1.10"')):
    shutil.rmtree(D / 'kz/t4', ignore_errors=True); W('kz/t4/kustomization.yaml', f'resources: [../base]\nimages: [{{name: busybox, newTag: {tag}}}]\n'); rc, o, e = run('kubectl', 'kustomize', 'kz/t4'); rows.append((name, rc, img(o) if rc == 0 else e.strip().splitlines()[-1][:120]))
print(table([['写法', '退出码', '渲染出的镜像(或错误)']] + [list(map(str, r)) for r in rows]))
print('  YAML 文件里没加引号的 1.10 是个浮点数,值 1.1,渲染出的镜像变成 busybox:1.1(Helm 不报错);这次测到 --set image.tag=1.10 得到的是 1.10,和 --set-string 一样,没有被当成浮点数。Kustomize 的 newTag 不加引号直接报类型错误。版本号这类看起来像数字的值,在 values 文件里要加引号')

# ============ 五 ============
print('== 五:写错了字段名会怎样。(a)Helm:values 里把 replicaCount 写成 replicaCnt: 9;(b)Helm:chart 带 values.schema.json(additionalProperties: false)之后同样的写错;(c)Kustomize:补丁里把 replicas 写成 replicass: 9,kubectl kustomize 的输出,再用 kubectl apply --dry-run=server --validate=strict 提交给集群')
(D / 'v-typo.yaml').write_text('replicaCnt: 9\n'); rc, o, e = run('helm', 'template', 'shop', 'chart', '-f', 'v-typo.yaml'); print(f'  (a)Helm 无 schema:退出码 {rc},渲染出的副本数 {docs(o)[("Deployment", "shop")]["spec"]["replicas"]}(想要 9,拿到的是默认值)')
(D / 'chart/values.schema.json').write_text(json.dumps({'$schema': 'https://json-schema.org/draft-07/schema#', 'type': 'object', 'additionalProperties': False, 'properties': {k_: {} for k_ in ('replicaCount', 'image', 'resources', 'env', 'podAnnotations', 'checksumConfig', 'ingress')}}))
rc, o, e = run('helm', 'template', 'shop', 'chart', '-f', 'v-typo.yaml'); print(f'  (b)Helm 加 schema:退出码 {rc};{e.strip().splitlines()[-1][:200] if e.strip() else o[:100]}')
shutil.rmtree(D / 'kz/t5', ignore_errors=True); W('kz/t5/kustomization.yaml', 'resources: [../base]\npatches:\n- target: {kind: Deployment, name: shop}\n  patch: |-\n    - {op: add, path: /spec/replicass, value: 9}\n')
rc, o, e = run('kubectl', 'kustomize', 'kz/t5'); has = 'replicass' in o; print(f'  (c)Kustomize:退出码 {rc},输出里带着拼错的字段 replicass: {has}')
r2 = k('apply', '-n', NS, '--dry-run=server', '--validate=strict', '-f', '-', input=o); print(f'  (c)提交给集群(--dry-run=server --validate=strict):退出码 {r2[0]};{r2[1].strip().splitlines()[-1][:220]}')
print('  Helm 对 values 里的未知键默认静默忽略,拿到的是默认值;加 values.schema.json 之后会报错。Kustomize 不认识字段的含义,拼错的字段会原样输出,到集群的 schema 校验才会被发现')
(D / 'chart/values.schema.json').unlink()

# ============ 六 ============
print('== 六:改了 ConfigMap 里的值,Pod 会不会重启?三种写法部署到集群(Deployment 用 envFrom 引用 ConfigMap,busybox 里 printenv 看当前的 LOG_LEVEL),把 LOG_LEVEL 从 info 改成 debug 后重新 apply,等 8 s,看 ReplicaSet 数量、Pod 是否重建、容器里的 LOG_LEVEL。(a)Helm 不带 checksum 注解;(b)Helm 设 checksumConfig=true(Pod 模板里加 checksum/config 注解);(c)Kustomize 用 configMapGenerator(名字带内容哈希)')
shutil.rmtree(D / 'kz/gen', ignore_errors=True); W('kz/gen/deployment.yaml', (D / 'kz/base/deployment.yaml').read_text().replace('shop-config', 'shop-config')); W('kz/gen/kustomization.yaml', 'resources: [deployment.yaml]\nconfigMapGenerator:\n- name: shop-config\n  literals: [LOG_LEVEL=info]\n')
def rolled(name, render, mutate):
    k('delete', 'all,cm', '-n', NS, '--all', '--wait=true', timeout=120); rc, o = k('apply', '-n', NS, '-f', '-', input=render('info')); assert rc == 0, o
    k('rollout', 'status', 'deploy/shop', '-n', NS, '--timeout=90s', timeout=120); pod0 = ko('get', 'pod', '-n', NS, '-l', 'app=shop', '-o', 'jsonpath={.items[*].metadata.name}')
    mutate(); rc, o = k('apply', '-n', NS, '-f', '-', input=render('debug')); assert rc == 0, o; time.sleep(8); k('rollout', 'status', 'deploy/shop', '-n', NS, '--timeout=90s', timeout=120)
    pod1 = ko('get', 'pod', '-n', NS, '-l', 'app=shop', '-o', 'jsonpath={.items[*].metadata.name}'); rs = ko('get', 'rs', '-n', NS, '-o', 'name').split(); lv = ko('exec', '-n', NS, 'deploy/shop', '--', 'printenv', 'LOG_LEVEL')
    return len(rs), pod0 != pod1, lv, pod0, pod1
def r_helm(chk): 
    def f(level): return helm(None, '--set', f'env.LOG_LEVEL={level}', '--set', f'checksumConfig={"true" if chk else "false"}')[1]
    return f
def r_kz(level): 
    t = (D / 'kz/gen/kustomization.yaml'); t.write_text(re.sub(r'LOG_LEVEL=\w+', f'LOG_LEVEL={level}', t.read_text())); return run('kubectl', 'kustomize', 'kz/gen')[1]
rows = []
for name, render in (('(a)Helm,没有 checksum 注解', r_helm(False)), ('(b)Helm,checksumConfig=true', r_helm(True)), ('(c)Kustomize configMapGenerator', r_kz)):
    n, changed, lv, p0, p1 = rolled(name, render, lambda: None); rows.append((name, n, '是' if changed else '否', lv))
print(table([['写法', 'ReplicaSet 数', 'Pod 重建了吗', '容器里的 LOG_LEVEL']] + [list(map(str, r)) for r in rows]))
print('  ConfigMap 改了,但 Deployment 的 Pod 模板没变就不会触发滚动更新:Pod 里还是旧值。Helm 的惯用法是把 ConfigMap 内容的哈希写进 Pod 模板注解(checksum/config);Kustomize 的 configMapGenerator 给 ConfigMap 名字加内容哈希,Deployment 里的引用被自动改写,模板变了就滚动')
k('delete', 'ns', NS, '--wait=false')
print('说明(哪些是测到的,哪些没有测)\n  渲染比较是离线的,第六节才用集群;只有一个小应用,三个环境,行数和耗时只代表这个例子;没有测:helm install / upgrade 的发布记录(见下一篇)、Helm hooks、子 chart 与 library chart、Kustomize 的 components 与 vars/replacements、helm 与 kustomize 叠加使用(kustomize --enable-helm、post-renderer)')
