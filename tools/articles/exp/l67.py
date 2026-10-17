import sys, os, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l67')
import ll as _ll
def run(d, cmd, t='now', **k): return _ll.run(d, cmd, t, **k)
def sh(d, cmd, t='now', **k): return _ll.sh(d, cmd, t, **k)
def ci(d, msg, files=None, t='now', **k): return _ll.ci(d, msg, files, t, **k)
SAN = "sed -E 's/[0-9a-f]{40}/<sha40>/g'"
src = lab('l67src'); [ci(src, f'提交 {i}', {f'f{i % 7}.txt': f'版本 {i}\n' * 40}, t=i) for i in range(1, 11)]
run(src, 'git branch dev HEAD~3; git tag v1 HEAD~5', 20)
B = LT / 'l67full.bundle'
print('== 一:git bundle create:一个文件里装下“若干个 ref + 一个 pack”。文件开头是几行文本,然后是 PACK 数据')
sh(src, f'git bundle create {B} --all 2>&1 | tail -1; ls -l {B} | awk \'{{print $5, "字节"}}\'')
raw = B.read_bytes(); i = raw.index(b'PACK')
head = raw[:i].decode(); print('  文件开头的文本部分(PACK 之前的字节):')
for l in head.rstrip('\n').split('\n'): print('    ' + re.sub(r'[0-9a-f]{40}', '<sha40>', l))
print('    (最后有一个空行:文本头与 pack 的分隔)')
ver, n, ents = parse_pack(raw[i:])
print(f'  PACK 头:版本 {ver},对象数 {n};源仓库 git rev-list --objects --all 数出 {out1(src, "git rev-list --objects --all | wc -l").strip()} 个对象——pack 里装的就是全部可达对象')
print('== 二:git bundle verify / list-heads;用 bundle 当作远程 clone')
sh(src, f'git bundle verify {B} 2>&1 | tail -2 | ' + SAN)
sh(src, f'git bundle list-heads {B} | ' + SAN)
c = LT / 'l67c'; shutil.rmtree(c, ignore_errors=True); r = subprocess.run(f'git clone -q {B} l67c', shell=True, cwd=LT, env=lenv(), capture_output=True, text=True)
sh(c, 'git log --oneline | wc -l | sed "s/^ */clone 出来的提交数: /"; git branch -a | tr "\\n" " "; echo; git tag | tr "\\n" " "; echo; git config --get remote.origin.url | sed "s#.*/#…/#"')
print('== 三:增量 bundle:只含“某个提交之后”的新对象,文件里记录前置条件(prerequisites,以 - 开头的行)')
[ci(src, f'新提交 {i}', {f'g{i}.txt': f'新 {i}\n' * 40}, t=30 + i) for i in range(1, 4)]
base = out1(src, 'git rev-parse HEAD~3'); INC = LT / 'l67inc.bundle'
sh(src, f'git bundle create {INC} main ^{base} 2>&1 | tail -1; ls -l {INC} | awk \'{{print $5, "字节"}}\'')
raw2 = INC.read_bytes(); j = raw2.index(b'PACK'); print('  增量 bundle 的文本部分:'); [print('    ' + re.sub(r'[0-9a-f]{40}', '<sha40>', l)) for l in raw2[:j].decode().split('\n') if l]
v2, n2, _ = parse_pack(raw2[j:]); print(f'  pack 里的对象数 {n2}(完整 bundle 是 {n}),文件大小 {INC.stat().st_size:,} 字节(完整 bundle {B.stat().st_size:,} 字节)')
print('  在缺少前置提交的仓库里验证:')
empty = lab('l67empty'); sh(empty, f'git bundle verify {INC} 2>&1 | head -3 | ' + SAN)
print('  在已经有这些提交的仓库(上面 clone 出来的 l67c)里验证:'); sh(c, f'git bundle verify {INC} 2>&1 | head -4 | sed -E "s/[0-9a-f]{{40}}/<sha40>/g"')
print('== 四:从 bundle fetch 就像从远程 fetch:更新远程跟踪分支')
sh(c, f'git fetch {INC} main:refs/remotes/bundle/main 2>&1 | tail -2 | sed -E "s/[0-9a-f]{{7}}\\.\\.[0-9a-f]{{7}}/<旧>..<新>/; s#From .*#From <bundle>#"; git log --oneline refs/remotes/bundle/main | wc -l | sed "s#^ *#bundle/main 的提交数: #"')
print('== 五:bundle 的 pack 与 git pack-objects 直接打包同样的对象一样大吗')
pk = int(subprocess.run('git rev-list --objects --all | git pack-objects --stdout | wc -c', shell=True, cwd=src, env=lenv(), capture_output=True, text=True).stdout.strip())
full2 = LT / 'l67full2.bundle'; run(src, f'git bundle create {full2} --all'); r2 = full2.read_bytes(); k = r2.index(b'PACK')
print(f'  git pack-objects 直接打包全部对象: {pk:,} 字节;bundle 里 PACK 部分: {len(r2) - k:,} 字节;文本头 {k} 字节')
