import sys, os, re, time, json, yaml; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k23')
cn, _ = up('main')
NS = ns('k23')
def P(name): return kj('get', 'pod', name, '-n', NS)
def state(p):
    cs = (p['status'].get('containerStatuses') or [{}])[0]; st = cs.get('state', {})
    k_ = next(iter(st), '-'); d = st.get(k_, {}) if k_ != '-' else {}
    return f'{k_}' + (f'({d.get("reason")})' if d.get('reason') else '')
def snap(name):
    p = P(name)
    if not p: return None
    conds = {c['type']: c['status'] for c in p['status'].get('conditions', [])}
    return (p['status'].get('phase'), conds, state(p), p['status'].get('containerStatuses', [{}])[0].get('ready') if p['status'].get('containerStatuses') else None, p['status'].get('containerStatuses', [{}])[0].get('restartCount') if p['status'].get('containerStatuses') else None)
def watch_pod(name, secs, ops=None):
    """每 0.25 秒读一次 Pod,记录 (phase, Initialized, Ready, ContainersReady, PodScheduled, 容器状态) 的变化序列,返回 [(t, 状态元组)]。"""
    seq = []; t0 = time.time(); done_ops = False
    while time.time() - t0 < secs:
        if ops and not done_ops and time.time() - t0 > 0.3: ops(); done_ops = True
        s = snap(name)
        if s is None:
            if not seq or seq[-1][1] != 'NotFound': seq.append((round(time.time() - t0, 1), 'NotFound'))
            break
        c = s[1]; key = (s[0], c.get('PodScheduled'), c.get('Initialized'), c.get('ContainersReady'), c.get('Ready'), s[2])
        if not seq or seq[-1][1] != key: seq.append((round(time.time() - t0, 1), key))
        time.sleep(0.25)
    return seq
def show(seq):
    return '\n'.join('    +%4.1fs phase=%-9s PodScheduled=%-5s Initialized=%-5s ContainersReady=%-5s Ready=%-5s 容器=%s' % ((t,) + k_) if k_ != 'NotFound' else f'    +{t:4.1f}s (Pod 已经不存在)' for t, k_ in seq)
print(f'集群 {cn};Pod 的 status 里有 phase(粗粒度)、conditions(PodScheduled / Initialized / ContainersReady / Ready)和每个容器的 state(Waiting / Running / Terminated)三层信息')

print('== 一:一个正常启动的 Pod——phase、conditions、容器状态各自什么时候变')
k('apply', '-f', '-', input=f'apiVersion: v1\nkind: Pod\nmetadata: {{name: ok, namespace: {NS}}}\nspec:\n  terminationGracePeriodSeconds: 0\n  containers: [{{name: c, image: busybox:1.36, command: [sh, -c, "sleep 3600"], readinessProbe: {{exec: {{command: [sh, -c, "test -f /tmp/ready"]}}, periodSeconds: 1}}}}]\n')
seq = watch_pod('ok', 20, ops=lambda: None)
print('  Pod ok(readinessProbe 检查 /tmp/ready 是否存在,一开始没有这个文件):'); print(show(seq))
k('exec', 'ok', '-n', NS, '--', 'touch', '/tmp/ready'); time.sleep(2.5)
s = snap('ok'); print(f'  在容器里创建 /tmp/ready 之后 2.5 秒:phase={s[0]} Ready={s[1].get("Ready")} ContainersReady={s[1].get("ContainersReady")} 容器 ready={s[3]}')

print('== 二:phase 只有五个取值——Running 不等于 Ready,Pending 里还分好几种')
k('apply', '-f', '-', input=f'apiVersion: v1\nkind: Pod\nmetadata: {{name: nosched, namespace: {NS}}}\nspec:\n  nodeSelector: {{no-such-label: "1"}}\n  containers: [{{name: c, image: busybox:1.36, command: [sleep, "3600"]}}]\n')
k('apply', '-f', '-', input=f'apiVersion: v1\nkind: Pod\nmetadata: {{name: badimg, namespace: {NS}}}\nspec:\n  containers: [{{name: c, image: "busybox:no-such-tag-23"}}]\n')
k('apply', '-f', '-', input=f'apiVersion: v1\nkind: Pod\nmetadata: {{name: oneshot, namespace: {NS}}}\nspec:\n  restartPolicy: Never\n  containers: [{{name: c, image: busybox:1.36, command: [sh, -c, "echo hi"]}}]\n')
k('apply', '-f', '-', input=f'apiVersion: v1\nkind: Pod\nmetadata: {{name: failing, namespace: {NS}}}\nspec:\n  restartPolicy: Never\n  containers: [{{name: c, image: busybox:1.36, command: [sh, -c, "exit 3"]}}]\n')
time.sleep(48)
for n in ('nosched', 'badimg', 'oneshot', 'failing'):
    p = P(n); s = snap(n); cs = (p['status'].get('containerStatuses') or [{}])[0]; st = cs.get('state', {})
    extra = ''
    if n == 'nosched': pc = [c for c in p['status']['conditions'] if c['type'] == 'PodScheduled'][0]; extra = f'PodScheduled={pc["status"]} reason={pc.get("reason")} message={pc.get("message", "")[:80]}'
    elif 'terminated' in st: extra = f'exitCode={st["terminated"]["exitCode"]} reason={st["terminated"]["reason"]}'
    elif 'waiting' in st: extra = f'waiting.reason={st["waiting"].get("reason")}'
    print(f'  {n:<9} phase={s[0]:<10} Ready={s[1].get("Ready")} 容器状态={s[2]};{extra}')
print('  kubectl get pod 的 STATUS 列(和 phase 不是一回事):' + ' | '.join(l.split()[0] + '=' + l.split()[2] for l in k('get', 'pod', '-n', NS)[1].strip().splitlines()[1:]))

print('== 三:删除时的状态——Terminating 并不是 phase')
k('apply', '-f', '-', input=f'apiVersion: v1\nkind: Pod\nmetadata: {{name: slow, namespace: {NS}}}\nspec:\n  terminationGracePeriodSeconds: 20\n  containers: [{{name: c, image: busybox:1.36, command: [sh, -c, "sleep 3600"]}}]\n')
until(lambda: (P('slow') or {}).get('status', {}).get('phase') == 'Running', 60)
k('delete', 'pod', 'slow', '-n', NS, '--wait=false'); time.sleep(1)
p = P('slow')
print(f'  Pod slow(sh -c "sleep 3600" 作为 1 号进程不处理 SIGTERM,terminationGracePeriodSeconds=20)执行 kubectl delete 1 秒后:phase={p["status"]["phase"]};metadata.deletionTimestamp={"有" if p["metadata"].get("deletionTimestamp") else "无"};deletionGracePeriodSeconds={p["metadata"].get("deletionGracePeriodSeconds")};容器状态={state(p)}')
print(f'  kubectl get pod slow 的 STATUS 列:{k("get", "pod", "slow", "-n", NS)[1].strip().splitlines()[-1].split()[2]}')
t0 = time.time(); v, dt = until(lambda: not P('slow'), 40, 0.5)
print(f'  最终在 {dt + 1:.0f} 秒后被 SIGKILL 并消失(Pod 对象被删除)' if v else '  40 秒内没有消失')

print('== 四:容器重启与 restartPolicy——restartCount、lastState 与 phase 的关系')
k('apply', '-f', '-', input=f'apiVersion: v1\nkind: Pod\nmetadata: {{name: flaky, namespace: {NS}}}\nspec:\n  restartPolicy: OnFailure\n  containers: [{{name: c, image: busybox:1.36, command: [sh, -c, "sleep 3; exit 1"]}}]\n')
time.sleep(30)
p = P('flaky'); cs = p['status']['containerStatuses'][0]
print(f'  restartPolicy=OnFailure、容器 3 秒后 exit 1,30 秒后:phase={p["status"]["phase"]} restartCount={cs["restartCount"]} 当前 state={list(cs["state"])[0]} lastState.terminated(exitCode={cs["lastState"]["terminated"]["exitCode"]},reason={cs["lastState"]["terminated"]["reason"]})')
print(f'  Ready={[c["status"] for c in p["status"]["conditions"] if c["type"] == "Ready"][0]}(容器在两次重启之间不就绪);phase 一直是 {p["status"]["phase"]},不会因为反复崩溃变成 Failed')
rmns(NS)
