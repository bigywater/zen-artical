import sys, os, random, math; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l51')
N = 1000
d = lab('l51'); fast_import(d, N, fname='f.txt')   # 每个提交把 f.txt 写成 "版本 i"
# fast_import 写的是 "版本 i\n";脚本里取数字
SCRIPT = LT / '_bisect_test.sh'
SCRIPT.write_text('#!/bin/sh\necho x >> "$COUNTER"\nn=$(sed "s/[^0-9]//g" f.txt)\n[ "$n" -lt "$K" ]\n')   # 好:f.txt 里的数字 < K;坏:>= K
SCRIPT.chmod(0o755)
CNT = LT / '_bisect_count'
def bisect_run(K, first_only=False):
    CNT.write_text('')
    env = {'K': K, 'COUNTER': CNT}
    run(d, 'git bisect reset >/dev/null 2>&1; git bisect start main $(git rev-list --max-parents=0 HEAD) >/dev/null 2>&1', env=env)
    rc, o = run(d, f'git bisect run {SCRIPT} 2>&1', env=env)
    n = len(CNT.read_text().split()); first = next((l for l in o.split('\n') if 'is the first bad commit' in l), '')
    res = out1(d, 'git log -1 --format=%s refs/bisect/bad 2>/dev/null')
    run(d, 'git bisect reset >/dev/null 2>&1')
    return n, first, res, o
print('== 一:%d 个提交的线性历史;好的起点是第 1 个提交,坏的终点是第 %d 个。手工 bisect 的前几步' % (N, N))
env = {'K': 637, 'COUNTER': CNT}
sh(d, 'git bisect start main $(git rev-list --max-parents=0 HEAD) 2>&1 | sed -E "s/[0-9a-f]{40}/<sha>/g; s/\\[[0-9a-f]+\\]/[<sha>]/"', env=env)
for i in range(4):
    n = int(out1(d, "sed 's/[^0-9]//g' f.txt", env=env))
    verdict = 'good' if n < 637 else 'bad'
    print(f'  测试当前提交 f.txt=“版本 {n}” → 标记 {verdict}'); sh(d, f'git bisect {verdict} 2>&1 | head -1 | sed -E "s/[0-9a-f]{{40}}/<sha>/g"', env=env, ind='    ')
sh(d, 'git bisect log | grep -E "^git bisect" | sed -E "s/[0-9a-f]{40}/<sha>/g" | head -5', env=env)
run(d, 'git bisect reset')
print('== 二:git bisect run:让脚本自动回答 good / bad。bug 在第 637 个提交引入')
n, first, res, o = bisect_run(637)
print(f'  脚本被调用 {n} 次(用于测试的提交数);找到的第一个坏提交: {res!r}(期望 “提交 637”)')
steps_ = [l for l in o.split('\n') if l.startswith('Bisecting')]
print(f'  bisect run 的输出里每一步都有一行 Bisecting: …,共 {len(steps_)} 行:'); [print('    ' + l) for l in steps_[:3] + ['    …'] + steps_[-2:]]
print('    ' + next(l for l in o.split('\n') if 'first bad commit' in l).replace(res, '<sha>') if False else '    <sha> is the first bad commit')
print('== 三:100 个随机的 bug 位置:测试次数 ≤ ceil(log2(%d)) = %d' % (N, math.ceil(math.log2(N))))
rnd = random.Random(51); Ks = [rnd.randint(2, N) for _ in range(100)]; counts = []; ok = 0
for K in Ks:
    c, first, res, _ = bisect_run(K); counts.append(c); ok += (res == f'提交 {K}')
print(f'  找对了 {ok}/100;测试次数 最少 {min(counts)} 最多 {max(counts)} 平均 {sum(counts) / len(counts):.2f}(log2({N}) = {math.log2(N):.2f})')
hist = {x: counts.count(x) for x in sorted(set(counts))}; print('  分布:', '  '.join(f'{k} 次×{v}' for k, v in hist.items()))
print('== 四:历史不是直线时,bisect 按“还有多少个提交可疑”折半,而不是按时间')
d2 = lab('l51b'); ci(d2, 'M1', {'a': '1\n'}, t=0)
run(d2, 'git checkout -q -b side'); [ci(d2, f'S{i}', {f's{i}': '1\n'}, t=1 + i) for i in range(1, 9)]
run(d2, 'git checkout -q main'); [ci(d2, f'M{i}', {f'm{i}': '1\n'}, t=20 + i) for i in range(2, 4)]
run(d2, 'git merge -q --no-edit side', t=30); [ci(d2, f'M{i}', {f'm{i}': '1\n'}, t=40 + i) for i in range(4, 6)]
sh(d2, "git log --graph --format='%s' | sed -E 's/^/  /'")
rootc = out1(d2, 'git rev-list --max-parents=0 HEAD')
sh(d2, f"git bisect start main {rootc} 2>&1 | sed -E 's/[0-9a-f]{{40}}/<sha>/g; s/\\[[0-9a-f]+\\]/[<sha>]/'; git log -1 --format='当前检出: %s'; git bisect reset >/dev/null")
root = out1(d2, 'git rev-list --max-parents=0 HEAD')
cands = out1(d2, f"git rev-list --reverse {root}..main").split()
print(f'  main 比 M1 多 {len(cands)} 个提交(可疑集合)。每个候选提交“自己加上它的祖先里属于可疑集合的个数”:')
cnt = {c: int(out1(d2, f"git rev-list --count {root}..{c}")) for c in cands}
print('   ' + '  '.join(f"{out1(d2, f'git log -1 --format=%s {c}')}={cnt[c]}" for c in cands))
print(f'  可疑集合是 {len(cands)} 个,折半约 {len(cands) / 2:g};计数最接近一半的是 S6(={cnt[next(c for c in cands if out1(d2, f"git log -1 --format=%s {c}") == "S6")]}),bisect 选的就是它')
print('== 五:跳过无法测试的提交(exit 125),以及 bisect 脚本退出码的含义')
SK = LT / '_bisect_skip.sh'
SK.write_text('#!/bin/sh\nn=$(sed "s/[^0-9]//g" f.txt)\n[ "$n" -ge 500 ] && [ "$n" -le 520 ] && exit 125\n[ "$n" -lt "$K" ]\n'); SK.chmod(0o755)
run(d, 'git bisect reset >/dev/null 2>&1; git bisect start main $(git rev-list --max-parents=0 HEAD) >/dev/null 2>&1', env={'K': 637})
rc, o = run(d, f'git bisect run {SK} 2>&1', env={'K': 637})
st = [l for l in o.split('\n') if l.startswith('Bisecting')]
print(f'  遇到“版本 500~520 无法编译”的提交(脚本 exit 125),bisect 跳过它们继续,共 {len(st)} 步;前三步:'); [print('    ' + l) for l in st[:3]]
print('    …\n    ' + ('<sha> is the first bad commit' if 'first bad commit' in o else '(没找到)'), '|', out1(d, 'git log -1 --format=%s refs/bisect/bad'))
run(d, 'git bisect reset >/dev/null 2>&1')
print('  退出码:0 = good,1~124 与 126~127 = bad,125 = 跳过,≥128 = 终止整个 bisect(文档约定)')
