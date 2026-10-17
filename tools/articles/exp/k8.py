import sys, os, re, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k8')
cn, _ = up('main')
NS = ns('k8')
P = f'/api/v1/namespaces/{NS}/configmaps'
rv = lambda n: ko('get', 'cm', n, '-n', NS, '-o', 'jsonpath={.metadata.resourceVersion}')
k('create', 'cm', 'quiet', '-n', NS, '--from-literal=v=1'); k('create', 'cm', 'noise', '-n', NS, '--from-literal=i=0')
r_q = rv('quiet')
print(f'集群 {cn};{NS} 里有两个 ConfigMap:quiet(不再修改,resourceVersion={r_q})和 noise(被疯狂修改)')

print('== 一:watch 一个“安静”的对象,同时在别处持续写入——有无 allowWatchBookmarks 的区别')
sel = f'fieldSelector=metadata.name%3Dquiet'
w_bm = WatchBg(f'{P}?{sel}&resourceVersion={r_q}&allowWatchBookmarks=true', secs=290)
w_no = WatchBg(f'{P}?{sel}&resourceVersion={r_q}', secs=290)
time.sleep(1)
t0 = time.time(); total = 0; exp_info = None
while time.time() - t0 < 240 and not exp_info:
    burst(1000, NS, 'noise'); total += 1000
    ev = watch_events(f'{P}?{sel}&resourceVersion={r_q}', secs=2)
    if ev and ev[0][0] == 'ERROR': exp_info = (time.time() - t0, total, ev[0][3]['object'].get('message'))
if not exp_info: print('  (240 秒内没有等到 410)')
bm_now = [e for e in w_bm.events if e[1] == 'BOOKMARK']
last_now = bm_now[-1][3] if bm_now else None
if exp_info: 
    ev2 = watch_events(f'{P}?{sel}&resourceVersion={last_now}', secs=2) if last_now else []
    ok2 = bool(ev2) and ev2[0][0] == 'ERROR'
    res2 = '成功,没有 410' if not ok2 else f'失败 {ev2[0][3]["object"].get("message")}'
    age = time.time() - t0 - bm_now[-1][0]
t_end = time.time() - t0
w_bm.p.terminate(); w_no.p.terminate(); time.sleep(0.5)
print(f'  持续在 noise 上写入,共 {total} 次,{t_end:.0f} 秒;quiet 自己一次都没有变过')
print(f'  不带 allowWatchBookmarks 的 watcher:收到 {len(w_no.events)} 个事件(它所知道的最后版本一直是 {r_q})')
print(f'  带 allowWatchBookmarks=true 的 watcher:收到 {len(w_bm.events)} 个事件,全是 BOOKMARK:')
for t, ty, n, r, e in w_bm.events: print(f'    第 {t:>5.1f} 秒 {ty} resourceVersion={r}')
if w_bm.events: print('  一个 BOOKMARK 事件的原文:' + json.dumps(w_bm.events[0][4], ensure_ascii=False))

print('== 二:断线重连——从 quiet 最后一次真正变化的版本重连 vs 从最近一个 BOOKMARK 的版本重连')
if exp_info:
    print(f'  写到第 {exp_info[1]} 次({exp_info[0]:.0f} 秒)时,从 quiet 最后一次变化的版本 rv={r_q} 重连:ERROR 410,{exp_info[2]}')
    print(f'  同一时刻,从最近收到的 BOOKMARK(rv={last_now},是 {age:.0f} 秒前收到的)重连:{res2}')
cur = json.loads(ko('get', '--raw', f'{P}?fieldSelector=metadata.name%3Dquiet'))['metadata']['resourceVersion']
print(f'  没有 bookmark 的客户端遇到 410 只能重新 list:得到 resourceVersion={cur}')
rmns(NS)
