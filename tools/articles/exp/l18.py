import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l18')
d = lab('l18'); N = 6000
print('== 一:造 %d 个提交的历史(每次改 200 个文件里轮流的一个),git gc 之后只有一个 pack,没有 bitmap' % N)
fast_import(d, N, fname=lambda i: f'src/d{i % 10}/f{i % 200}.txt')
run(d, 'git checkout -q -f main && git gc -q')
sh(d, 'ls .git/objects/pack; git count-objects -v | grep -E "^(in-pack|packs)"; git rev-list --objects --all | wc -l')
def bench(cmd, n=5):
    ts = []
    for _ in range(n):
        t0 = time.perf_counter(); run(d, cmd); ts.append((time.perf_counter() - t0) * 1000)
    return median(ts)
print('== 二:没有 bitmap 时,数出“从 HEAD 能到达的全部对象”要逐个 commit、tree 走一遍')
c1 = 'git rev-list --objects --count HEAD'; c2 = 'git rev-list --objects --count HEAD~3000 --not HEAD~3010'
t_no1 = bench(c1); t_no2 = bench(c2)
sh(d, c1); print(f'  耗时 {t_no1:.1f} ms')
print('== 三:git repack -adb 写出 .bitmap,然后再数一次')
sh(d, 'git repack -adbq; ls -l .git/objects/pack/*.bitmap | awk \'{print $5, $9}\' | sed "s#.git/objects/pack/##"')
t_b1 = bench('git rev-list --use-bitmap-index --objects --count HEAD')
sh(d, 'git rev-list --use-bitmap-index --objects --count HEAD'); print(f'  耗时 {t_b1:.1f} ms(没有 bitmap 时 {t_no1:.1f} ms,快 {t_no1 / t_b1:.1f} 倍)')
print('== 四:解析 .bitmap 头部:BITM、版本、选项、被位图化的提交数、pack 的校验和')
bm = next((d / '.git' / 'objects' / 'pack').glob('*.bitmap')); data = bm.read_bytes()
pk = bm.with_suffix('.pack'); pkd = pk.read_bytes()
sig, ver, opt, cnt = struct.unpack('>4sHHI', data[:12]); ck = data[12:32].hex()
print(f'  签名 {sig!r}  版本 {ver}  选项 0x{opt:04x}  位图化的提交数 {cnt}'); hexdump(data, 32)
print(f'  头部里记的 pack 校验和 {ck}\n  pack 文件最后 20 字节   {pkd[-20:].hex()}  一致: {ck == pkd[-20:].hex()}')
print('  选项位:', ', '.join(n for b, n in [(1, 'FULL_DAG'), (4, 'HASH_CACHE'), (0x10, 'LOOKUP_TABLE'), (8, 'PSEUDO_MERGES')] if opt & b))
print('== 五:四张按类型的位图(commit / tree / blob / tag):每个对象一位,1 表示是这个类型')
pos = 32; types = []
for nm in ['commit', 'tree', 'blob', 'tag']:
    v, bits, pos = ewah(data, pos); types.append(v); print(f'  {nm:<6} 位图:共 {bits:,} 位,其中 {bin(v).count("1"):,} 位为 1')
tot = out1(d, 'git count-objects -v | grep ^in-pack').split()[1]
print(f'  四类相加 = {sum(bin(v).count("1") for v in types):,};pack 里的对象数 = {int(tot):,}')
print('== 六:每个被位图化的提交有一张“从它出发能到达的所有对象”的位图(相邻的两张用 XOR 压缩)')
entries = []; full = []
for k in range(cnt):
    opos, xo, fl = struct.unpack('>IBB', data[pos:pos + 6]); pos += 6
    v, bits, pos = ewah(data, pos); entries.append((opos, xo, fl)); full.append(v ^ full[k - xo] if xo else v)
vp = {}
for l in out1(d, f'git verify-pack -v {pk}').split('\n'):
    p = l.split()
    if len(p) >= 5 and len(p[0]) == 40: vp[int(p[4])] = p[0]
by_off = [vp[o] for o in sorted(vp)]; by_sha = sorted(vp.values())
print(f'  共解出 {len(entries)} 张;xor_offset 非 0 的有 {sum(1 for e in entries if e[1])} 张')
print('  entry 里的 object_pos 是提交在 .idx(按 hash 排序)里的下标;位图里的第 n 位对应 pack 里按偏移排序的第 n 个对象')
def check(k):
    sha = by_sha[entries[k][0]]
    reach = {x.split()[0] for x in out1(d, f'git rev-list --objects {sha}').split('\n')}
    bits = {i for i in range(len(by_off)) if full[k] >> i & 1}
    return sha, len(bits), len(reach), {by_off.index(x) for x in reach} == bits
for k in [0, len(entries) // 2, len(entries) - 1]:
    sha, nb, nr, ok = check(k)
    print(f'  第 {k:>3} 张:提交 {sha[:10]}… xor_offset={entries[k][1]}  位图里 1 的个数 {nb:>6,}  git rev-list --objects 数出 {nr:>6,}  集合完全一致: {ok}')
sample = list(range(0, len(entries), 10)); bad = sum(1 for k in sample if not check(k)[3])
print(f'  每 10 张抽查一张(共 {len(sample)} 张),集合不一致的: {bad}')
print(f'  HEAD 对应第 {next(k for k in range(len(entries)) if by_sha[entries[k][0]] == out1(d, "git rev-parse HEAD"))} 张')
print('== 七:用 bitmap 的场景:fetch/clone 时算“服务端该发送哪些对象”')
t_p_no = bench('echo HEAD | git -c pack.useBitmaps=false pack-objects --revs --stdout -q > /dev/null', 3)
t_p_b = bench('echo HEAD | git -c pack.useBitmaps=true pack-objects --revs --stdout -q > /dev/null', 3)
print(f'  git pack-objects --revs --stdout(相当于整库 clone,打包 HEAD 可达的全部对象):不用 bitmap {t_p_no:.1f} ms,用 bitmap {t_p_b:.1f} ms')
