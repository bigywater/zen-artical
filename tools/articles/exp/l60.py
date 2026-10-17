import sys, os, random; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l60')
import ll as _ll
def run(d, cmd, t='now', **k): return _ll.run(d, cmd, t, **k)
def sh(d, cmd, t='now', **k): return _ll.sh(d, cmd, t, **k)
rnd = random.Random(60)
src = lab('l60src'); N = 300
out = []; t0 = int(BASE_T.timestamp()); mark = 0
for i in range(1, N + 1):
    mark += 1; body = bytes(rnd.getrandbits(8) for _ in range(20000))   # 20 KB 随机字节:压缩不动
    out.append((f'commit refs/heads/main\nmark :{mark}\ncommitter A <a@e> {t0 + i * 60} +0000\ndata 2\nx\n' + (f'from :{mark - 1}\n' if mark > 1 else '') + f'M 100644 inline data/b{i % 40:02d}.bin\ndata {len(body)}\n').encode() + body + b'\n')
subprocess.run([GIT, 'fast-import', '--quiet'], cwd=src, env=lenv(), input=b''.join(out), check=True); run(src, 'git checkout -q -f main && git gc -q')
run(src, 'git config uploadpack.allowFilter true; git config uploadpack.allowAnySHA1InWant true')
def ob(c): return int(out1(c, "git count-objects -v | awk '/^in-pack|^count/{s+=$2} END{print s}'"))
def sz(c): return sum(p.stat().st_size for p in (c / '.git' / 'objects' / 'pack').glob('*.pack')) + sum(p.stat().st_size for p in (c / '.git' / 'objects').glob('??/*') if p.is_file())
print('== 一:源仓库:%d 个提交,每次改一个 20 KB 的随机二进制文件(40 个文件轮流),共 %d 个 blob' % (N, N))
sh(src, 'git count-objects -vH | grep -E "^(in-pack|size-pack)"; git config --get uploadpack.allowFilter')
print('== 二:几种克隆方式的对象数与体积(都是 file:// 克隆,--no-checkout 以便只看克隆本身)')
rows = []
for nm, opt in [('完整', ''), ('--filter=blob:none', '--filter=blob:none'), ('--filter=blob:limit=1k', '--filter=blob:limit=1k'), ('--filter=tree:0', '--filter=tree:0')]:
    c = LT / 'l60x'; shutil.rmtree(c, ignore_errors=True)
    t0_ = time.perf_counter(); subprocess.run(f'git clone -q --no-checkout {opt} file://{src} l60x', shell=True, cwd=LT, env=lenv(), check=True); t = (time.perf_counter() - t0_) * 1000
    rows.append((nm, ob(c), sz(c), t))
print(f'  {"克隆方式":<26}{"本地对象数":>10}{"对象库大小":>12}{"耗时":>9}')
for nm, n, s_, t in rows: print(f'  {nm:<26}{n:>10,}{s_ / 1024:>9.0f} KB{t:>7.0f}ms')
print('== 三:blob:none 克隆的记号:promisor 配置、.promisor 文件,以及“缺失的对象”')
c = LT / 'l60p'; shutil.rmtree(c, ignore_errors=True); subprocess.run(f'git clone -q --no-checkout --filter=blob:none file://{src} l60p', shell=True, cwd=LT, env=lenv(), check=True)
sh(c, 'git config --get-regexp "promisor|partialclone|extensions"; ls .git/objects/pack | sed -E "s/pack-[0-9a-f]{40}/pack-<hash>/"')
sh(c, 'git rev-list --objects --missing=print HEAD | grep -c "^?"; git rev-list --objects HEAD --missing=allow-any | grep -vc "^?" | sed "s/^ */非缺失对象(commit + tree)的个数: /"')
print('== 四:按需下载(lazy fetch):访问一个缺失的 blob 时,git 在后台悄悄 fetch 它')
b = out1(c, "git ls-tree HEAD data/b05.bin | awk '{print $3}'")
n0 = ob(c); sh(c, f'git cat-file -t {b[:10]}… 2>/dev/null; true', show=False)
r = subprocess.run(f'GIT_TRACE=1 git cat-file -s {b} 2>&1 | grep -E "run_command|built-in" | sed -E "s/^[0-9:.]+ *//; s/[0-9a-f]{{40}}/<sha>/g" | head -5', shell=True, cwd=c, env=lenv(), capture_output=True, text=True)
print('  访问一个缺失的 blob(git cat-file -s)时的子进程:'); [print('    ' + _ll.tidy(l)[:150]) for l in r.stdout.strip().split('\n') if l]
print(f'  对象数 {n0} → {ob(c)}(多了 1 个 blob,下载自 origin)')
print('== 五:git checkout 需要所有当前文件的 blob:一次批量 fetch;git log -p 要历史上所有的 blob,可能多次 fetch')
sh(c, 'git checkout -q main')
print(f'  checkout 之后对象数 {ob(c)}(HEAD 的 40 个文件的 blob 一次性下载)')
r = subprocess.run('GIT_TRACE=1 git log -p --format=%h 2>&1 >/dev/null | grep -c "run_command: git.*fetch"', shell=True, cwd=c, env=lenv(), capture_output=True, text=True)
print(f'  git log -p(历史上全部 {N} 个 blob 的补丁):触发 {r.stdout.strip()} 次后台 fetch;完成后对象数 {ob(c)}')
print(f'  现在还缺失的对象数: {out1(c, "git rev-list --objects --missing=print --all | grep -c ^?")}')
