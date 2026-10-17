import sys, os, random, math; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l16')
d = lab('l16'); NP = 20
print('== 一:造 20 个 pack:每次提交 150 个新文件,然后 git repack -d(只打包松散对象,不合并旧 pack)')
for k in range(NP):
    W(d, {f'g{k:02d}/f{i:03d}.txt': f'第 {k} 批第 {i} 个文件\n' for i in range(150)}); ci(d, f'批 {k}', t=k)
    run(d, 'git repack -d -q', k)
sh(d, 'ls .git/objects/pack/*.pack | wc -l; git count-objects -v | grep -E "^(count|in-pack|packs)"')
print('== 二:git multi-pack-index write:多出一个文件,头部是 MIDX、版本、哈希版本、块数、pack 数')
sh(d, 'git multi-pack-index write; ls -l .git/objects/pack/multi-pack-index | awk \'{print $5, $9}\'')
data = (d / '.git' / 'objects' / 'pack' / 'multi-pack-index').read_bytes()
sig, ver, hver, nch, nbase, npk = struct.unpack('>4sBBBBI', data[:12])
print(f'  签名 {sig!r}  版本 {ver}  哈希版本 {hver}(1 = SHA-1)  块数 {nch}  基础 midx 数 {nbase}  pack 数 {npk}')
hexdump(data, 32)
chunks = []
pos = 12
for i in range(nch + 1):
    cid = data[pos:pos + 4]; off = struct.unpack('>Q', data[pos + 4:pos + 12])[0]; chunks.append((cid, off)); pos += 12
for (cid, off), nxt in zip(chunks, chunks[1:]): print(f'  块 {cid.decode() if cid != b"\0\0\0\0" else "(结束)"}  偏移 {off:>6}  长度 {nxt[1] - off}')
C = {cid.decode(): (off, nxt[1] - off) for (cid, off), nxt in zip(chunks, chunks[1:])}
print('== 三:PNAM(pack 名字表)、OIDF(fanout)、OIDL(所有 pack 合并后的 hash 表)、OOFF(每个对象在哪个 pack、什么偏移)')
off, ln = C['PNAM']; names = [x.decode() for x in data[off:off + ln].split(b'\0') if x]
print(f'  PNAM:{len(names)} 个 pack 名字(按字典序),前 3 个:'); [print('    ' + x) for x in names[:3]]
off, ln = C['OIDF']; fan = struct.unpack('>256I', data[off:off + ln]); N = fan[255]
print(f'  OIDF 末项 = {N} 个对象(去重后);各 pack 的 in-pack 之和:', end=' ')
tot = 0
for nm in names: tot += int(out1(d, f'git show-index < .git/objects/pack/{nm[:-4]}.idx | wc -l'))
print(f'{tot}')
off, ln = C['OIDL']; hashes = [data[off + 20 * i: off + 20 * i + 20] for i in range(N)]
print('  OIDL 升序排列:', hashes == sorted(hashes))
off2, ln2 = C['OOFF']
tgt = out1(d, 'git rev-parse HEAD~7:g12/f100.txt'); idx = hashes.index(bytes.fromhex(tgt))
pid, poff = struct.unpack('>II', data[off2 + 8 * idx: off2 + 8 * idx + 8])
print(f'  目标 {tgt[:12]}…:OOFF 里 pack 编号 {pid} → {names[pid]},偏移 {poff}')
vp = out1(d, f'git verify-pack -v .git/objects/pack/{names[pid][:-4]}.pack | grep ^{tgt}').split()
print(f'  该 pack 里 git verify-pack 给出的偏移 {vp[4]}  一致: {int(vp[4]) == poff}')
sh(d, 'git multi-pack-index verify 2>&1; echo "verify 退出码 $?"')
print('== 四:有没有 midx 对查找速度的影响:git cat-file --batch-check 查全部 %d 个对象,9 次中位数' % N)
allobj = '\n'.join(h.hex() for h in hashes) + '\n'
def bench():
    ts = []
    for _ in range(9):
        t0 = time.perf_counter(); subprocess.run([GIT, 'cat-file', '--batch-check'], cwd=d, env=lenv(), input=allobj.encode(), capture_output=True); ts.append((time.perf_counter() - t0) * 1000)
    return median(ts)
a = bench(); run(d, 'git config core.multiPackIndex false'); b = bench(); run(d, 'git config core.multiPackIndex true')
print(f'  {NP} 个 pack,使用 midx : {a:.1f} ms'); print(f'  {NP} 个 pack,不使用 midx(core.multiPackIndex=false): {b:.1f} ms')
print('== 五:git multi-pack-index repack:把一批小 pack 合成一个新 pack,expire 再删掉被完全覆盖的旧 pack')
sizes = sorted(p.stat().st_size for p in (d / '.git' / 'objects' / 'pack').glob('*.pack'))
print(f'  现有 {len(sizes)} 个 pack,大小 {sizes[0]:,} ~ {sizes[-1]:,} 字节,合计 {sum(sizes):,}')
sh(d, 'git multi-pack-index repack --batch-size=1; ls .git/objects/pack/*.pack | wc -l')
print('  --batch-size=1:没有产生新 pack,pack 数仍是 20')
for bs in [30000, 60000]:
    sh(d, f'git multi-pack-index repack --batch-size={bs}; ls .git/objects/pack/*.pack | wc -l')
    sh(d, 'git multi-pack-index expire; ls .git/objects/pack/*.pack | wc -l; git multi-pack-index verify && echo verify 通过; git count-objects -v | grep -E "^(in-pack|packs)"')
