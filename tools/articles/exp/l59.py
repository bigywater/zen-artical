import sys, os, random; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l59')
import ll as _ll
def run(d, cmd, t='now', **k): return _ll.run(d, cmd, t, **k)
def sh(d, cmd, t='now', **k): return _ll.sh(d, cmd, t, **k)
rnd = random.Random(59)
src = lab('l59src'); N = 2000
# 2000 个提交,每次改 50 个文件中的一个(每个文件约 3 KB 随机文本)
out = []; t0 = int(BASE_T.timestamp()); mark = 0
for i in range(1, N + 1):
    mark += 1; body = f'版本 {i}\n' + ''.join(''.join(rnd.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(60)) + '\n' for _ in range(50))
    out.append(f'commit refs/heads/main\nmark :{mark}\ncommitter A <a@e> {t0 + i * 3600} +0000\ndata {len(f"提交 {i}".encode())}\n提交 {i}\n' + (f'from :{mark - 1}\n' if mark > 1 else '') + f'M 100644 inline f{i % 50:02d}.txt\ndata {len(body.encode())}\n{body}\n')
subprocess.run([GIT, 'fast-import', '--quiet'], cwd=src, env=lenv(), input=''.join(out).encode(), check=True); run(src, 'git checkout -q -f main && git gc -q')
sh(src, 'git rev-list --count HEAD; git count-objects -vH | grep -E "^(in-pack|size-pack)"')
def stats(c): return int(out1(c, 'git rev-list --count HEAD')), int(out1(c, "git count-objects -v | awk '/^in-pack|^count/{s+=$2} END{print s}'")), out1(c, "git count-objects -vH | awk '/^size-pack|^size:/{print $2\" \"$3}' | tr '\\n' ' '")
print('== 一:本地路径 clone 会忽略 --depth;要用 file:// 才真的浅克隆。浅克隆在 .git/shallow 里记下“边界提交”')
c = LT / 'l59d1'; shutil.rmtree(c, ignore_errors=True)
r = subprocess.run(f'git clone --depth 1 {src} l59local', shell=True, cwd=LT, env=lenv(), capture_output=True, text=True); print('  git clone --depth 1 /路径 →', next((l for l in r.stderr.split('\n') if 'warning' in l), '(没有警告)')[:110]); shutil.rmtree(LT / 'l59local', ignore_errors=True)
subprocess.run(f'git clone -q --depth 1 file://{src} l59d1', shell=True, cwd=LT, env=lenv(), check=True)
sh(c, 'git log --oneline; cat .git/shallow | sed -E "s/[0-9a-f]{40}/<sha40>/"; git rev-parse --is-shallow-repository')
sh(c, 'git cat-file -p HEAD | grep -E "^(parent|tree)" | sed -E "s/[0-9a-f]{40}/<sha40>/"; echo "---"; P=$(git cat-file -p HEAD | grep ^parent | cut -d" " -f2); git cat-file -t $P 2>&1 | head -1; git log --oneline --parents | sed -E "s/[0-9a-f]{40}/<sha40>/g"')
print('== 二:完整克隆与不同深度的对象数和 pack 大小')
rows = []
for nm, opt in [('完整', ''), ('--depth 50', '--depth 50'), ('--depth 10', '--depth 10'), ('--depth 1', '--depth 1')]:
    d_ = LT / 'l59x'; shutil.rmtree(d_, ignore_errors=True)
    t0 = time.perf_counter(); subprocess.run(f'git clone -q {opt} file://{src} l59x', shell=True, cwd=LT, env=lenv(), check=True); t = (time.perf_counter() - t0) * 1000
    pk = sum(p.stat().st_size for p in (d_ / '.git' / 'objects' / 'pack').glob('*.pack')); n = int(out1(d_, "git count-objects -v | awk '/^in-pack|^count/{s+=$2} END{print s}'")); rows.append((nm, int(out1(d_, 'git rev-list --count HEAD')), n, pk, t))
print(f'  {"克隆方式":<14}{"可见提交数":>10}{"对象数":>10}{"pack 大小":>12}{"耗时":>9}')
for nm, c_, n, pk, t in rows: print(f'  {nm:<14}{c_:>10,}{n:>10,}{pk / 1024:>9.0f} KB{t:>7.0f}ms')
print('== 三:加深与恢复:--deepen N 再多取 N 层,--unshallow 取回全部')
sh(c, 'git fetch -q --deepen 9; git rev-list --count HEAD; wc -l < .git/shallow | sed "s/^ */shallow 文件行数: /"')
sh(c, 'git fetch -q --unshallow; git rev-list --count HEAD; git rev-parse --is-shallow-repository; ls .git/shallow 2>&1 | head -1')
print('== 四:历史不完整会让哪些命令受限')
c = LT / 'l59d1'; shutil.rmtree(c, ignore_errors=True); subprocess.run(f'git clone -q --depth 5 file://{src} l59d1', shell=True, cwd=LT, env=lenv(), check=True)
sh(c, 'git log --oneline | wc -l | sed "s/^ */git log 能看到的提交数: /"; git blame -s f07.txt | head -2 | cut -c1-60; git describe --always 2>&1 | head -1 | sed -E "s/[0-9a-f]{7,}/<sha>/"')
sh(c, 'git cat-file -t $(git -C %s rev-parse HEAD~100) 2>&1 | head -1' % src)
sh(c, 'git log --oneline HEAD~10 2>&1 | head -2')
print('== 五:--shallow-since 与 --shallow-exclude:按时间或按引用截断,而不是按层数')
d_ = LT / 'l59y'; shutil.rmtree(d_, ignore_errors=True)
cut = t0_ = int(BASE_T.timestamp()) + 1990 * 3600
subprocess.run(f'git clone -q --shallow-since=@{cut} file://{src} l59y', shell=True, cwd=LT, env=lenv(), check=True)
print(f'  --shallow-since=<第 1990 个提交的时间>:可见提交 {out1(d_, "git rev-list --count HEAD")} 个(第 1990~2000 共 11 个)')
src_tag = run(src, 'git tag mark1950 HEAD~50')
d2_ = LT / 'l59z'; shutil.rmtree(d2_, ignore_errors=True)
subprocess.run(f'git clone -q --shallow-exclude=mark1950 file://{src} l59z', shell=True, cwd=LT, env=lenv(), check=True)
print(f'  --shallow-exclude=mark1950(标签在倒数第 51 个):可见提交 {out1(d2_, "git rev-list --count HEAD")} 个(标签之后的 50 个提交,标签自身被排除)')
