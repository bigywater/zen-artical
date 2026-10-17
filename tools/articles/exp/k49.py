import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k49')
cn, _ = up('main')
NS = ns('k49')
ts = lambda s: datetime.datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp()
def cj(name, policy='Allow', dur=75, suspend=False, extra='', hist=''):
    return f'''apiVersion: batch/v1
kind: CronJob
metadata: {{name: {name}, namespace: {NS}}}
spec:
  schedule: "* * * * *"
  concurrencyPolicy: {policy}
  suspend: {str(suspend).lower()}
{extra}{hist}  jobTemplate:
    spec:
      backoffLimit: 0
      template:
        spec:
          restartPolicy: Never
          terminationGracePeriodSeconds: 0
          containers: [{{name: c, image: busybox:1.36, command: [sh, -c, "echo 开始 $(date +%S); sleep {dur}; echo 结束"]}}]
'''
def sec_to_next_minute(): return 60 - (time.time() % 60)
def jobs(cjn): return sorted(kj('get', 'jobs', '-n', NS)['items'], key=lambda j: j['metadata']['creationTimestamp']) if not cjn else sorted([j for j in kj('get', 'jobs', '-n', NS)['items'] if j['metadata']['name'].startswith(cjn + '-')], key=lambda j: j['metadata']['creationTimestamp'])
def clock(t): return datetime.datetime.fromtimestamp(t).strftime('%H:%M:%S')
print(f'集群 {cn};CronJob 每个调度时刻(这里是每分钟的第 0 秒)创建一个 Job;concurrencyPolicy 决定上一个还没跑完时怎么办;所有 Job 的容器睡 75 秒,所以相邻两次会重叠')
w = sec_to_next_minute()
if w < 8: time.sleep(w + 1); w = sec_to_next_minute()
time.sleep(max(0, w - 4)); t0 = time.time()
for nm, pol in (('cj-allow', 'Allow'), ('cj-forbid', 'Forbid'), ('cj-replace', 'Replace')): k('apply', '-f', '-', input=cj(nm, pol))
k('apply', '-f', '-', input=cj('cj-miss', 'Allow', dur=5, suspend=True))
k('apply', '-f', '-', input=cj('cj-deadline', 'Allow', dur=5, suspend=True, extra='  startingDeadlineSeconds: 10\n'))
print(f'  创建时刻 {clock(t0)}(离下一个整分还有 4 秒);下一个整分 {clock(t0 + 4)}')
t_unsus_miss = t0 + 150; unsus_miss = False; t_unsus_dl = None; unsus_dl = False
snaps = []; ev_seen = {}
while time.time() - t0 < 290:
    now = time.time()
    if not unsus_miss and now >= t_unsus_miss:
        k('patch', 'cronjob', 'cj-miss', '-n', NS, '--type=merge', '-p', '{"spec":{"suspend":false}}'); unsus_miss = True; t_um = now
    if not unsus_dl and now - t0 > 70 and (now % 60) > 30 and (now % 60) < 35:
        k('patch', 'cronjob', 'cj-deadline', '-n', NS, '--type=merge', '-p', '{"spec":{"suspend":false}}'); unsus_dl = True; t_ud = now
    snaps.append((now - t0, {nm: [(j['metadata']['name'][-8:], ts(j['metadata']['creationTimestamp']) - t0, j['status'].get('active', 0), j['status'].get('succeeded', 0)) for j in jobs(nm)] for nm in ('cj-allow', 'cj-forbid', 'cj-replace', 'cj-miss', 'cj-deadline')}))
    time.sleep(3)
print('== 一:Allow / Forbid / Replace——连续三个整分,每个 CronJob 创建了哪些 Job、什么时候被替换')
for nm in ('cj-allow', 'cj-forbid', 'cj-replace'):
    allj = {}
    for t, d in snaps:
        for (name, cr, act, suc) in d[nm]: allj.setdefault(name, [cr, t, t, act, suc]); allj[name][2] = t
    print(f'  {nm}(concurrencyPolicy: {nm.split("-")[1].capitalize()}):在 {snaps[-1][0]:.0f} 秒的观察期里一共创建了 {len(allj)} 个 Job:')
    for name, (cr, first, last, act, suc) in sorted(allj.items(), key=lambda x: x[1][0]): print(f'    Job …{name} 创建于 +{cr:5.1f}s;最后一次被看到是 +{last:5.1f}s' + ('(之后消失了:被删除或被替换)' if last < snaps[-1][0] - 4 else ''))
ev = [e for e in kj('get', 'events', '-n', NS)['items'] if e['involvedObject']['kind'] == 'CronJob']
print('  CronJob 控制器的事件:')
for e in sorted(ev, key=lambda e: e.get('lastTimestamp') or ''):
    print(f'    {e["involvedObject"]["name"]:<11} {e["reason"]:<18} x{e.get("count", 1)} {e["message"][:130]}')
print('== 二:错过的调度——suspend 了 150 秒再恢复,不会补跑所有错过的,只跑最近的那一次')
mj = snaps[-1][1]['cj-miss']
print(f'  cj-miss 暂停了约 {t_um - t0:.0f} 秒(期间错过 2 次整分调度),恢复后 {snaps[-1][0] - (t_um - t0):.0f} 秒内创建的 Job:{[(n, round(c - (t_um - t0), 1)) for n, c, a, s in mj]}(时间是相对恢复那一刻的秒数)')
print('== 三:startingDeadlineSeconds——调度时刻过了太久,就不补了')
dj = snaps[-1][1]['cj-deadline']
c = kj('get', 'cronjob', 'cj-deadline', '-n', NS)
print(f'  cj-deadline(startingDeadlineSeconds=10)在某个整分之后约 {t_ud % 60:.0f} 秒恢复(那个整分的调度已经错过了 {t_ud % 60:.0f} 秒 > 10 秒):恢复后创建的 Job:{[(n, round(cr - (t_ud - t0), 1)) for n, cr, a, s in dj]}')
dl_ev = [e for e in ev if e['involvedObject']['name'] == 'cj-deadline']
print(f'  事件:{[(e["reason"], e["message"][:100]) for e in dl_ev] or "(没有)"}')
print('== 四:历史保留与状态字段')
c = kj('get', 'cronjob', 'cj-miss', '-n', NS)['status']; print(f'  cj-miss 的 status:lastScheduleTime={c.get("lastScheduleTime")} lastSuccessfulTime={c.get("lastSuccessfulTime")} active={len(c.get("active", []))};默认保留成功 Job {kj("get", "cronjob", "cj-miss", "-n", NS)["spec"].get("successfulJobsHistoryLimit")} 个、失败 {kj("get", "cronjob", "cj-miss", "-n", NS)["spec"].get("failedJobsHistoryLimit")} 个')
print(f'  命名空间里现存的 Job 总数 {len(kj("get", "jobs", "-n", NS)["items"])}(每个 CronJob 只留着最近成功的 3 个以及还在运行的)')
rmns(NS)
