import sys, os, random; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l32')
def entry(d, path='a.txt'): return next(e for e in parse_index(d / '.git' / 'index')[1] if e['path'] == path)
def fmt(ns): return f'{ns // 10**9}.{ns % 10**9:09d}'
def setup(name, mtime_offset, content='hello\n'):
    d = lab(name); W(d, {'a.txt': content}); t = time.time_ns() + int(mtime_offset * 1e9); os.utime(d / 'a.txt', ns=(t, t))
    run(d, 'git add a.txt'); return d
def tamper(d):
    st = os.stat(d / 'a.txt'); orig = (st.st_atime_ns, st.st_mtime_ns)
    with open(d / 'a.txt', 'r+b') as f: f.write(b'HELLO\n')
    os.utime(d / 'a.txt', ns=orig)
print('== 一:racy 的定义:index 条目里的 mtime ≥ index 文件自己的修改时间。说明这个文件“可能在 index 写出之后又被改过,而 mtime 没变”')
print('  a) 正常情况:文件是之前写的,mtime 早于 index 写出的时刻')
d = setup('l32a', -60); st = os.stat(d / 'a.txt'); ix = os.stat(d / '.git' / 'index'); e = entry(d)
print(f'     文件 mtime {fmt(st.st_mtime_ns)}  index 文件 mtime {fmt(ix.st_mtime_ns)}  文件早于 index: {st.st_mtime_ns < ix.st_mtime_ns}  index 里记的 size = {e["size"]}(文件真实大小 {st.st_size})')
print('  b) racy:文件的 mtime 比 index 文件的修改时间还晚(这里用 os.utime 把 mtime 设到 60 秒后,等同于时钟不同步 / 解压出来的文件)')
d = setup('l32b', +60); st = os.stat(d / 'a.txt'); ix = os.stat(d / '.git' / 'index'); e = entry(d)
print(f'     文件 mtime {fmt(st.st_mtime_ns)}  index 文件 mtime {fmt(ix.st_mtime_ns)}  文件早于 index: {st.st_mtime_ns < ix.st_mtime_ns}  index 里记的 size = {e["size"]}(文件真实大小 {st.st_size})')
print('== 二:同样的“原地改写 + 恢复 mtime”(core.trustctime=false、core.checkStat=minimal,只比 mtime 和 size),racy 的被发现,非 racy 的看不出来(AM 里的 M 就是发现的改动)')
for nm, d in [('a) 非 racy', LT / 'l32a'), ('b) racy', LT / 'l32b')]:
    run(d, 'git config core.trustctime false; git config core.checkStat minimal'); tamper(d)
    o = out1(d, 'git status --short')
    print(f'  {nm}: git status --short → {o or "(空,没发现)"}   工作区 blob {out1(d, "git hash-object a.txt")[:8]}  index blob {out1(d, "git rev-parse :a.txt")[:8]}')
def mk(name, off):
    d = lab(name); rnd = random.Random(32)
    W(d, {f'd{i // 100:02d}/f{i:05d}.txt': f'内容 {i} ' + 'x' * rnd.randint(200, 800) + '\n' for i in range(10000)})
    t = time.time_ns() + int(off * 1e9)
    for p in d.rglob('*.txt'): os.utime(p, ns=(t, t))
    run(d, 'git add -A'); run(d, 'git commit -q -m x'); return d
def tm(d):
    t0 = time.perf_counter(); run(d, 'git status --short'); return (time.perf_counter() - t0) * 1000
print('== 三:racy 什么时候解除:1 万个文件的 mtime 设在 20 秒之后;mtime 还没到、刚过 0.3 秒时 status 都每次重读内容;过去几秒后的第一次 status 才重写 index,之后恢复快速')
t_M = time.time() + 20
d = mk('l32m', +20)
left = t_M - time.time(); print(f'  建好仓库之后,离文件 mtime 还剩 {left:.0f} 秒(add 和 commit 本身就花了 {20 - left:.0f} 秒)')
print('  mtime 还没到:' + '  '.join(f'{tm(d):.0f} ms' for _ in range(3)))
time.sleep(max(0, t_M + 0.3 - time.time()))
print('  mtime 刚过去 0.3 秒之后连续 3 次:' + '  '.join(f'{tm(d):.0f} ms' for _ in range(3)))
time.sleep(max(0, t_M + 3.0 - time.time()))
print('  mtime 过去 3 秒之后连续 4 次:' + '  '.join(f'{tm(d):.0f} ms' for _ in range(4)))
print('== 四:racy 的代价:文件 mtime 在 2 分钟后,git status 每次都重读内容(1 万个文件,5 次连续运行的耗时);对照 mtime 在过去的正常仓库')
dp = mk('l32p', -60); dn = mk('l32n', +120)
time.sleep(1.1)
print('  文件 mtime 在过去(正常):' + '  '.join(f'{tm(dp):.0f} ms' for _ in range(5)))
print('  文件 mtime 在 2 分钟后(racy):' + '  '.join(f'{tm(dn):.0f} ms' for _ in range(5)))
