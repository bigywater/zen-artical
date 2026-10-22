import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import prometheus_client as pc
from prometheus_client import CollectorRegistry, Gauge, start_http_server
tee('v75'); reset()
print('告警:持续时间、抖动与去重。Prometheus 3.15.0 的告警规则(for、keep_firing_for)+ Alertmanager 0.34.1(分组、repeat_interval、抑制、静默)+ 我写的 webhook 接收端(记录每一次通知)。用一条按脚本变化的时间线(约 160 s)驱动所有情形,指标是 prometheus_client 暴露的 gauge')
GW, GI, RI = 3, 6, 30        # group_wait / group_interval / repeat_interval(秒)
reg = CollectorRegistry()
FLAP = Gauge('flap', 'flapping signal', registry=reg); BAD = Gauge('bad_many', 'many instances', ['inst'], registry=reg); CD = Gauge('cluster_down', 'cluster down', ['cluster'], registry=reg)
ID = Gauge('inst_down', 'instance down', ['cluster', 'inst'], registry=reg); SIL = Gauge('silenced_signal', 'to be silenced', registry=reg)
FLAP.set(0); SIL.set(0); CD.labels('c1').set(0)
for i in range(20): BAD.labels(f'i{i}').set(0)
ID.labels('c1', 'n1').set(0)
port, srv = (lambda p: (p, start_http_server(p, addr='127.0.0.1', registry=reg)[0]))(free_port())
posts = []; plk = threading.Lock(); T0 = [None]
def hook(h):
    pass
class H(http.server.BaseHTTPRequestHandler if False else object): pass
import http.server
class WH(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        n = int(self.headers.get('Content-Length', 0)); body = json.loads(self.rfile.read(n) or b'{}')
        with plk: posts.append((time.time() - (T0[0] or time.time()), self.path, body))
        self.send_response(200); self.send_header('Content-Length', '0'); self.end_headers()
wport = free_port(); wsrv = http.server.ThreadingHTTPServer(('127.0.0.1', wport), WH); wsrv.daemon_threads = True; threading.Thread(target=wsrv.serve_forever, daemon=True).start()
rules = TT / 'v75_rules.yml'
rules.write_text('''groups:
  - name: r
    interval: 1s
    rules:
      - {alert: FlapFor0, expr: flap == 1, for: 0s}
      - {alert: FlapFor5, expr: flap == 1, for: 5s}
      - {alert: FlapFor15, expr: flap == 1, for: 15s}
      - {alert: FlapKeep10, expr: flap == 1, for: 0s, keep_firing_for: 10s}
      - {alert: ManyA, expr: bad_many == 1, labels: {grp: a}}
      - {alert: ManyB, expr: bad_many == 1, labels: {grp: b}}
      - {alert: ClusterDown, expr: cluster_down == 1, labels: {severity: critical}}
      - {alert: InstanceDown, expr: inst_down == 1, labels: {severity: warning}}
      - {alert: Silenced, expr: silenced_signal == 1}
''')
am = Alertmgr('v75am', f"""global:
  resolve_timeout: 1m
route:
  receiver: all
  group_by: [alertname]
  group_wait: {GW}s
  group_interval: {GI}s
  repeat_interval: {RI}s
  routes:
    - matchers: [grp="a"]
      receiver: ra
      group_by: [alertname]
      group_wait: {GW}s
      group_interval: {GI}s
      repeat_interval: {RI}s
    - matchers: [grp="b"]
      receiver: rb
      group_by: [alertname, inst]
      group_wait: {GW}s
      group_interval: {GI}s
      repeat_interval: {RI}s
receivers:
  - {{name: all, webhook_configs: [{{url: 'http://127.0.0.1:{wport}/all', send_resolved: true}}]}}
  - {{name: ra, webhook_configs: [{{url: 'http://127.0.0.1:{wport}/ra', send_resolved: true}}]}}
  - {{name: rb, webhook_configs: [{{url: 'http://127.0.0.1:{wport}/rb', send_resolved: true}}]}}
inhibit_rules:
  - source_matchers: [severity="critical"]
    target_matchers: [severity="warning"]
    equal: [cluster]
""").start()
prom = Prom('v75', f"""global:
  scrape_interval: 1s
  evaluation_interval: 1s
rule_files: ['{rules}']
alerting:
  alertmanagers:
    - static_configs:
        - targets: ['127.0.0.1:{am.port}']
scrape_configs:
  - job_name: app
    static_configs:
      - targets: ['127.0.0.1:{port}']
""").start()
time.sleep(3)
# 静默:对 Silenced 这条告警
import urllib.request
def am_post(path, obj):
    r = urllib.request.Request(f'http://127.0.0.1:{am.port}{path}', data=json.dumps(obj).encode(), headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(r, timeout=10) as x: return json.loads(x.read() or b'null')
now = time.time(); iso = lambda t: time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime(t))
sil = am_post('/api/v2/silences', {'matchers': [{'name': 'alertname', 'value': 'Silenced', 'isRegex': False, 'isEqual': True}], 'startsAt': iso(now - 5), 'endsAt': iso(now + 600), 'createdBy': 'exp', 'comment': 'v75'})
T0[0] = time.time(); T = T0[0]
def at(t, fn):
    time.sleep(max(0, T + t - time.time())); fn()
sched = []
for s in (10, 22, 34): sched += [(s, lambda: FLAP.set(1)), (s + 3, lambda: FLAP.set(0))]
sched += [(50, lambda: FLAP.set(1)), (75, lambda: FLAP.set(0))]
sched += [(60, lambda: SIL.set(1)), (90, lambda: SIL.set(0))]
sched += [(100, lambda: [BAD.labels(f'i{i}').set(1) for i in range(20)]), (140, lambda: [BAD.labels(f'i{i}').set(0) for i in range(20)])]
sched += [(100, lambda: (CD.labels('c1').set(1), ID.labels('c1', 'n1').set(1))), (150, lambda: (CD.labels('c1').set(0), ID.labels('c1', 'n1').set(0)))]
sched.sort(key=lambda x: x[0]); snap = {}; snap70 = []
def take70():
    time.sleep(max(0, T + 70 - time.time()))
    with urllib.request.urlopen(f'http://127.0.0.1:{am.port}/api/v2/alerts', timeout=10) as x: snap70[:] = json.loads(x.read())
threading.Thread(target=take70, daemon=True).start()
for t, fn in sched:
    at(t, fn)
time.sleep(max(0, T + 120 - time.time()))
def alerts_now(): 
    with urllib.request.urlopen(f'http://127.0.0.1:{am.port}/api/v2/alerts', timeout=10) as x: return json.loads(x.read())
snap = alerts_now()
time.sleep(max(0, T + 175 - time.time()))
with plk: P = list(posts)
def posts_for(name, status='firing'):
    return [(round(t, 1), path) for t, path, b in P for a in b.get('alerts', []) if a['labels']['alertname'] == name and a['status'] == status]

print('== 一:for 与 keep_firing_for。同一个信号 flap(1 表示异常):第 10、22、34 秒各出现一次 3 秒的短暂异常(间隔 9 秒),第 50 到 75 秒是持续 25 秒的异常。四条规则:for 0s、for 5s、for 15s、for 0s 加 keep_firing_for 10s。Alertmanager group_wait 3 s。看每条规则发出的 firing 通知和 resolved 通知(webhook 收到的时刻,相对时间线起点)')
rows = []
for name, label in (('FlapFor0', 'for: 0s'), ('FlapFor5', 'for: 5s'), ('FlapFor15', 'for: 15s'), ('FlapKeep10', 'for: 0s + keep_firing_for: 10s')):
    f = [t for t, p in posts_for(name, 'firing') if p == '/all']; r = [t for t, p in posts_for(name, 'resolved') if p == '/all']
    rows.append((label, len(f), ', '.join(f'{t:.0f}' for t in f) or '-', len(r), ', '.join(f'{t:.0f}' for t in r) or '-'))
table(rows, ['规则', 'firing 通知次数', 'firing 通知时刻(s)', 'resolved 通知次数', 'resolved 通知时刻(s)'])
def rel(ts):
    try:
        import datetime
        return datetime.datetime.fromisoformat(ts.replace('Z', '+00:00')).timestamp() - T0[0]
    except Exception: return float('nan')
for name in ('FlapFor0', 'FlapKeep10'):
    print(f'  {name} 的 webhook 通知明细(通知时刻 | 整条通知的状态 | 其中该告警的状态、startsAt、endsAt,时间都相对时间线起点):')
    for t, path, b in P:
        if path != '/all': continue
        for a in b['alerts']:
            if a['labels']['alertname'] == name: print(f'    {t:6.1f} s | {b["status"]:8s} | {a["status"]:8s} start {rel(a["startsAt"]):7.1f} end {rel(a["endsAt"]) if not a["endsAt"].startswith("0001") else float("nan"):7.1f}')
print('  for: 5s 和 for: 15s 要求条件连续成立这么久才从 pending 变 firing,3 秒的短暂异常到不了,只有持续异常才通知(通知时刻比异常开始晚 for 的时长再加 group_wait 3 s 和评估的延迟)。for: 0s 时,短暂异常有没有通知取决于它和 Alertmanager 分组计时(group_wait、group_interval)的相位:一个告警要在计时点到来时还处于 firing 才会发出 firing 通知,在计时点之前已经恢复的,Alertmanager 什么都不发——看上面 FlapFor0 的明细,三次短暂异常里发出通知的只有 startsAt 对应的那一次(具体是哪几次每次运行会不同)。keep_firing_for 在条件不再成立之后继续保持 firing 一段时间:FlapKeep10 的 startsAt 到 endsAt 是一整段,相隔 9 s 的三次短暂异常被合并成了一个告警,只发一次 firing 和一次 resolved;持续异常那次 firing 之后还有第二次 firing 通知,那是 repeat_interval 到期后的重复通知')

print('== 二:分组。20 个实例在第 100 秒同时出现同一个问题(bad_many)。同样的告警规则复制成两份,带不同的 grp 标签,走不同的路由:grp=a 按 alertname 分组,grp=b 按 alertname 加 inst 分组。看这两条路由各发出多少次 webhook 通知、每次通知里有几个告警')
rows = []
for name, route, label in (('ManyA', '/ra', 'group_by: [alertname]'), ('ManyB', '/rb', 'group_by: [alertname, inst]')):
    ps = [(round(t, 1), len(b['alerts'])) for t, path, b in P if path == route and t >= 99 and b['status'] == 'firing' and t < 125]
    rows.append((label, len(ps), sum(n for _, n in ps), ', '.join(f'{n}' for _, n in ps[:6]) + ('…' if len(ps) > 6 else '')))
table(rows, ['分组方式', '第 100 到 125 秒 firing 通知的次数', '通知里的告警总数', '每次通知里的告警数(前几次)'])
print('  按 alertname 分组时,20 个同样的告警合并成一条通知;按 alertname + inst 分组,每个实例一条通知,同一时间会来 20 条')

print(f'== 三:重复通知。ClusterDown 从第 100 秒持续到第 150 秒(50 秒),Alertmanager 的 group_wait = {GW} s、group_interval = {GI} s、repeat_interval = {RI} s。看它的 firing 通知出现在哪些时刻')
ts = [t for t, p in posts_for('ClusterDown', 'firing')]; rs = [t for t, p in posts_for('ClusterDown', 'resolved')]
print(f'  ClusterDown 的 firing 通知时刻(s):{ts};resolved 通知时刻(s):{rs}。第一次通知在告警开始之后 {ts[0] - 100:.1f} s(group_wait 加上规则评估),第二次通知比第一次晚 {ts[1] - ts[0]:.1f} s:repeat_interval 是 {RI} s,实际的间隔落在 group_interval({GI} s)的计时点上,所以是 {RI} s 到 {RI + GI} s 之间,直到恢复才发 resolved')

print('== 四:抑制与静默。第 100 秒起 ClusterDown(severity=critical)和 InstanceDown(severity=warning,同一个 cluster)同时成立;抑制规则:有 critical 告警时,同一个 cluster 的 warning 告警不通知。Silenced 这条告警在第 60 到 90 秒成立,Alertmanager 里事先对 alertname=Silenced 建了静默。看这两条告警各收到几次通知,以及第 120 秒时 Alertmanager API 里它们的状态')
st = {a['labels']['alertname']: a['status'] for a in snap if a['labels']['alertname'] in ('ClusterDown', 'InstanceDown')}
st70 = {a['labels']['alertname']: a['status'] for a in snap70 if a['labels']['alertname'] == 'Silenced'}
rows = [('ClusterDown(critical)', len(posts_for('ClusterDown', 'firing')), st.get('ClusterDown', '(不在了)')), ('InstanceDown(warning,被抑制)', len(posts_for('InstanceDown', 'firing')), json.dumps(st.get('InstanceDown', '(不在了)'), ensure_ascii=False)), ('Silenced(有静默,第 70 秒的快照)', len(posts_for('Silenced', 'firing')), json.dumps(st70.get('Silenced', '(不在)'), ensure_ascii=False))]
table([(a, b, c if isinstance(c, str) else str(c)) for a, b, c in rows], ['告警', 'firing 通知次数', 'Alertmanager API 中的状态(ClusterDown 和 InstanceDown 取第 120 秒,Silenced 取第 70 秒)'])
print('  被抑制或被静默的告警仍然存在于 Alertmanager 里(状态是 suppressed),只是不发通知;去掉 critical 告警或者静默到期之后,它们才会通知')
prom.stop(); am.stop(); srv.shutdown(); wsrv.shutdown()
print('ERRORS', dict(ERRORS))
