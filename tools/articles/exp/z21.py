import sys, os, time, json, re, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
from kazoo.exceptions import *
tee('z21'); R = {}
n = Node('z21', 7300).start(); z = client('127.0.0.1:7300')
print('== 一:100 次 create:逐个同步 vs 一个 multi(transaction)提交(各重复 5 次取中位数)')
def single(tag):
    z.ensure_path(f'/s{tag}'); t0 = time.perf_counter()
    for i in range(100): z.create(f'/s{tag}/n{i}', b'x' * 50)
    return (time.perf_counter() - t0) * 1000
def multi(tag):
    z.ensure_path(f'/m{tag}'); t0 = time.perf_counter(); t = z.transaction()
    for i in range(100): t.create(f'/m{tag}/n{i}', b'x' * 50)
    t.commit(); return (time.perf_counter() - t0) * 1000
a = statistics.median(single(i) for i in range(5)); b = statistics.median(multi(i) for i in range(5))
print(f'  逐个 create 100 次:{a:7.1f} ms({a / 100:.2f} ms/个)'); print(f'  一个 multi 含 100 个 create:{b:7.1f} ms({b / 100:.2f} ms/个)  → 快 {a / b:.0f} 倍'); R['speed'] = dict(single=a, multi=b)
print()
print('== 二:原子性:multi 里有一个操作失败,全部回滚')
z.create('/at', b'')
t = z.transaction(); t.create('/at/a', b'1'); t.create('/at/b', b'2'); t.create('/at/a', b'dup'); t.create('/at/c', b'3')
try: r = t.commit(); print('  commit 返回', r)
except RolledBackError as e: print('  commit 抛出 RolledBackError')
r = t.commit() if False else None
print('  之后 /at 的子节点:', z.get_children('/at'), '(a、b 也没有被创建)')
t = z.transaction(); t.create('/at/a', b'1'); t.create('/at/a', b'dup'); res = t.commit(); print('  不抛异常的写法 commit() 返回的结果列表:', [type(x).__name__ if isinstance(x, Exception) else x for x in res]); R['atomic'] = [type(x).__name__ if isinstance(x, Exception) else x for x in res]
print()
print('== 三:一个 multi 里的所有操作共用同一个 zxid(它们是一个事务)')
z.ensure_path('/zx'); t = z.transaction()
for i in range(5): t.create(f'/zx/n{i}', b'')
t.commit(); zs = [z.get(f'/zx/n{i}')[1].czxid for i in range(5)]; print('  5 个 create 的 czxid:', [hex(x) for x in zs], '全部相同:', len(set(zs)) == 1); R['zxid_same'] = len(set(zs)) == 1
print()
print('== 四:check 操作:用 multi 实现「版本没变才写」的跨节点一致性')
z.create('/cfg', b'v1'); ver = z.get('/cfg')[1].version
t = z.transaction(); t.check('/cfg', ver); t.create('/derived', b'based-on-v1'); print('  版本一致时 commit →', [type(x).__name__ if isinstance(x, Exception) else x for x in t.commit()])
z.set('/cfg', b'v2'); t = z.transaction(); t.check('/cfg', ver); t.create('/derived2', b'based-on-v1'); res = t.commit(); print('  /cfg 被改过之后 commit →', [type(x).__name__ if isinstance(x, Exception) else x for x in res], '| /derived2 存在:', z.exists('/derived2') is not None); R['check'] = [type(x).__name__ if isinstance(x, Exception) else x for x in res]
print()
print('== 五:multi 也受 1 MiB 的请求大小限制')
t = z.transaction()
for i in range(30): t.create(f'/big{i}', b'x' * 50000)
try: t.commit(); r = '成功'
except Exception as e: r = type(e).__name__
print(f'  30 个各 50000 字节的 create(合计约 1.5 MiB)一次提交 → {r}'); R['big'] = r
z.stop(); n.stop(); save('z21', R)
