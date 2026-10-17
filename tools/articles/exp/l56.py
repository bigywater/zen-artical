import sys, os, random; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l56')
import ll as _ll
def run(d, cmd, t='now', **k): return _ll.run(d, cmd, t, **k)
rnd = random.Random(56)
src = lab('l56src')
W(src, {f'd{i // 200:02d}/f{i:05d}.txt': f'内容 {i} ' + 'x' * rnd.randint(100, 300) + '\n' for i in range(4000)}); run(src, 'git add -A && git commit -q -m 4000个文件', 0)
W(src, {f'e/g{i:03d}.txt': f'第二批 {i}\n' for i in range(500)}); run(src, 'git add -A && git commit -q -m 第二批', 1)
run(src, 'git repack -q -d')   # 一部分对象打成 pack,稍后再造一批松散对象
W(src, {f'h/j{i:04d}.txt': f'第三批 {i} ' + 'y' * 100 + '\n' for i in range(3000)}); run(src, 'git add -A && git commit -q -m 第三批', 2)
def cnt(d): return int(out1(d, "find .git/objects -type f -path '*/??/*' | wc -l")), len(list((d / '.git' / 'objects' / 'pack').glob('*.pack')))
n_loose, n_pack = cnt(src)
print(f'== 一:源仓库:{n_loose:,} 个松散对象 + {n_pack} 个 pack(一共 7,500 多个文件的三次提交)')
sh(src, 'git count-objects -vH | grep -E "^(count|size|in-pack|size-pack):"')
def inode(path): return os.stat(path).st_ino
def link(path): return os.stat(path).st_nlink
loose = next(p for p in (src / '.git' / 'objects').glob('??/*') if p.is_file())
print('== 二:四种本地 clone 方式(耗时是 3 次中位数,含检出工作区):耗时、松散对象的链接数、pack 的链接数、和源仓库合计占多少磁盘')
rows = []
for nm, cmd in [('git clone /路径(默认,本地路径)', 'git clone -q {s} {d}'), ('git clone --no-hardlinks /路径', 'git clone -q --no-hardlinks {s} {d}'), ('git clone file:///路径', 'git clone -q file://{s} {d}'), ('git clone --shared /路径', 'git clone -q --shared {s} {d}')]:
    dst = LT / 'l56dst'; ts_ = []
    for _ in range(3):
        shutil.rmtree(dst, ignore_errors=True)
        t0 = time.perf_counter(); r = subprocess.run(cmd.format(s=src, d=dst), shell=True, cwd=LT, env=lenv(), capture_output=True, text=True); ts_.append((time.perf_counter() - t0) * 1000)
        assert r.returncode == 0, r.stderr
    t = median(ts_)
    lo = [p for p in (dst / '.git' / 'objects').glob('??/*') if p.is_file()]; pk = list((dst / '.git' / 'objects' / 'pack').glob('*.pack'))
    nlinks = f'{link(lo[0])}' if lo else '(没有松散对象)'; plinks = f'{link(pk[0])}' if pk else '(没有 pack)'
    both = int(out1(LT, f"du -sk {src}/.git/objects {dst}/.git/objects | awk '{{s+=$1}} END{{print s}}'")); only_src = int(out1(LT, f"du -sk {src}/.git/objects | cut -f1"))
    alt = (dst / '.git' / 'objects' / 'info' / 'alternates').exists()
    rows.append((nm, t, len(lo), len(pk), nlinks, plinks, both - only_src, alt))
    shutil.rmtree(LT / f'l56_{len(rows)}', ignore_errors=True); shutil.copytree(dst, LT / f'l56_{len(rows)}', symlinks=True)
print(f'  {"方式":<36}{"耗时":>9}{"松散":>8}{"pack":>6}{"松散链接数":>12}{"pack 链接数":>12}{"clone 的 objects 额外磁盘":>16}{"alternates":>12}')
for nm, t, nl, npk, a, b, extra, alt in rows: print(f'  {nm:<36}{t:>7.0f}ms{nl:>8,}{npk:>6}{a:>12}{b:>12}{extra / 1024:>13.1f} MB{"有" if alt else "无":>11}')
print('  (“objects 额外磁盘”=把源和 clone 的 .git/objects 放在同一个 du 里统计,clone 多出来的部分;硬链接的文件在 du 里只算一次)')
print('== 三:file:// 与路径方式的区别:file:// 走的是 upload-pack(重新打包,不用硬链接),路径方式直接复制或链接 .git/objects')
dst = LT / 'l56_3'; sh(dst, 'ls .git/objects | head -3 | tr "\\n" " "; echo "...(松散对象目录)"; ls .git/objects/pack')
dst = LT / 'l56_1'; sh(dst, 'ls .git/objects/info; git config --get remote.origin.url | sed "s#.*/#…/#"')
print('== 四:硬链接的 clone 不受源仓库 gc 影响;--shared 的 clone 依赖源仓库的对象,源仓库把对象清理掉它就坏')
sa = lab('l56a'); [ci(sa, f'提交 {i}', {f'f{i}.txt': f'{i}\n' * 50}, t=i) for i in range(1, 4)]
for k, opt in [('H', ''), ('SH', '--shared')]:
    shutil.rmtree(LT / f'l56{k}', ignore_errors=True); subprocess.run(f'git clone -q {opt} {sa} l56{k}', shell=True, cwd=LT, env=lenv(), check=True)
sh(LT / 'l56SH', 'cat .git/objects/info/alternates | sed "s#.*/ltmp#<ltmp>#"; ls .git/objects | tr "\\n" " "; echo "(--shared 的 clone 自己没有对象文件)"')
print('  在源仓库里把最新的提交永远删掉(reset、清 reflog、gc --prune=now):')
run(sa, 'git reset -q --hard HEAD~1; git reflog expire --expire=now --all; git gc -q --prune=now')
sh(sa, 'git log --oneline | wc -l | sed "s/^ */源仓库现在的提交数: /"')
for k, nm in [('H', '硬链接的 clone'), ('SH', '--shared 的 clone')]:
    c = LT / f'l56{k}'; rc1, o1 = run(c, 'git fsck 2>&1 | head -2'); rc2, o2 = run(c, 'git log --oneline 2>&1 | head -4')
    print(f'  [{nm}] git fsck → {o1 or "(无输出:完整)"}'); print(f'  [{nm}] git log → ' + o2.replace(chr(10), ' | ')[:150])
