import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k48')
cn, _ = up('main')
NS = ns('k48')
ts = lambda s: datetime.datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp()
def job(name, spec, cmd, restart='Never', extra=''):
    return f'''apiVersion: batch/v1
kind: Job
metadata: {{name: {name}, namespace: {NS}}}
spec:
{spec}  template:
    spec:
      restartPolicy: {restart}
      terminationGracePeriodSeconds: 0
      containers:
      - name: c
        image: busybox:1.36
        command: [sh, -c, {json.dumps(cmd)}]
'''
def jstat(name):
    j = kj('get', 'job', name, '-n', NS)['status']; return j
def jpods(name): return kj('get', 'pods', '-n', NS, '-l', f'job-name={name}')['items']
print(f'集群 {cn};Job 把“跑完一件事”做成对象:completions 要成功几个 Pod,parallelism 同时跑几个,backoffLimit 失败几次放弃')

print('== 一:completions=6、parallelism=2——同时最多 2 个,一批批地跑(每个 Pod 睡 3 秒)')
t0 = time.time(); k('apply', '-f', '-', input=job('par', '  completions: 6\n  parallelism: 2\n', 'sleep 3; echo done')); seq = []; last = None; maxact = 0
while time.time() - t0 < 60:
    s = jstat('par'); cur = (s.get('active', 0), s.get('succeeded', 0)); maxact = max(maxact, cur[0])
    if cur != last: seq.append((round(time.time() - t0, 1), cur)); last = cur
    if s.get('succeeded') == 6: break
    time.sleep(0.2)
print('  (active, succeeded) 的变化:' + ' → '.join(f'{c}@{t}s' for t, c in seq))
j = jstat('par'); print(f'  最多同时 {maxact} 个 Pod 在跑;总共 {len(jpods("par"))} 个 Pod;conditions={[ (c["type"], c["status"]) for c in j["conditions"]]};startTime→completionTime 用了 {ts(j["completionTime"]) - ts(j["startTime"]):.0f} 秒')
k('apply', '-f', '-', input=job('idx', '  completions: 4\n  parallelism: 4\n  completionMode: Indexed\n', 'echo 我是第 $JOB_COMPLETION_INDEX 个; sleep 1')); until(lambda: jstat('idx').get('succeeded') == 4, 60)
print('  completionMode: Indexed(4 个):' + '; '.join(f'{p["metadata"]["name"]}→index 注解 {p["metadata"]["annotations"].get("batch.kubernetes.io/job-completion-index")}、日志「{k("logs", p["metadata"]["name"], "-n", NS)[1].strip()}」' for p in sorted(jpods('idx'), key=lambda p: p['metadata']['name'])[:3]) + ' …')
k('delete', 'job', 'par', 'idx', '-n', NS, '--wait=true', timeout=60)

print('== 二:失败了怎么办——backoffLimit,以及 restartPolicy 的差别')
t0 = time.time(); k('apply', '-f', '-', input=job('fail-never', '  backoffLimit: 2\n', 'echo 失败; exit 1', 'Never')); k('apply', '-f', '-', input=job('fail-onfail', '  backoffLimit: 2\n', 'echo 失败; exit 1', 'OnFailure'))
maxrc = 0; podsn = {'fail-never': 0, 'fail-onfail': 0}; seen_pods = set(); tdone = {}
while time.time() - t0 < 120:
    for nm in ('fail-never', 'fail-onfail'):
        ps = jpods(nm); podsn[nm] = max(podsn[nm], len(ps))
        for p in ps:
            seen_pods.add((nm, p['metadata']['name']))
            if nm == 'fail-onfail': maxrc = max(maxrc, p['status'].get('containerStatuses', [{}])[0].get('restartCount', 0) or 0)
        if nm not in tdone and any(c['type'] == 'Failed' for c in jstat(nm).get('conditions', [])): tdone[nm] = time.time() - t0
    if len(tdone) == 2: break
    time.sleep(1)
ps = sorted(jpods('fail-never'), key=lambda p: p['metadata']['creationTimestamp']); j = jstat('fail-never'); fc = [c for c in j['conditions'] if c['type'] == 'Failed'][0]
cr = [ts(p['metadata']['creationTimestamp']) - ts(ps[0]['metadata']['creationTimestamp']) for p in ps]
print(f'  fail-never(backoffLimit 2,restartPolicy: Never):每次失败都新建一个 Pod:共 {len(ps)} 个 Pod,创建时刻(相对第一个){[round(x) for x in cr]} 秒(间隔 10 秒、20 秒的指数退避);status.failed={j.get("failed")};{tdone["fail-never"]:.0f} 秒时 Failed:reason={fc["reason"]} message={fc["message"]}')
j = jstat('fail-onfail'); fc = [c for c in j['conditions'] if c['type'] == 'Failed'][0]
print(f'  fail-onfail(backoffLimit 2,restartPolicy: OnFailure):始终只有 {podsn["fail-onfail"]} 个 Pod,容器在原地重启,轮询到的最大 restartCount={maxrc};{tdone["fail-onfail"]:.0f} 秒时 Failed:reason={fc["reason"]};失败后 Pod 数 {len(jpods("fail-onfail"))}(Job 失败时把 Pod 删除了);status.failed={j.get("failed")}')
k('delete', 'job', 'fail-never', 'fail-onfail', '-n', NS, '--wait=true', timeout=60)

print('== 三:activeDeadlineSeconds——整个 Job 的时间上限')
t0 = time.time(); k('apply', '-f', '-', input=job('dl', '  activeDeadlineSeconds: 8\n', 'sleep 60'))
v, dt = until(lambda: any(c['type'] == 'Failed' for c in jstat('dl').get('conditions', [])), 40, 0.3)
j = jstat('dl'); fc = [c for c in j['conditions'] if c['type'] == 'Failed'][0]
print(f'  activeDeadlineSeconds=8、容器 sleep 60:{dt:.1f} 秒后 Job 条件 Failed reason={fc["reason"]} message={fc["message"]};active={j.get("active", 0)};Pod:{[(p["metadata"]["name"][-5:], p["status"]["phase"], bool(p["metadata"].get("deletionTimestamp"))) for p in jpods("dl")] or "(已被删除)"}')
k('delete', 'job', 'dl', '-n', NS, '--wait=true', timeout=60)

print('== 四:suspend 与 ttlSecondsAfterFinished')
k('apply', '-f', '-', input=job('sus', '  suspend: true\n  ttlSecondsAfterFinished: 8\n', 'sleep 2; echo ok')); time.sleep(4)
j = jstat('sus'); print(f'  suspend: true 创建 4 秒后:Pod 数 {len(jpods("sus"))};conditions={[(c["type"], c["status"], c.get("reason")) for c in j.get("conditions", [])]}')
t1 = time.time(); k('patch', 'job', 'sus', '-n', NS, '--type=merge', '-p', '{"spec":{"suspend":false}}')
v, dt = until(lambda: any(c['type'] == 'Complete' for c in jstat('sus').get('conditions', [])), 30, 0.3); print(f'  取消暂停之后 {dt:.1f} 秒 Job Complete;Pod 数 {len(jpods("sus"))}')
t2 = time.time(); v, dt2 = until(lambda: not kj('get', 'job', 'sus', '-n', NS), 40, 0.5); dt2 = dt2 + dt - dt
print(f'  ttlSecondsAfterFinished=8:Complete 之后 {dt2:.1f} 秒 Job 与它的 Pod 被自动删除:Job {"已删除" if v else "仍在"};剩余 Pod {len(kj("get", "pods", "-n", NS, "-l", "job-name=sus")["items"])} 个')
rmns(NS)
