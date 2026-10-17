import sys, os, time, json, re, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z9'); R = {}
n = Node('z9', 7300).start(); z = client('127.0.0.1:7300')
print('== 一:顺序节点的名字:路径前缀 + 10 位十进制、左补零的序号')
z.create('/q', b''); names = [z.create('/q/item-', b'', sequence=True) for _ in range(3)]
print('  ', names); R['names'] = names
print()
print('== 二:序号是父节点下的计数:删除子节点后,删掉的序号不会被重用,新序号也没有倒退')
s0 = z.get('/q')[1]; print('  现在 /q 的 cversion =', s0.cversion, ', 子节点:', sorted(z.get_children('/q')))
z.delete('/q/item-0000000000'); z.delete('/q/item-0000000001')
s1 = z.get('/q')[1]; print('  删掉 2 个之后 cversion =', s1.cversion, ', 子节点:', sorted(z.get_children('/q')))
nxt = z.create('/q/item-', b'', sequence=True); print('  再创建一个顺序节点 →', nxt, ' | 创建后 cversion =', z.get('/q')[1].cversion)
R['cversion'] = dict(before=s0.cversion, after_delete=s1.cversion, next=nxt)
z.create('/s', b''); a1 = z.create('/s/n-', b'', sequence=True); z.create('/s/plain', b''); a2 = z.create('/s/n-', b'', sequence=True); z.delete('/s/plain'); a3 = z.create('/s/n-', b'', sequence=True)
print('  对照实验:/s 下 顺序 → 普通子节点 → 顺序 → 删掉普通子节点 → 顺序:', [a.rsplit('/', 1)[1] for a in (a1, a2, a3)], '| 此时 /s 的 cversion =', z.get('/s')[1].cversion)
R['control'] = [a1, a2, a3]
print()
print('== 三:不同父节点各有自己的计数;根下直接创建的顺序节点也一样')
z.create('/r', b''); a = z.create('/r/x-', b'', sequence=True); b = z.create('/q/x-', b'', sequence=True); c = z.create('/x-', b'', sequence=True)
print('  /r 下:', a, '| /q 下:', b, '| / 下:', c); R['per_parent'] = [a, b, c]
print()
print('== 四:并发:8 个客户端线程各创建 50 个顺序节点(共 400 个):序号唯一、连续吗')
z.create('/c', b''); lock = threading.Lock(); got = []
def work():
    w = client('127.0.0.1:7300')
    mine = [w.create('/c/n-', b'', sequence=True) for _ in range(50)]
    with lock: got.extend(mine)
    w.stop()
ts = [threading.Thread(target=work) for _ in range(8)]; [t.start() for t in ts]; [t.join() for t in ts]
seqs = sorted(int(x.rsplit('-', 1)[1]) for x in got)
print('  总数', len(got), '| 不同序号数', len(set(seqs)), '| 最小', seqs[0], '最大', seqs[-1], '| 恰好是 0..399:', seqs == list(range(400))); R['conc'] = dict(n=len(got), uniq=len(set(seqs)), exact=seqs == list(range(400)))
print()
print('== 五:临时顺序节点(分布式锁的基础):同一个客户端的两个、另一个客户端的一个')
w = client('127.0.0.1:7300'); z.create('/lk', b'')
p1 = z.create('/lk/l-', b'', ephemeral=True, sequence=True); p2 = w.create('/lk/l-', b'', ephemeral=True, sequence=True); p3 = z.create('/lk/l-', b'', ephemeral=True, sequence=True)
print('  创建顺序:z → w → z;得到:', [p.rsplit('/', 1)[1] for p in (p1, p2, p3)]); print('  /lk 的子节点排序:', sorted(z.get_children('/lk')))
w.stop(); time.sleep(0.5); print('  w 的会话关闭后:', sorted(z.get_children('/lk')), '(序号不连续,w 的那个没了)'); R['eph_seq'] = sorted(z.get_children('/lk'))
z.stop(); n.stop(); save('z9', R)
