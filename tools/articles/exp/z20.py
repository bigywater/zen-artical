import sys, os, time, json, re, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
from kazoo.exceptions import *
tee('z20'); R = {}
n = Node('z20', 7300).start(); px = Proxy(7390, 7300).start()
z = client('127.0.0.1:7390', timeout=10); adm = client('127.0.0.1:7300')
def lost_response(fn):
    """请求发出、服务端执行了,但响应在回来的路上丢了(代理丢弃 + 断开连接)。返回客户端看到的异常。"""
    box = {}
    px.drop_resp = True
    def call():
        try: box['r'] = fn()
        except Exception as e: box['e'] = e
    t = threading.Thread(target=call); t.start(); time.sleep(0.4); px.close_all(); px.drop_resp = False; t.join(15)
    time.sleep(1.5); return box
print('== 一:创建普通节点:响应丢失后客户端看到 ConnectionLoss;重试 → NodeExists(其实第一次已经成功了)')
box = lost_response(lambda: z.create('/job', b'v1', ephemeral=False))
print('  第一次调用客户端看到:', type(box.get('e')).__name__, '| 服务端实际有 /job:', adm.exists('/job') is not None)
try: z.create('/job', b'v1'); r = '成功'
except Exception as e: r = type(e).__name__
print('  客户端重试 create → ', r); R['create'] = dict(first=type(box.get('e')).__name__, exists=adm.exists('/job') is not None, retry=r)
print()
print('== 二:顺序节点:响应丢失后重试,会创建出第二个节点(没有幂等性)')
adm.create('/seq', b'')
box = lost_response(lambda: z.create('/seq/task-', b'', sequence=True))
print('  第一次调用客户端看到:', type(box.get('e')).__name__, '| 服务端此时 /seq 的子节点:', sorted(adm.get_children('/seq')))
z.create('/seq/task-', b'', sequence=True); kids = sorted(adm.get_children('/seq')); print('  客户端重试 create(sequence) 之后:', kids); R['seq'] = dict(after_first=1, kids=kids)
print()
print('== 三:带版本号的 set:重试得到 BadVersion(第一次已经把版本推进了)')
adm.create('/ver', b'a'); v = adm.get('/ver')[1].version
box = lost_response(lambda: z.set('/ver', b'b', version=v))
print('  第一次调用客户端看到:', type(box.get('e')).__name__, '| 服务端数据:', adm.get('/ver')[0], ' version:', adm.get('/ver')[1].version)
try: z.set('/ver', b'b', version=v); r = '成功'
except Exception as e: r = type(e).__name__
print('  客户端用同一个 version 重试 set →', r); R['set'] = dict(retry=r)
print()
print('== 四:delete:重试得到 NoNode')
adm.create('/gone', b'x')
box = lost_response(lambda: z.delete('/gone'))
print('  第一次调用客户端看到:', type(box.get('e')).__name__, '| 服务端已删除:', adm.exists('/gone') is None)
try: z.delete('/gone'); r = '成功'
except Exception as e: r = type(e).__name__
print('  客户端重试 delete →', r); R['delete'] = dict(retry=r)
print()
print('== 五:不带版本的 set(覆盖写):重试是安全的,结果一样')
adm.create('/ow', b'a')
box = lost_response(lambda: z.set('/ow', b'z'))
print('  第一次调用客户端看到:', type(box.get('e')).__name__, '| 服务端数据:', adm.get('/ow')[0]); z.set('/ow', b'z'); print('  重试后数据:', adm.get('/ow')[0], '| version =', adm.get('/ow')[1].version, '(被写了两次,版本号 +2)'); R['ow'] = adm.get('/ow')[1].version
z.stop(); adm.stop(); px.stop(); n.stop(); save('z20', R)
