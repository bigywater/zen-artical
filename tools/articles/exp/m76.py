import sys, os, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
tee('m76'); reset()
nd = Node('m76', cache=0.25).start(); c = nd.client()
c.test.a.insert_many([{'_id': i, 'k': i % 100, 'p': 'x' * 100} for i in range(20000)], ordered=False)
c.test.b.insert_one({'_id': 1})
stop = threading.Event(); mode = {'m': 'idle'}; done_ops = {'ins': 0, 'qry': 0, 'upd': 0, 'del': 0}
def load():
    cl = nd.client(); i = 100000
    while not stop.is_set():
        t0 = time.time()
        if mode['m'] == 'mixed':
            for _ in range(300): cl.test.a.insert_one({'_id': i, 'k': 1}); i += 1; done_ops['ins'] += 1
            for j in range(100): cl.test.a.find_one({'_id': j}); done_ops['qry'] += 1
            for j in range(50): cl.test.a.update_one({'_id': j}, {'$inc': {'k': 1}}); done_ops['upd'] += 1
            for j in range(20): cl.test.a.delete_one({'_id': i - 1 - j}); done_ops['del'] += 1
        elif mode['m'] == 'bulk':
            cl.test.big.insert_many([{'p': 'z' * 1000, 'i': i + j} for j in range(2000)], ordered=False); i += 2000
        elif mode['m'] == 'sleepers': time.sleep(0.2)
        dt = time.time() - t0
        if mode['m'] == 'mixed' and dt < 1: time.sleep(1 - dt)
        elif mode['m'] == 'idle': time.sleep(0.2)
th = threading.Thread(target=load, daemon=True); th.start()
def run(cmd, n=12, hdr=True):
    shown = cmd.replace(nd.uri, '<mongod>')
    print(f'  $ {shown}')
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, env={'PATH': '/usr/bin:/bin:/opt/homebrew/bin', 'HOME': str(MHOME)})
    ls = [re.sub(r'\s+[A-Z][a-z]{2}\s+\d+\s+\d\d:\d\d:\d\d(\.\d+)?\s*$', '  <时间>', l.rstrip()) for l in tidy(r.stdout + r.stderr).split('\n') if l.strip()]
    ls = [re.sub(r'\d{4}-\d\d-\d\dT[\d:+]+', '<时间>', l) for l in ls]
    ls = [l for l in ls if not l.startswith('Note:') and 'connected to' not in l]
    for l in ls[:n]: print('  ' + l[:190])
    return ls
print('== 一:空闲时的 mongostat(每秒一行,共 3 行):默认列的含义——insert/query/update/delete/getmore/command 是每秒操作数,dirty/used 是 WiredTiger 缓存比例,vsize/res 是内存,qrw/arw 是读写队列和活跃数,net_in/net_out 是每秒网络字节,conn 是连接数')
run(f"mongostat --host 127.0.0.1:{nd.port} --rowcount 3 1")
print('== 二:每秒做已知数量的操作:300 次 insert、100 次 find、50 次 update、20 次 delete(单线程,一秒内做完)。mongostat 的数字和我们做的次数对得上吗?')
mode['m'] = 'mixed'; time.sleep(1.2); d0 = dict(done_ops)
ls = run(f"mongostat --host 127.0.0.1:{nd.port} --rowcount 4 1")
print('  load 线程累计: ' + str({k: v - d0[k] for k, v in done_ops.items()}) + '(4 秒内;一秒大约 300 / 100 / 50 / 20)')
print('== 三:-o 自定义列、--json 输出')
run(f"mongostat --host 127.0.0.1:{nd.port} --rowcount 2 -o 'insert=insert,query=query,update=update,delete=delete,command=command,conn=conn,time=time' 1")
ls = run(f"mongostat --host 127.0.0.1:{nd.port} --rowcount 2 --json 1", n=2)
print('== 四:mongotop:按命名空间看读写占用的时间(毫秒/每个间隔);load 在 test.a 上读写,test.b 几乎不碰')
for i in range(5): c.test.b.find_one({'_id': 1})
run(f"mongotop --host 127.0.0.1:{nd.port} --rowcount 2 1", n=30)
print('== 五:批量写入时 dirty 和 used 列的变化(WiredTiger 缓存 256 MB;一个线程不停地 insert_many,每批 2,000 个约 1 KB 的文档)')
mode['m'] = 'bulk'; time.sleep(0.5)
run(f"mongostat --host 127.0.0.1:{nd.port} --rowcount 4 -o 'insert=insert,dirty=dirty,used=used,flushes=flushes,net_in=net_in,time=time' 1")
mode['m'] = 'idle'; time.sleep(1)
print('== 六:qrw / arw:8 个并发的慢查询($where 里 sleep)正在跑时,活跃读数 arw 是多少')
def slow():
    cl = nd.client()
    try: cl.test.command({'find': 'a', 'filter': {'$where': 'sleep(1000) || true'}, 'limit': 1})
    except Exception as ex: pass
sl = [threading.Thread(target=slow, daemon=True) for _ in range(8)]
for t in sl: t.start()
time.sleep(0.2)
g = c.admin.command('serverStatus'); print('  serverStatus: globalLock.currentQueue = ' + str(dict(g['globalLock']['currentQueue'])) + ',globalLock.activeClients = ' + str(dict(g['globalLock']['activeClients'])))
print('  serverStatus.queues = ' + json.dumps(g.get('queues'), default=str)[:400])
run(f"mongostat --host 127.0.0.1:{nd.port} --rowcount 2 -o 'query=query,qrw=qrw,arw=arw,conn=conn,time=time' 1")
for t in sl: t.join(30)
stop.set(); nd.stop()
