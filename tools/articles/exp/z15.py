import sys, os, time, json, re, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z15'); R = {}
n = Node('z15', 7300).start(); z = client('127.0.0.1:7300'); w = client('127.0.0.1:7300')
EV = []
def cb(tag): return lambda e: EV.append((tag, e.type, e.state, e.path))
def run(label, setup, action):
    EV.clear(); setup(); action(); time.sleep(0.3)
    got = [(t, str(ty), p) for t, ty, st, p in EV]; print(f'  {label:<44} → {got or "没有事件"}'); return got
print('== 一:三种 watch 的触发矩阵(w 注册 watch,z 做修改)。事件只带 type / state / path,不带数据')
rows = {}
z.ensure_path('/m')
def mk(p, v=b'1'): z.create(p, v)
rows['data/set'] = run('get(/m/a, watch) 然后 set /m/a', lambda: (mk('/m/a'), w.get('/m/a', watch=cb('data'))), lambda: z.set('/m/a', b'2'))
rows['data/delete'] = run('get(/m/a2, watch) 然后 delete /m/a2', lambda: (mk('/m/a2'), w.get('/m/a2', watch=cb('data'))), lambda: z.delete('/m/a2'))
rows['exists/create'] = run('exists(/m/b, watch) 然后 create /m/b', lambda: w.exists('/m/b', watch=cb('exists')), lambda: mk('/m/b'))
rows['exists/set'] = run('exists(/m/b, watch) 然后 set /m/b', lambda: w.exists('/m/b', watch=cb('exists')), lambda: z.set('/m/b', b'3'))
rows['child/create'] = run('get_children(/m/p1, watch) 然后 create /m/p1/c', lambda: (z.ensure_path('/m/p1'), w.get_children('/m/p1', watch=cb('child'))), lambda: mk('/m/p1/c', b''))
rows['child/setchild'] = run('get_children(/m/p1, watch) 然后 set /m/p1/c', lambda: w.get_children('/m/p1', watch=cb('child')), lambda: z.set('/m/p1/c', b'x'))
rows['child/delchild'] = run('get_children(/m/p2, watch) 然后 delete /m/p2/c', lambda: (z.ensure_path('/m/p2'), mk('/m/p2/c', b''), w.get_children('/m/p2', watch=cb('child'))), lambda: z.delete('/m/p2/c'))
rows['child/deleteself'] = run('get_children(/m/p3, watch) 然后 delete /m/p3 本身', lambda: (z.ensure_path('/m/p3'), w.get_children('/m/p3', watch=cb('child'))), lambda: z.delete('/m/p3'))
rows['dataparent/createchild'] = run('get(/m/q, watch) 然后 create /m/q/c(父节点数据 watch)', lambda: (z.ensure_path('/m/q'), w.get('/m/q', watch=cb('data'))), lambda: mk('/m/q/c', b''))
R['rows'] = rows
print()
print('== 二:事件里没有新数据:收到 NodeDataChanged 后必须再 get 一次(并且要重新注册 watch)')
got = []; z.create('/n', b'v1'); w.get('/n', watch=lambda e: got.append(e))
z.set('/n', b'v2'); time.sleep(0.3); e = got[0]
print('  事件对象的字段:', {k: str(getattr(e, k)) for k in ('type', 'state', 'path')}, '| 有数据字段吗:', hasattr(e, 'data')); print('  事件之后再 get(/n) 拿到:', w.get('/n')[0])
R['event_fields'] = dict(type=str(e.type), path=e.path)
print()
print('== 三:没有重新注册就不会再有通知:set 两次,只收到第一次')
got = []; z.create('/o', b'0'); w.get('/o', watch=lambda e: got.append(str(e.type)))
z.set('/o', b'1'); z.set('/o', b'2'); z.set('/o', b'3'); time.sleep(0.4); print('  连续 3 次 set 之后收到的事件数:', len(got), got); R['once'] = len(got)
z.stop(); w.stop(); n.stop(); save('z15', R)
