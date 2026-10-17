import sys, os, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
from pymongo import ReadPreference
from pymongo.write_concern import WriteConcern
from pymongo.errors import PyMongoError
tee('m63'); reset()
def run_scenario(name, action, retry, election_ms=None, secs=22, setup_settings=None):
    rs = ReplSet(name, 3, settings=({'electionTimeoutMillis': election_ms} if election_ms else None)).start(); rs.wait_secondaries()
    pi = rs.wait_primary(); pri = rs.nodes[pi]
    c = MongoClient(rs.uri(), replicaSet=rs.rs, retryWrites=retry, w='majority', serverSelectionTimeoutMS=30000); db = c.test
    db.t.insert_one({'_id': -1}); log = []; errs = []; stop = threading.Event(); acked = []
    def writer():
        i = 0
        while not stop.is_set():
            t0 = time.time()
            try: db.t.insert_one({'_id': i}); acked.append(i); log.append((t0, time.time(), True))
            except PyMongoError as e: errs.append((round(t0 - T0, 1), type(e).__name__)); log.append((t0, time.time(), False))
            i += 1; time.sleep(0.005)
    T0 = time.time(); wt = threading.Thread(target=writer); wt.start(); time.sleep(3); t_act = time.time()
    action(rs, pri); time.sleep(secs); stop.set(); wt.join()
    ok = [l for l in log if l[2]]; gaps = [(ok[i + 1][1] - ok[i][1], ok[i][1]) for i in range(len(ok) - 1)]
    base = sorted(g[0] for g in gaps if g[1] < t_act)
    after = [g for g in gaps if g[1] >= t_act - 0.5]
    mg = max(after, key=lambda x: x[0]) if after else (0, 0)
    time.sleep(1)
    new_c = rs.client(); final = {d['_id'] for d in new_c.test.t.find({'_id': {'$gte': 0}}, {'_id': 1})}
    lost = [a for a in acked if a not in final]
    res = dict(gap=mg[0], base=base[len(base) // 2] if base else 0, start=mg[1] - T0, errs=len(errs), kinds={k: sum(1 for e in errs if e[1] == k) for k in set(e[1] for e in errs)}, acked=len(acked), lost=len(lost), n_ok=len(ok), t_act=t_act - T0)
    rs.stop(); return res
print('== 一:三种切主方式下,一个持续写入(w:majority,每 5 ms 一次)的客户端看到的“不可写时间” = 两次成功写入之间的最大间隔')
print('  方式 A:primary 上执行 replSetStepDown(优雅切主,等 secondary 追平)')
def stepdown(rs, pri): pri.client().admin.command('replSetStepDown', 60, 10)
rA = run_scenario('m63a', stepdown, True)
print(f'    retryWrites=True :动作之后的最大间隔 {rA["gap"]:.2f} s(平时的中位数间隔 {rA["base"] * 1000:.0f} ms);客户端看到的错误 {rA["errs"]} 个 {rA["kinds"]};确认写入 {rA["acked"]} 条,丢失 {rA["lost"]} 条')
rA2 = run_scenario('m63a2', stepdown, False)
print(f'    retryWrites=False:动作之后的最大间隔 {rA2["gap"]:.2f} s;客户端看到的错误 {rA2["errs"]} 个 {rA2["kinds"]};确认写入 {rA2["acked"]} 条,丢失 {rA2["lost"]} 条')
print('  方式 B:kill -9 primary(崩溃,默认 electionTimeoutMillis = 10 s)')
def killp(rs, pri): pri.stop(kill=True)
rB = run_scenario('m63b', killp, True, secs=25)
print(f'    retryWrites=True :动作之后的最大间隔 {rB["gap"]:.2f} s(平时 {rB["base"] * 1000:.0f} ms);错误 {rB["errs"]} 个 {rB["kinds"]};确认写入 {rB["acked"]} 条,丢失 {rB["lost"]} 条')
print('  方式 C:同样 kill -9,但把 electionTimeoutMillis 调成 4000(必须大于心跳间隔 2000)')
rC = run_scenario('m63c', killp, True, election_ms=4000, secs=15)
print(f'    retryWrites=True :动作之后的最大间隔 {rC["gap"]:.2f} s(平时 {rC["base"] * 1000:.0f} ms);错误 {rC["errs"]} 个 {rC["kinds"]};确认写入 {rC["acked"]} 条,丢失 {rC["lost"]} 条')
print('== 二:汇总')
print(f'  {"方式":<36}{"不可写时间":>12}')
for lab_, r_ in [('replSetStepDown(优雅)', rA), ('kill -9,electionTimeoutMillis 10 s', rB), ('kill -9,electionTimeoutMillis 4 s', rC)]: print(f'  {lab_:<36}{r_["gap"]:>10.2f} s')
print('== 三:切主期间 secondary 读不受影响;primary 读偏好的读会失败或等待')
rs = ReplSet('m63d', 3).start(); rs.wait_secondaries(); pi = rs.wait_primary(); pri = rs.nodes[pi]
c = rs.client(); c.test.t.insert_one({'_id': 1})
cs = MongoClient(rs.uri(), replicaSet=rs.rs, read_preference=ReadPreference.SECONDARY, serverSelectionTimeoutMS=15000); cp = MongoClient(rs.uri(), replicaSet=rs.rs, serverSelectionTimeoutMS=15000, retryReads=False)
pri.stop(kill=True); t_kill = time.time()
def reader(cl, out, ms=None):
    while time.time() - t_kill < 14:
        t1 = time.time()
        try: cl.test.t.find_one({'_id': 1}); ok = True
        except PyMongoError: ok = False
        out.append((t1 - t_kill, (time.time() - t1) * 1000, ok)); time.sleep(0.2)
so, po = [], []; th = [threading.Thread(target=reader, args=(cs, so)), threading.Thread(target=reader, args=(cp, po))]; [x.start() for x in th]; [x.join() for x in th]
def summ(o): return f'{len(o)} 次读,失败 {sum(1 for x in o if not x[2])} 次;单次读的最大耗时 {max(x[1] for x in o):.0f} ms;耗时超过 1 s 的读有 {sum(1 for x in o if x[1] > 1000)} 次(最长的一次在 kill 后 {max(o, key=lambda x: x[1])[0]:.1f} s 开始)'
print(f'  primary 被 kill 后的 14 秒里,两个线程每 0.2 秒各读一次:')
print(f'    secondary 读偏好:{summ(so)}')
print(f'    primary 读偏好:  {summ(po)}')
rs.stop()
