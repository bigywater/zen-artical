import sys, os, re, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k29')
cn, _ = up('main')
NS = ns('k29')
def mk(name, grace, cmd, extra=''):
    return f'''apiVersion: v1
kind: Pod
metadata: {{name: {name}, namespace: {NS}}}
spec:
{('  terminationGracePeriodSeconds: %s' % grace) + chr(10) if grace is not None else ''}  containers:
  - name: c
    image: busybox:1.36
    command: [sh, -c, "{cmd}"]
'''
def timed_delete(name, *extra):
    until(lambda: (kj('get', 'pod', name, '-n', NS) or {}).get('status', {}).get('phase') == 'Running', 60); time.sleep(1.5)
    t0 = time.time(); k('delete', 'pod', name, '-n', NS, '--wait=true', *extra, timeout=120); return time.time() - t0
print(f'集群 {cn};kubectl delete 之后:SIGTERM → 等 terminationGracePeriodSeconds → SIGKILL;1 号进程如何对待 SIGTERM 决定了你实际要等多久')

print('== 一:1 号进程不处理 SIGTERM——一直等到宽限期结束被 SIGKILL')
res = {}
for g in (3, 8):
    k('apply', '-f', '-', input=mk(f'ign{g}', g, 'sleep 3600'))
    res[g] = timed_delete(f'ign{g}')
    print(f'  terminationGracePeriodSeconds={g},命令 sh -c "sleep 3600"(busybox 的 sleep 是 shell 内置,不 fork,1 号进程就是 sh 自己,没有 SIGTERM 处理函数):从 kubectl delete 到 Pod 消失 {res[g]:.1f} 秒')
k('apply', '-f', '-', input=mk('exec3', 3, 'exec sleep 3600'))
d = timed_delete('exec3'); print(f'  同样的宽限期 3 秒,但命令是 exec sleep 3600(sleep 本身是 1 号进程,同样没有处理函数):{d:.1f} 秒——Linux 不会因为一个没有处理函数的 SIGTERM 终止 1 号进程,所以都要等满宽限期')

print('== 二:应用自己处理 SIGTERM——收到就退出,不用等宽限期')
k('apply', '-f', '-', input=mk('handler', 30, "trap 'exit 0' TERM; while true; do sleep 1; done"))
d = timed_delete('handler'); print(f'  宽限期 30 秒,sh 里 trap exit 0 TERM、循环 sleep 1:从 kubectl delete 到 Pod 消失 {d:.1f} 秒(sh 要等当前的 sleep 1 结束才处理信号)')
k('apply', '-f', '-', input=mk('handler2', 30, "trap 'exit 0' TERM; sleep 3600 & wait"))
d = timed_delete('handler2'); print(f'  trap exit 0 TERM; sleep 3600 & wait(wait 会被信号立即打断):{d:.1f} 秒')

print('== 三:宽限期可以在删除时覆盖,也可以是 0')
k('apply', '-f', '-', input=mk('over', 60, 'sleep 3600'))
d = timed_delete('over', '--grace-period=2'); print(f'  Pod 里写的 terminationGracePeriodSeconds=60,kubectl delete --grace-period=2:{d:.1f} 秒')
k('apply', '-f', '-', input=mk('zero', 60, 'sleep 3600'))
d = timed_delete('zero', '--grace-period=0', '--force'); print(f'  --grace-period=0 --force:{d:.1f} 秒(API 对象立即删除)')
k('apply', '-f', '-', input=mk('spec0', 0, 'sleep 3600'))
d = timed_delete('spec0'); print(f'  spec.terminationGracePeriodSeconds=0:{d:.1f} 秒')
k('apply', '-f', '-', input=mk('default', None, 'sleep 3600'))
p = kj('get', 'pod', 'default', '-n', NS); print(f'  不写 terminationGracePeriodSeconds 时服务端补上的默认值:{p["spec"]["terminationGracePeriodSeconds"]}')
d = timed_delete('default'); print(f'  按默认值删除一个不处理 SIGTERM 的 Pod(sh -c sleep 3600):{d:.1f} 秒')

print('== 四:sh -c 包一层的陷阱——SIGTERM 发给 1 号进程,到不了它的子进程')
for n_, cmd, desc in (('wrap', 'tail -f /dev/null; echo done', '没有转发:sh 作 1 号进程,tail 是它的子进程'), ('fwd', 'tail -f /dev/null & c=$!; trap \'kill $c\' TERM; wait $c; echo done', '转发:sh 的 trap 把信号转给 tail')):
    k('apply', '-f', '-', input=mk(n_, 5, cmd))
    until(lambda: (kj('get', 'pod', n_, '-n', NS) or {}).get('status', {}).get('phase') == 'Running', 60); time.sleep(1.5)
    rc, o = k('exec', n_, '-n', NS, '--', 'ps', '-o', 'pid,args'); procs = [' '.join(l.split()[:1] + l.split()[1:])[:70] for l in o.splitlines()[1:] if 'ps -o' not in l]
    t0 = time.time(); k('delete', 'pod', n_, '-n', NS, '--wait=true', timeout=60); d = time.time() - t0
    print(f'  {desc}:容器里的进程 {procs};terminationGracePeriodSeconds=5,删除用了 {d:.1f} 秒')
rmns(NS)
