import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l17')
d = lab('l17'); N = 30000
print('== 一:用 git fast-import 造 %d 个提交的历史(每 100 个提交有一次合并)' % N)
head = fast_import(d, N, merges_every=100)
run(d, 'git checkout -q -f main')
sh(d, 'git rev-list --count HEAD; git rev-list --merges --count HEAD; ls .git/objects/info 2>&1')
def bench(cmd, n=5):
    ts = []
    for _ in range(n):
        t0 = time.perf_counter(); run(d, cmd); ts.append((time.perf_counter() - t0) * 1000)
    return median(ts)
CMDS = [('git rev-list --count HEAD', '数全部提交'), ('git log --topo-order -1 --format=%h', 'log --topo-order -1'), ('git merge-base --is-ancestor HEAD~25000 HEAD', 'is-ancestor(25000 步之前)'), ('git merge-base HEAD~20000 HEAD~1', 'merge-base')]
print('== 二:没有 commit-graph 时的耗时(5 次中位数)')
no = {}
for c, nm in CMDS: no[c] = bench(c); print(f'  {nm:<28} {no[c]:>8.1f} ms')
print('== 三:git commit-graph write --reachable,然后解析这个文件')
sh(d, 'git commit-graph write --reachable; ls -l .git/objects/info/commit-graph | awk \'{print $5, $9}\'')
data = (d / '.git' / 'objects' / 'info' / 'commit-graph').read_bytes()
sig, ver, hv, nch, nbase = struct.unpack('>4sBBBB', data[:8])
print(f'  签名 {sig!r}  版本 {ver}  哈希版本 {hv}  块数 {nch}  基础图数 {nbase}'); hexdump(data, 16)
chunks = []; pos = 8
for i in range(nch + 1):
    cid = data[pos:pos + 4]; off = struct.unpack('>Q', data[pos + 4:pos + 12])[0]; chunks.append((cid, off)); pos += 12
C = {}
for (cid, off), nxt in zip(chunks, chunks[1:]): C[cid.decode()] = (off, nxt[1] - off); print(f'  块 {cid.decode()}  偏移 {off:>8}  长度 {nxt[1] - off:>8}')
off, ln = C['OIDF']; fan = struct.unpack('>256I', data[off:off + ln]); M = fan[255]
print(f'  OIDF 末项 = {M:,} 个提交(= git rev-list --all --count: {out1(d, "git rev-list --all --count")})')
print('== 四:CDAT:每个提交 36 字节 = 根 tree(20)+ 第一个 parent(4,下标)+ 第二个 parent(4)+ 世代数/时间(8)')
off, ln = C['CDAT']; assert ln == 36 * M
off_l, _ = C['OIDL']; hashes = [data[off_l + 20 * i: off_l + 20 * i + 20] for i in range(M)]
idx = hashes.index(bytes.fromhex(head)); rec = data[off + 36 * idx: off + 36 * idx + 36]
tree = rec[:20].hex(); p1, p2 = struct.unpack('>II', rec[20:28]); w = struct.unpack('>II', rec[28:36])
gen = w[0] >> 2; tim = ((w[0] & 3) << 32) | w[1]
print(f'  HEAD={head[:10]}…  下标 {idx}')
print(f'  tree   {tree[:10]}…(git 里是 {out1(d, "git rev-parse HEAD^{tree}")[:10]}…)')
print(f'  parent1 下标 {p1} → {hashes[p1].hex()[:10]}…(git: {out1(d, "git rev-parse HEAD^1")[:10]}…)')
print(f'  parent2 下标 {p2} → {hashes[p2].hex()[:10]}…(git: {out1(d, "git rev-parse HEAD^2")[:10]}…)  HEAD 是合并提交')
nm_ = bytes.fromhex(out1(d, 'git rev-parse HEAD^1~1')); j = hashes.index(nm_); rr = data[off + 36 * j: off + 36 * j + 36]
print(f'  对一个普通提交(HEAD^1~1)取 parent2 字段: 0x{struct.unpack(">I", rr[24:28])[0]:08x}(没有第二个 parent 时的占位值)')
print(f'  提交时间 {tim}(git: {out1(d, "git log -1 --format=%ct")});世代数 {gen}')
gens = {}
for i in range(M):
    r = data[off + 36 * i: off + 36 * i + 36]; ww = struct.unpack('>II', r[28:36]); gens[i] = ww[0] >> 2
print(f'  世代数范围 {min(gens.values())} ~ {max(gens.values())};根提交的世代数 = {gens[hashes.index(bytes.fromhex(out1(d, "git rev-list --max-parents=0 HEAD")))]}')
print('== 五:有 commit-graph 时的耗时(5 次中位数)')
for c, nm in CMDS:
    w_ = bench(c); print(f'  {nm:<28} {no[c]:>8.1f} → {w_:>8.1f} ms   快 {no[c] / w_:.1f} 倍')
print('== 六:git gc 默认就会写 commit-graph(gc.writeCommitGraph 没有显式设置)')
d2 = lab('l17b'); fast_import(d2, 500); run(d2, 'git checkout -q -f main')
sh(d2, 'ls .git/objects/info/; git gc -q; ls .git/objects/info/')
sh(d2, 'git config gc.writeCommitGraph || echo "gc.writeCommitGraph 未显式设置(默认 true)"')
