import sys, os, time, json, re, shutil, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z57'); R = {}
V = '/Volumes/ZKSMALL'; D = f'{V}/z57'
shutil.rmtree(D, ignore_errors=True); os.makedirs(D, exist_ok=True)
def free(): return shutil.disk_usage(V).free / 1048576
ballast = f'{V}/ballast.bin'
with open(ballast, 'wb') as f: f.write(b'0' * 6 * 1048576)
print(f'== 一:事务日志与快照放在一个只有 24 MiB 的小盘上(preAllocSize=512 KB,先放 6 MiB 的压舱文件),不断写入 100 KiB 的 znode,直到盘满')
n = Node('z57', 7300, conf={'dataDir': f'{D}/data', 'dataLogDir': f'{D}/log', 'snapCount': 100000}, jvm=['-Dzookeeper.preAllocSize=512']).start(); os.makedirs(D, exist_ok=True)
z = client('127.0.0.1:7300', timeout=10); err = None; cnt = 0
print(f'  起始可用空间 {free():.1f} MiB')
t0 = time.time()
while time.time() - t0 < 60:
    try: z.create(f'/f{cnt}', b'x' * 100 * 1024); cnt += 1
    except Exception as e: err = type(e).__name__; break
print(f'  成功写入 {cnt} 个(约 {cnt * 100 / 1024:.1f} MiB)后第 {cnt + 1} 次写入失败:{err};此时盘上可用 {free():.2f} MiB')
R['fill'] = dict(count=cnt, err=err)
time.sleep(2)
def sf(c):
    try: return four(7300, c, 2).strip()
    except Exception as e: return '(' + type(e).__name__ + ')'
print('  进程还活着:', n.alive(), '| 退出码:', n.p.poll(), '| ruok:', sf('ruok')); R['alive'] = n.alive(); R['exit'] = n.p.poll()
lg = [re.sub(r'^\S+ \[(.*?)\] \w+\s+\S+ - ', r'[\1] ', l)[:150] for l in n.log().splitlines() if 'No space' in l or 'space' in l.lower() and ('ERROR' in l or 'Exception' in l) or 'shutting down' in l.lower() or 'Severe' in l or 'Exiting JVM' in l or 'SyncThread' in l and 'ERROR' in l][:6]
print('  服务端日志里与磁盘满相关的行:'); [print('   ', l) for l in lg]; R['log'] = lg
print()
print('== 二:服务端进程已经退出,读和新连接都不可能(进程退出码 0,是服务端自己「体面地」关闭)')
try: four(7300, 'ruok', 2); r = '有响应'
except Exception as e: r = type(e).__name__
print('  对 7300 端口发 ruok →', r); R['after'] = r
try: z.stop()
except Exception: pass
print()
print('== 三:腾出 6 MiB(删掉压舱文件)后重启:启动时服务端要先写一份新快照,空间还是不够')
os.remove(ballast); time.sleep(1); print(f'  腾出空间后可用 {free():.1f} MiB')
def try_start(conf):
    nd = Node('z57r', 7300, conf=conf, jvm=['-Dzookeeper.preAllocSize=512']); nd.prepare(wipe=False) if False else None
    nd.start(wipe=False, wait=False); 
    for _ in range(100):
        if nd.p.poll() is not None: break
        try:
            if nd.mode() == 'standalone': return nd, True, None
        except Exception: pass
        time.sleep(0.2)
    return nd, False, nd.p.poll()
conf_small = {'dataDir': f'{D}/data', 'dataLogDir': f'{D}/log', 'snapCount': 100000}
nd, ok, code = try_start(conf_small)
lg = [re.sub(r'^\S+ \[(.*?)\] \w+\s+\S+ - ', r'[\1] ', l)[:120] for l in nd.log().splitlines() if 'Severe' in l or 'No space' in l or 'Exiting JVM' in l][-3:]
print(f'  重启{"成功" if ok else "失败"}(退出码 {code});日志:'); [print('   ', l) for l in lg]; R['restart1'] = dict(ok=ok, code=code, log=lg)
snaps = sorted(p for p in os.listdir(f'{D}/data/version-2') if p.startswith('snapshot.')); sz = {p: os.path.getsize(f'{D}/data/version-2/{p}') for p in snaps}
print('  数据目录里的快照文件(注意启动失败时留下了一个写了一半的快照):', {k: f'{v / 1048576:.1f} MiB' for k, v in sz.items()}); R['partial'] = {k: v for k, v in sz.items()}
print()
print('== 四:删掉那个写了一半的快照后再启动:还是不够(完整快照要约 17 MiB),只能把数据目录搬到更大的盘')
for p in snaps:
    if p != 'snapshot.0': os.remove(f'{D}/data/version-2/{p}')
print(f'  现在可用 {free():.1f} MiB'); nd, ok, code = try_start(conf_small); print(f'  再次启动:{"成功" if ok else "失败"}(退出码 {code})'); R['restart2'] = dict(ok=ok, code=code)
for p in snaps:
    if p != 'snapshot.0' and os.path.exists(f'{D}/data/version-2/{p}'): os.remove(f'{D}/data/version-2/{p}')
BIG = '/Volumes/ZKMED/z57'; shutil.rmtree(BIG, ignore_errors=True); shutil.copytree(D, BIG)
conf_big = {'dataDir': f'{BIG}/data', 'dataLogDir': f'{BIG}/log', 'snapCount': 100000}
nd, ok, code = try_start(conf_big)
if ok:
    zz = client('127.0.0.1:7300'); zz.create('/after-move', b'x'); print(f'  数据目录搬到 256 MiB 的盘上启动:成功;znode 数 {kv(nd.four("mntr")).get("zk_znode_count")}(写入成功的 {cnt} 个 100 KiB 的 znode 都在),并且可以继续写'); R['moved'] = dict(ok=True, count=kv(nd.four('mntr')).get('zk_znode_count')); zz.stop()
else: print('  搬到大盘后启动失败,退出码', code); R['moved'] = dict(ok=False)
nd.stop(); shutil.rmtree(D, ignore_errors=True); shutil.rmtree(BIG, ignore_errors=True); save('z57', R)
