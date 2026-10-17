import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l24')
d = lab('l24'); c1 = ci(d, '提交 1', {'a.txt': '1\n'}, t=0)
run(d, 'git branch dev && git branch feat/x && git tag v1 && git tag -a v2 -m 带注解', 1)
F = "find .git/refs -type f | sort"
print('== 一:一开始每个 ref 是 .git/refs 下的一个文件')
sh(d, F); sh(d, 'cat .git/refs/heads/dev | cut -c1-12; ls .git/packed-refs 2>&1')
print('== 二:git pack-refs --all --prune:移进 .git/packed-refs,松散文件被删除')
sh(d, 'git pack-refs --all --prune; find .git/refs -type f | sort; echo "(以上是剩下的松散 ref 文件)"')
sh(d, "cat .git/packed-refs | sed -E 's/^([0-9a-f]{7})[0-9a-f]{33}/\\1…/; s/^\\^([0-9a-f]{7})[0-9a-f]{33}/^\\1…/'")
sh(d, 'git rev-parse dev v2 v2^{} | cut -c1-12')
print('== 三:同一个 ref 既有松散文件又有 packed 记录时,松散文件优先')
c2 = ci(d, '提交 2', {'a.txt': '2\n'}, t=2)
sh(d, "ls .git/refs/heads; grep -E ' refs/heads/main$' .git/packed-refs | cut -c1-12; cat .git/refs/heads/main | cut -c1-12")
print(f'  git rev-parse main = {out1(d, "git rev-parse main")[:12]}(提交 2 是 {c2[:12]},提交 1 是 {c1[:12]})')
sh(d, 'rm .git/refs/heads/main; git rev-parse main | cut -c1-12')
print('  手工删掉松散文件之后,main “回退”成 packed-refs 里的旧值(提交 1)——松散文件被删就露出下面的旧记录')
run(d, f'git update-ref refs/heads/main {c2}')
print('== 四:删除一个 packed 的分支:要改写 packed-refs;删除一个松散的分支:删文件')
sh(d, "git branch -D dev; grep -c refs/heads/dev .git/packed-refs || true; git branch")
sh(d, 'git branch tmp1; git branch -D tmp1; ls .git/refs/heads')
print('== 五:ref 多的时候:5000 个 tag,松散 vs packed 的耗时(5 次中位数)')
d2 = lab('l24b'); ci(d2, 'x', {'a': '1\n'}, t=0)
inp = ''.join(f'create refs/tags/t{i:05d} HEAD\n' for i in range(5000))
run(d2, 'git update-ref --stdin', stdin=inp)
def bench(cmd, n=5):
    ts = []
    for _ in range(n):
        t0 = time.perf_counter(); run(d2, cmd); ts.append((time.perf_counter() - t0) * 1000)
    return median(ts)
nfiles = lambda: out1(d2, "find .git/refs -type f | wc -l").strip()
sh(d2, 'find .git/refs/tags -type f | wc -l; ls .git/packed-refs 2>&1 | head -1')
CM = ['git for-each-ref refs/tags | wc -l', 'git rev-parse t04999', 'git tag -l | wc -l']
loose = {c: bench(c) for c in CM}
sh(d2, 'git pack-refs --all --prune; find .git/refs/tags -type f | wc -l; wc -l < .git/packed-refs; ls -l .git/packed-refs | awk \'{print $5}\'')
pk = {c: bench(c) for c in CM}
for c in CM: print(f'  {c:<36} 松散 {loose[c]:>6.1f} ms → packed {pk[c]:>6.1f} ms')
print('== 六:git gc 默认就会执行 pack-refs;新建的 ref 又是松散文件,下一次 gc 再合并')
d3 = lab('l24c'); ci(d3, 'x', {'a': '1\n'}, t=0); run(d3, 'git branch b1; git branch b2')
sh(d3, 'git gc -q; find .git/refs -type f | sort; grep -c . .git/packed-refs')
sh(d3, 'git branch b3; find .git/refs -type f | sort')
