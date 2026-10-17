import sys, os, time, json, re, threading, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z46'); R = {}
e = Ensemble('z46', 3, base=7300, conf={'tickTime': 500, 'syncLimit': 2, 'initLimit': 4}).start(); ld = e.leader(); f = e.followers()[0]
print('== 一:follower 被暂停(SIGSTOP)超过 syncLimit × tickTime(2 × 500 ms = 1 s):leader 什么时候判定它掉线?(每 100 ms 读一次 leader 的 zk_synced_followers)')
def tod(): n = datetime.datetime.now(); return n.hour * 3600 + n.minute * 60 + n.second + n.microsecond / 1e6
tl = []; stop = threading.Event()
def poll():
    last = None
    while not stop.is_set():
        try: v = kv(ld.four('mntr')).get('zk_synced_followers')
        except Exception: v = None
        if v != last: tl.append((time.perf_counter(), v)); last = v
        time.sleep(0.05)
th = threading.Thread(target=poll); th.start(); time.sleep(1)
nb = len(ld.log().splitlines()); t0 = time.perf_counter(); f.pause(); time.sleep(5); t1 = time.perf_counter(); f.resume(); time.sleep(4); stop.set(); th.join()
for t, v in tl: print(f'  +{(t - t0) * 1000:>6.0f} ms  leader 的 zk_synced_followers = {v}')
down = next(((t - t0) * 1000 for t, v in tl if v == '1' and t > t0), None); back = next(((t - t1) * 1000 for t, v in tl if v == '2' and t > t1), None)
print(f'  → 暂停后 {down:.0f} ms leader 判定该 follower 掉线(syncLimit × tickTime = 1000 ms);恢复后 {back:.0f} ms 重新同步完成' if down and back else '  (没有观察到)'); R['down_ms'] = down; R['back_ms'] = back
print()
print('== 二:leader 日志里的证据(暂停与恢复期间)')
L = [re.sub(r'^\S+ \[.*?\] \w+\s+\S+ - ', '', l)[:150] for l in ld.log().splitlines()[nb:] if 'LearnerHandler' in l or 'sid' in l.lower()][:6]
for l in L: print('  ', l)
R['log'] = L
print()
print('== 三:暂停时间短于 syncLimit × tickTime(0.5 s):follower 不会被判定掉线')
nb = len(ld.log().splitlines()); f.pause(); time.sleep(0.5); f.resume(); time.sleep(2)
print('  暂停 0.5 s 后 synced_followers =', kv(ld.four('mntr')).get('zk_synced_followers'), '| follower Mode =', f.mode()); R['short'] = kv(ld.four('mntr')).get('zk_synced_followers')
e.stop(); save('z46', R)
