import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l26')
d = lab('l26', '--ref-format=reftable')
print('== 一:--ref-format=reftable 的仓库:HEAD 是占位值,refs/heads 是一个说明文件,真正的引用在 .git/reftable/')
sh(d, 'cat .git/HEAD; echo "---"; git config --local --list | grep -E "refstorage|formatversion"; echo "---"; ls -l .git/refs | awk \'NR>1 {print $5, $9}\'; cat .git/refs/heads; echo; echo "---"; ls -l .git/reftable | awk \'NR>1 {print $5, $9}\'; cat .git/reftable/tables.list')
print('  (git 自己仍能正常工作:)'); sh(d, 'git symbolic-ref HEAD; git show-ref 2>&1 | head -2; echo "(新仓库没有任何 ref,show-ref 无输出)"')
print('== 二:每次更新 ref 都往 reftable/ 里加一个新表文件,文件名是 起始更新序号-结束更新序号-校验;自动合并(compaction)让表的数量保持很少')
ci(d, '提交 1', {'a.txt': '1\n'}, t=0)
print(f'  提交 1 之后:'); sh(d, 'ls .git/reftable | grep -v tables.list')
for i in range(2, 9):
    run(d, f'git branch b{i}')
    names = [x for x in os.listdir(d / '.git' / 'reftable') if x.endswith('.ref')]
    print(f'  git branch b{i} 之后:{len(names)} 个表  ' + '  '.join(sorted(n[:-4].rsplit("-", 1)[0].replace('0x00000000000', '').replace('0x0000000000', '') + f'({os.path.getsize(d / ".git" / "reftable" / n)}B)' for n in names)))
print('== 三:解析一个表文件的头和尾:REFT、版本、块大小、更新序号范围、各部分偏移、CRC-32')
run(d, 'git pack-refs --all')
tabs = sorted(n for n in os.listdir(d / '.git' / 'reftable') if n.endswith('.ref')); print(f'  (先 git pack-refs --all 合并成 {len(tabs)} 个表)')
data = (d / '.git' / 'reftable' / tabs[-1]).read_bytes(); print(f'  表文件 {tabs[-1]},{len(data)} 字节'); hexdump(data, 32)
magic = data[:4]; ver = data[4]; bs = int.from_bytes(data[5:8], 'big'); mn, mx = struct.unpack('>QQ', data[8:24])
print(f'  头部:魔数 {magic!r}  版本 {ver}  块大小 {bs}  最小更新序号 {mn}  最大更新序号 {mx}')
f = data[-68:]; fm = f[:4]; fmn, fmx = struct.unpack('>QQ', f[8 + 16 - 16 + 0: 8 + 16 - 16 + 16]) if False else struct.unpack('>QQ', f[8:24])
ref_idx, obj_off, obj_idx, log_off, log_idx = struct.unpack('>5Q', f[24:64]); crc = struct.unpack('>I', f[64:68])[0]
print(f'  尾部(最后 68 字节):魔数 {fm!r}  与头部相同: {f[:24] == data[:24]}  ref_index_offset={ref_idx}  obj_offset(含长度字段)={obj_off}  obj_index_offset={obj_idx}  log_offset={log_off}  log_index_offset={log_idx}')
print(f'  CRC-32(尾部前 64 字节)= {zlib.crc32(f[:64]):08x};文件里记的 {crc:08x};一致: {zlib.crc32(f[:64]) == crc}')
print('  表里有多少个 ref(用 git 数):', out1(d, 'git for-each-ref | wc -l').strip())
print('== 四:5000 个 tag:reftable 与 files 后端对比(目录文件数、占用字节、查询耗时,5 次中位数)')
inp = ''.join(f'create refs/tags/t{i:05d} HEAD\n' for i in range(5000))
dr = lab('l26r', '--ref-format=reftable'); ci(dr, 'x', {'a': '1\n'}, t=0); run(dr, 'git update-ref --stdin', stdin=inp)
dl = lab('l26f'); ci(dl, 'x', {'a': '1\n'}, t=0); run(dl, 'git update-ref --stdin', stdin=inp)
def bench(dd, cmd, n=5):
    ts = []
    for _ in range(n):
        t0 = time.perf_counter(); run(dd, cmd); ts.append((time.perf_counter() - t0) * 1000)
    return median(ts)
def tot(dd, sub): return sum(p.stat().st_size for p in (dd / '.git' / sub).rglob('*') if p.is_file())
CM = ['git tag -l | wc -l', 'git rev-parse t04999']
rows = {}
rows['files(松散)'] = (int(out1(dl, 'find .git/refs -type f | wc -l')), tot(dl, 'refs'), [bench(dl, c) for c in CM])
run(dl, 'git pack-refs --all --prune')
rows['files(packed-refs)'] = (int(out1(dl, 'find .git/refs -type f | wc -l')) + 1, (dl / '.git' / 'packed-refs').stat().st_size, [bench(dl, c) for c in CM])
rows['reftable'] = (len([x for x in os.listdir(dr / '.git' / 'reftable') if x.endswith('.ref')]), tot(dr, 'reftable'), [bench(dr, c) for c in CM])
print(f'  {"后端":<20}{"文件数":>8}{"占用字节":>12}{"git tag -l":>14}{"rev-parse 单个":>16}')
for k, (n, b, t) in rows.items(): print(f'  {k:<20}{n:>8}{b:>12,}{t[0]:>11.1f} ms{t[1]:>13.1f} ms')
print('== 五:5000 个 tag 一次事务写入 = 1 个新表;而逐个 git tag 则每次一个小表,靠自动合并保持数量')
print(f'  一次 update-ref --stdin 事务写入 5000 个:表的个数 = {rows["reftable"][0]}')
d3 = lab('l26c', '--ref-format=reftable'); ci(d3, 'x', {'a': '1\n'}, t=0)
cnt = []
for i in range(1, 201):
    run(d3, f'git tag t{i}')
    if i in (1, 2, 3, 4, 5, 8, 16, 32, 64, 100, 150, 200): cnt.append((i, len([x for x in os.listdir(d3 / '.git' / 'reftable') if x.endswith('.ref')])))
print('  逐个 git tag(第 N 个之后的表数):' + '  '.join(f'{i}→{c}' for i, c in cnt))
print('== 六:迁移:git refs migrate 在两种后端之间转换')
d4 = lab('l26m'); ci(d4, 'x', {'a': '1\n'}, t=0); run(d4, 'git branch b1; git tag t1')
sh(d4, 'git refs migrate --ref-format=reftable; cat .git/HEAD; ls .git | grep -E "^(logs|packed-refs|reftable)$"; git for-each-ref --format="%(refname)"; git config --local --list | grep -E "refstorage|formatversion"')
sh(d4, 'git refs migrate --ref-format=files; cat .git/HEAD; ls .git | grep -E "^(logs|packed-refs|reftable)$"; git for-each-ref --format="%(refname)"; git config --local --list | grep -E "refstorage|formatversion" || echo "(没有 refstorage 了;formatversion 回到 0)"')
