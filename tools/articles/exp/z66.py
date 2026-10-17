import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z66'); R = {}
CMDS = ['ruok', 'srvr', 'stat', 'conf', 'cons', 'crst', 'dirs', 'dump', 'envi', 'gtmk', 'isro', 'mntr', 'srst', 'wchc', 'wchp', 'wchs', 'hash']
def first(out, n=1): return ' | '.join(l.strip() for l in out.strip().splitlines()[:n])[:95] or '(空)'
print('== 一:默认配置(没有设置 4lw.commands.whitelist)下,每个四字命令得到什么')
n = Node('z66a', 7300); n.prepare(); cfg = (n.dir / 'zoo.cfg').read_text().replace('4lw.commands.whitelist=*\n', ''); (n.dir / 'zoo.cfg').write_text(cfg); n.keep_cfg = True; n.start(wipe=False); z = client('127.0.0.1:7300'); z.create('/a', b'x'); z.get('/a', watch=lambda e: None)
print('  默认白名单生效的配置行:', [l for l in cfg.splitlines() if '4lw' in l] or '(没有写 4lw 白名单)')
R['default'] = {}
for c in CMDS:
    o = four(7300, c); R['default'][c] = first(o); print(f'  {c:<5} → {first(o)}')
print('  日志里的启用列表:', [re.sub(r'^\S+ \[.*?\] \w+\s+\S+ - ', '', l)[:140] for l in n.log().splitlines() if 'list of enabled four letter word' in l][:1]); R['enabled_log'] = [l[:200] for l in n.log().splitlines() if 'list of enabled four letter word' in l][:1]
z.stop(); n.stop()
print()
print('== 二:白名单设成 *(实验用)后的完整输出(每条命令的前 3 行)')
n = Node('z66b', 7301).start(); z = client('127.0.0.1:7301'); z.create('/a', b'x'); z.get('/a', watch=lambda e: None); c2 = client('127.0.0.1:7301')
R['full'] = {}
for c in ['ruok', 'srvr', 'stat', 'conf', 'cons', 'dirs', 'dump', 'envi', 'gtmk', 'isro', 'wchs', 'wchp', 'wchc']:
    o = four(7301, c); R['full'][c] = o.strip().splitlines()[:3]; print(f'  [{c}]'); [print('     ', l[:110]) for l in o.strip().splitlines()[:3]]
c2.stop(); z.stop(); n.stop(); save('z66', R)
