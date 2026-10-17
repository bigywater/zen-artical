import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z37'); R = {}
def split(h): v = int(h, 16); return v >> 32, v & 0xffffffff
e = Ensemble('z37', 3, base=7300).start(); ld = e.leader(); z = client(e.hosts())
def show(label):
    zs = {nd.name: nd.srvr().get('zxid') for nd in e.nodes if nd.alive()}
    print(f'  {label}:', {k: f'{v} = epoch {split(v)[0]} + counter {split(v)[1]}' for k, v in zs.items()}); return zs
print('== 一:zxid 是一个 64 位数:高 32 位是 epoch(第几任 leader),低 32 位是 counter(这一任 leader 的第几个事务)')
R['start'] = show('刚选出第一任 leader 后')
z.create('/a', b'1'); z.create('/b', b'2'); z.create('/c', b'3'); time.sleep(0.3); R['after3'] = show('写 3 个 znode 之后')
print('  这 3 个 znode 的 czxid:', [hex(z.get(p)[1].czxid) for p in ('/a', '/b', '/c')])
print()
print('== 二:换 leader 之后 epoch + 1,counter 从 0 重新开始')
z.stop(); ld.kill(); e.wait_quorum() if False else None; time.sleep(3)
alive = [n for n in e.nodes if n.alive()]; z = client(','.join(f'127.0.0.1:{n.cport}' for n in alive)); R['elect'] = show('第二任 leader 选出后')
z.create('/d', b'4'); z.create('/e', b'5'); time.sleep(0.3); R['after2'] = show('再写 2 个之后')
print('  /c(第一任)与 /d(第二任)的 czxid:', hex(z.get('/c')[1].czxid), hex(z.get('/d')[1].czxid), '→ 后一任的 zxid 一定更大,即使 counter 更小')
print()
print('== 三:数据目录里的纪元文件与事务日志文件名')
nd = alive[0]; v2 = nd.dir / 'data' / 'version-2'
print(f'  {nd.name} 的 data 目录:', sorted(p.name for p in nd.dir.joinpath('data').iterdir())); print(f'  acceptedEpoch = {(v2 / "acceptedEpoch").read_text().strip()!r}  currentEpoch = {(v2 / "currentEpoch").read_text().strip()!r}')
print('  事务日志文件(文件名是第一条事务的 zxid):', sorted(p.name for p in v2.iterdir() if p.name.startswith('log.')))
R['files'] = sorted(p.name for p in v2.iterdir() if p.name.startswith('log.')); R['epochs'] = ((v2 / 'acceptedEpoch').read_text().strip(), (v2 / 'currentEpoch').read_text().strip())
z.stop(); e.stop(); save('z37', R)
