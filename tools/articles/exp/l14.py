import sys, os, random; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l14')
rnd = random.Random(14)
def ln(): return ' '.join(''.join(rnd.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(rnd.randint(3, 8))) for _ in range(8))
lines = [ln() for _ in range(400)]
d = lab('l14'); NV = 40
vers = []
for v in range(NV):
    if v:
        for _ in range(3): lines[rnd.randrange(len(lines))] = ln()
        lines.append(ln())
    W(d, {'data.txt': '\n'.join(lines) + '\n'}); ci(d, f'v{v}', t=v)
raw = (d / 'data.txt').stat().st_size
blobs = out1(d, "git log --reverse --format=%H | while read c; do git rev-parse $c:data.txt; done").split()
print('== 一:一个文件改了 40 个版本(每次改 3 行再追加 1 行),约 %d KB' % (raw // 1000))
rawsum = 0
for b in blobs: rawsum += int(out1(d, f'git cat-file -s {b}'))
print(f'  40 个版本的原始字节合计 {rawsum:,};最新版 {raw:,} 字节')
def repack(w, dp):
    run(d, f'git -c pack.threads=1 repack -adfq --window={w} --depth={dp}')
    packs = list((d / '.git' / 'objects' / 'pack').glob('*.pack')); sz = sum(p.stat().st_size for p in packs)
    st = out1(d, f'git verify-pack -v {packs[0]} | grep -E "^(chain length|non delta)"')
    chain = [int(x.split(':')[0].split('=')[1]) for x in st.split('\n') if x.startswith('chain length')]
    nd = [x for x in st.split('\n') if x.startswith('non delta')]
    return sz, max(chain) if chain else 0, nd[0].split(':')[1].strip() if nd else ''
sz0, _, _ = repack(0, 0)
print(f'  window=0 depth=0(完全不做 delta):pack {sz0:,} 字节')
print('== 二:window(同时考虑多少个候选基础对象),depth 固定 50')
for w in [1, 2, 5, 10, 50]:
    sz, mx, nd = repack(w, 50)
    print(f'  window={w:<3} pack {sz:>8,} 字节  最长链 {mx:>3}  完整存放 {nd}')
print('== 三:depth(链最长多深),window 固定 50')
for dp in [0, 1, 2, 5, 10, 50]:
    sz, mx, nd = repack(50, dp)
    print(f'  depth={dp:<3} pack {sz:>8,} 字节  最长链 {mx:>3}  完整存放 {nd}')
print('== 四:深度的代价:一个进程里读 40 个版本(git cat-file --batch),9 次中位数')
inp = '\n'.join(blobs) + '\n'
for dp in [0, 1, 5, 50]:
    repack(50, dp); ts = []
    for _ in range(9):
        t0 = time.perf_counter(); subprocess.run([GIT, 'cat-file', '--batch'], cwd=d, env=lenv(), input=inp.encode(), capture_output=True); ts.append((time.perf_counter() - t0) * 1000)
    print(f'  depth={dp:<3} 读完 40 个版本: {median(ts):.1f} ms')
print('== 五:git gc 的参数:aggressive 到底改了什么(GIT_TRACE 里的 repack 命令行)')
sh(d, 'GIT_TRACE=1 git gc -q 2>&1 | grep "built-in: git repack" | sed "s/.*built-in: //"')
sh(d, 'GIT_TRACE=1 git gc --aggressive -q 2>&1 | grep "built-in: git repack" | sed "s/.*built-in: //"')
