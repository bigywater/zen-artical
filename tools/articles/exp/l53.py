import sys, os, random, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l53')
D = LT / 'l53'; shutil.rmtree(D, ignore_errors=True); D.mkdir(parents=True)
ALGS = ['myers', 'minimal', 'patience', 'histogram']
def gdiff(a, b, alg, extra=''):
    pa, pb = D / 'a.txt', D / 'b.txt'; pa.write_text(a); pb.write_text(b)
    r = subprocess.run([GIT, 'diff', '--no-index', f'--diff-algorithm={alg}', '--no-color', *extra.split(), str(pa), str(pb)], capture_output=True, text=True, env=lenv())
    return r.stdout
def counts(t): return sum(1 for l in t.split('\n') if l.startswith('+') and not l.startswith('+++')), sum(1 for l in t.split('\n') if l.startswith('-') and not l.startswith('---')), t.count('\n@@')
def body(t): return '\n'.join(l for l in t.split('\n')[4:] if l)
print('== 一:同一对文件,不同的算法给出不同的 diff(都是正确的,只是对齐方式不同)。下面是从随机小文件里搜出的第一个 Myers 与 patience 输出不同的例子')
rs = random.Random(5); W_ = ['{', '}', '', 'x();', 'y();', 'return;', 'if (a) {', '} else {']
found = None
for _ in range(20000):
    A = [rs.choice(W_) for _ in range(rs.randint(8, 14))]; B = list(A)
    for _ in range(rs.randint(1, 3)):
        i = rs.randrange(len(B) + 1); B[i:i] = [rs.choice(W_) for _ in range(rs.randint(2, 4))]
        if rs.random() < 0.5 and len(B) > 6: j = rs.randrange(len(B) - 3); del B[j:j + rs.randint(1, 3)]
    sa, sb = '\n'.join(A) + '\n', '\n'.join(B) + '\n'
    ta, tb = gdiff(sa, sb, 'myers'), gdiff(sa, sb, 'patience')
    if body(ta) != body(tb) and counts(ta)[:2] != counts(tb)[:2] and len(A) <= 12 and len(B) <= 14: found = (sa, sb); break
sa, sb = found; EXA, EXB = found
print('  旧: ' + ' '.join(repr(l) if l else '<空>' for l in sa.rstrip('\n').split('\n')))
print('  新: ' + ' '.join(repr(l) if l else '<空>' for l in sb.rstrip('\n').split('\n')))
for alg in ALGS:
    t = gdiff(sa, sb, alg); p_, m_, h_ = counts(t)
    print(f'  [{alg}] +{p_} -{m_}  {h_} 个 hunk'); [print('    ' + (l if l.strip() else l + '·')) for l in body(t).split('\n')[1:] if l]
print('== 二:随机编辑 300 次(一个 200 行的文件做若干次插入、删除、整段搬动),统计各算法的改动行数')
rnd = random.Random(53); words = ['}', '{', 'return 0;', 'if (x) {', 'else {', 'break;', 'i++;', '', '    ', 'foo();', 'bar();', '/* c */']
def mkfile(n): return [rnd.choice(words) + (f' // {rnd.randint(0, 40)}' if rnd.random() < 0.5 else '') for _ in range(n)]
tot = {a: [0, 0] for a in ALGS}; differ = 0; best_cnt = {a: 0 for a in ALGS}; examples = []
for t_ in range(300):
    A = mkfile(200); B = list(A)
    for _ in range(rnd.randint(3, 8)):
        op = rnd.choice(['ins', 'del', 'move']); i = rnd.randrange(len(B))
        if op == 'ins': B[i:i] = mkfile(rnd.randint(1, 8))
        elif op == 'del': del B[i:i + rnd.randint(1, 8)]
        else: seg = B[i:i + rnd.randint(2, 10)]; del B[i:i + len(seg)]; j = rnd.randrange(len(B)); B[j:j] = seg
    sa, sb = '\n'.join(A) + '\n', '\n'.join(B) + '\n'; cs = {}
    for alg in ALGS:
        p, m, h = counts(gdiff(sa, sb, alg)); cs[alg] = p + m; tot[alg][0] += p + m; tot[alg][1] += h
    mn = min(cs.values())
    for alg in ALGS: best_cnt[alg] += (cs[alg] == mn)
    if len(set(cs.values())) > 1: differ += 1
print(f'  {"算法":<10}{"改动行数合计(+ 和 −)":>22}{"hunk 数合计":>14}{"改动行数最少的次数":>20}')
for alg in ALGS: print(f'  {alg:<10}{tot[alg][0]:>22,}{tot[alg][1]:>14,}{best_cnt[alg]:>20}')
print(f'  300 次里有 {differ} 次四种算法给出的改动行数不全相同;minimal 保证每次都是最少的(它的“最少次数”应该是 300)')
print('== 三:速度:20 万行的文件,约 2% 的行被改动(替换、插入、删除),各算法的耗时(5 次中位数)')
base = [f'line {i:06d} ' + 'x' * 20 for i in range(200000)]; new = list(base); r2 = random.Random(2)
for _ in range(4000):
    i = r2.randrange(len(new)); op = r2.choice(['r', 'i', 'd'])
    if op == 'r': new[i] = f'changed {i} ' + 'y' * 10
    elif op == 'i': new.insert(i, f'inserted {i}')
    elif op == 'd': del new[i]
(D / 'big_a.txt').write_text('\n'.join(base) + '\n'); (D / 'big_b.txt').write_text('\n'.join(new) + '\n')
for alg in ALGS:
    ts = []
    for _ in range(5):
        t0 = time.perf_counter(); subprocess.run([GIT, 'diff', '--no-index', '--stat', f'--diff-algorithm={alg}', str(D / 'big_a.txt'), str(D / 'big_b.txt')], capture_output=True, env=lenv()); ts.append((time.perf_counter() - t0) * 1000)
    print(f'  {alg:<10} {median(ts):>7.1f} ms')
print('== 四:怎么选:配置与命令行选项')
d = lab('l53r'); ci(d, 'x', {'f.c': EXA}, t=0); W(d, {'f.c': EXB})
sh(d, 'git config --get diff.algorithm || echo "diff.algorithm 未设置(默认 myers)"; git config diff.algorithm histogram; git diff --stat | tail -1; git diff --diff-algorithm=myers --stat | tail -1')
sh(d, 'git diff --patience --stat | tail -1; git diff --histogram --stat | tail -1; git diff --minimal --stat | tail -1')
