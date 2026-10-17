import sys, os, random; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l12')
rnd = random.Random(12)
words = [''.join(rnd.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(rnd.randint(2, 9))) for _ in range(2000)]
def text(n):
    out = []; sz = 0
    while sz < n:
        l = ' '.join(rnd.choice(words) for _ in range(rnd.randint(6, 14))) + '\n'; out.append(l); sz += len(l)
    return ''.join(out).encode()
T = text(1_000_000); R = bytes(rnd.getrandbits(8) for _ in range(1_000_000)); Z = b'\0' * 1_000_000
def objsize(d, sha): p = d / '.git' / 'objects' / sha[:2] / sha[2:]; return p.stat().st_size
def du(d): return sum(f.stat().st_size for f in (d / '.git' / 'objects').rglob('*') if f.is_file())
print('== 一:三种 1 MB 的文件(文本、随机字节、全零)add 之后,松散对象的大小')
d = lab('l12a'); W(d, {'text.txt': T, 'random.bin': R, 'zeros.bin': Z})
sh(d, 'git add -A')
for f, raw in [('text.txt', T), ('random.bin', R), ('zeros.bin', Z)]:
    sha = out1(d, f'git rev-parse :{f}'); sz = objsize(d, sha)
    print(f'  {f:<11} 原始 {len(raw):>9,} 字节 → 松散对象 {sz:>9,} 字节  ({sz / len(raw):.1%})')
print('== 二:每次改一行再提交:每个版本都是一个完整的松散对象,存储线性增长')
d = lab('l12b'); lines = T.decode().split('\n')
W(d, {'big.txt': T}); ci(d, 'v0', t=0)
sizes = [du(d)]
print(f'  提交 v0 之后 objects 目录: {sizes[0]:,} 字节')
for v in range(1, 6):
    lines[v * 100] = f'第 {v} 次改动的这一行 ' + lines[v * 100]
    W(d, {'big.txt': '\n'.join(lines)}); ci(d, f'v{v}', t=v); sizes.append(du(d))
    print(f'  提交 v{v} 之后: {sizes[-1]:,} 字节(这次新增 {sizes[-1] - sizes[-2]:,})')
sh(d, "git count-objects -v | grep -E '^(count|size|in-pack|size-pack)'")
print('== 三:git gc 之后(增量压缩进 packfile)')
sh(d, 'git gc -q; git count-objects -v | grep -E "^(count|size|in-pack|size-pack)"')
print(f'  objects 目录总大小: {du(d):,} 字节(gc 前 {sizes[-1]:,})')
print('== 四:core.compression 级别对 1 MB 文本的影响(0 = 不压缩,9 = 最强)')
for lv in [0, 1, 4, 6, 9]:
    dd = lab(f'l12c{lv}'); W(dd, {'text.txt': T})
    t0 = time.perf_counter(); run(dd, f'git -c core.compression={lv} add text.txt'); t1 = (time.perf_counter() - t0) * 1000
    sha = out1(dd, 'git rev-parse :text.txt')
    print(f'  level {lv}: 松散对象 {objsize(dd, sha):>9,} 字节  add 耗时 {t1:.0f} ms')
print('== 五:不可压缩的大文件改 10 个字节:gc 之后的 delta 能省多少')
d = lab('l12d'); W(d, {'blob.bin': R}); ci(d, 'v0', t=0)
R2 = bytearray(R); R2[500_000:500_010] = b'0123456789'; W(d, {'blob.bin': bytes(R2)}); ci(d, 'v1', t=1)
print(f'  gc 前 objects: {du(d):,} 字节')
sh(d, 'git gc -q; git count-objects -v | grep -E "^(in-pack|size-pack)"')
print(f'  gc 后 objects 目录: {du(d):,} 字节(两个版本的原始字节共 {2 * len(R):,})')
