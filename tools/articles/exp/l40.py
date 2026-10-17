import sys, os, random, itertools; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l40')
import ll as _ll
def run(d, cmd, t='now', **k): return _ll.run(d, cmd, t, **k)
def ci(d, msg, files=None, t='now', **k): return _ll.ci(d, msg, files, t, **k)
def short(d, rev): return out1(d, f'git log -1 --format=%s {rev}')
print('== 一:最简单的分叉:main 与 feature 从 M1 分开,merge-base 就是分叉点')
d = lab('l40a'); ci(d, 'M0', {'a': '0\n'}); ci(d, 'M1', {'a': '1\n'}); run(d, 'git checkout -q -b feature'); ci(d, 'F1', {'f': '1\n'}); ci(d, 'F2', {'f': '2\n'})
run(d, 'git checkout -q main'); ci(d, 'M2', {'a': '2\n'}); ci(d, 'M3', {'a': '3\n'})
sh(d, 'git log --graph --oneline --all | sed -E "s/[0-9a-f]{7} //"')
print(f'  git merge-base main feature → {short(d, "$(git merge-base main feature)")}')
print(f'  用集合算:main 的祖先 ∩ feature 的祖先 = {sorted(short(d, c) for c in set(out1(d, "git rev-list main").split()) & set(out1(d, "git rev-list feature").split()))};其中不是别的公共祖先的祖先的那个,就是 merge-base')
print('== 二:criss-cross(交叉合并)会有两个最佳公共祖先')
d = lab('l40b'); ci(d, 'R', {'a': 'r\n'}); run(d, 'git checkout -q -b A'); ci(d, 'A1', {'a1': '1\n'}); run(d, 'git checkout -q -b B R~0 2>/dev/null || git checkout -q -b B main')
run(d, 'git checkout -q main'); run(d, 'git checkout -q -B B main'); ci(d, 'B1', {'b1': '1\n'})
run(d, 'git checkout -q A'); run(d, 'git merge -q --no-edit -m "A 合并 B1" B'); run(d, 'git checkout -q B'); run(d, 'git merge -q --no-edit -m "B 合并 A1" A~1')
run(d, 'git checkout -q A'); ci(d, 'A2', {'a2': '1\n'}); run(d, 'git checkout -q B'); ci(d, 'B2', {'b2': '1\n'})
sh(d, 'git log --graph --oneline --all | sed -E "s/[0-9a-f]{7} //"')
sh(d, 'git merge-base A B | wc -l; git merge-base --all A B | wc -l; for c in $(git merge-base --all A B); do git log -1 --format="  最佳公共祖先: %s" $c; done')
print('== 三:Python 暴力算最佳公共祖先,和 git merge-base --all 比对:随机 DAG 300 个提交、300 对随机提交')
def build(name, N, seed, skew):
    rnd = random.Random(seed); d = lab(name); t0 = int(BASE_T.timestamp()); out = []
    parents = {}
    for i in range(1, N + 1):
        ps = [] if i == 1 else [rnd.randint(max(1, i - 8), i - 1)]
        if i > 4 and rnd.random() < 0.3:
            q = rnd.randint(1, i - 1)
            if q not in ps: ps.append(q)
        parents[i] = ps
        t = t0 + i * 60 + (rnd.randint(-skew, skew) if skew else 0)
        body = f'{i}\n'
        out.append(f'commit refs/heads/main\nmark :{i}\ncommitter A <a@e> {t} +0000\ndata 2\nx\n' + (f'from :{ps[0]}\n' if ps else '') + ''.join(f'merge :{q}\n' for q in ps[1:]) + f'M 100644 inline f\ndata {len(body)}\n{body}\n')
    r = subprocess.run([GIT, 'fast-import', '--quiet', f'--export-marks={d / "marks"}'], cwd=d, env=lenv(), input=''.join(out).encode(), capture_output=True); assert r.returncode == 0, r.stderr
    sha = {int(l.split()[0][1:]): l.split()[1] for l in (d / 'marks').read_text().split('\n') if l}
    return d, parents, sha
def anc(parents, i, memo={}):
    key = id(parents)
    s = {i}; st = [i]
    while st:
        x = st.pop()
        for p in parents[x]:
            if p not in s: s.add(p); st.append(p)
    return s
def best(parents, a, b):
    common = anc(parents, a) & anc(parents, b)
    drop = set()
    for c in common:
        for p in parents[c]: drop |= anc(parents, p)
    return common - drop
def compare(d, parents, sha, pairs):
    inv = {v: k for k, v in sha.items()}; ok = 0; multi = 0
    inp = '\n'.join(f'{sha[a]} {sha[b]}' for a, b in pairs)
    for a, b in pairs:
        g = set(inv[x] for x in out1(d, f'git merge-base --all {sha[a]} {sha[b]}').split())
        e = best(parents, a, b); ok += (g == e); multi += (len(e) > 1)
    return ok, multi
for label, skew in [('时间戳正常递增', 0), ('时间戳乱序(±2 小时的偏差,模拟时钟不同步)', 7200)]:
    d, parents, sha = build('l40c', 300, 40, skew); rnd = random.Random(1); pairs = [(rnd.randint(1, 300), rnd.randint(1, 300)) for _ in range(300)]
    ok1, multi = compare(d, parents, sha, pairs)
    run(d, 'git commit-graph write --reachable'); ok2, _ = compare(d, parents, sha, pairs)
    print(f'  {label}:无 commit-graph {ok1}/300 一致;写入 commit-graph 之后 {ok2}/300 一致;其中有 {multi} 对存在多个最佳公共祖先')
print('== 四:--is-ancestor、--independent、--octopus')
d = LT / 'l40a'
sh(d, 'git merge-base --is-ancestor feature main; echo "feature 是 main 的祖先吗?退出码 $?"; git merge-base --is-ancestor main~2 main; echo "main~2 是 main 的祖先吗?退出码 $?"')
run(d, 'git checkout -q -b third main~3'); ci(d, 'T1', {'t': '1\n'}); run(d, 'git checkout -q main')
sh(d, 'git merge-base --octopus main feature third | xargs -I{} git log -1 --format="三个分支的公共祖先: %s" {}')
sh(d, 'git merge-base --independent main feature third main~1 | xargs -I{} git log -1 --format="  独立的(不是彼此祖先的)提交: %s" {}')
print('== 五:--fork-point:上游被 rebase / 强推之后,从 reflog 里找这个分支原来的分叉点')
shutil.rmtree(LT / 'l40up.git', ignore_errors=True); shutil.rmtree(LT / 'l40cl', ignore_errors=True)
seed = lab('l40seed'); ci(seed, 'U1', {'a': '1\n'}); ci(seed, 'U2', {'a': '2\n'}); run(seed, f'git clone -q --bare . {LT / "l40up.git"}')
run(LT, f'git clone -q {LT / "l40up.git"} l40cl'); cl = LT / 'l40cl'; run(cl, 'git config user.name A; git config user.email a@e')
run(cl, 'git checkout -q -b topic'); ci(cl, 'T1', {'t': '1\n'}); ci(cl, 'T2', {'t': '2\n'})
b_before = short(cl, '$(git merge-base origin/main topic)')
run(seed, 'git checkout -q -B rewrite HEAD~1'); ci(seed, 'U2 重写', {'a': '2 重写\n'}); ci(seed, 'U3', {'a': '3\n'}); run(seed, f'git push -q -f {LT / "l40up.git"} rewrite:main')
run(cl, 'git fetch -q origin')
print(f'  上游把 U2 重写成 U2重写(强推)。topic 原来基于 {b_before}。')
print(f'  普通 git merge-base origin/main topic        → {short(cl, "$(git merge-base origin/main topic)")}  (U1:两条历史唯一共同的祖先)')
fp = out1(cl, 'git merge-base --fork-point origin/main topic'); print(f'  git merge-base --fork-point origin/main topic → {short(cl, fp) if fp else "(无)"}  (U2:用 origin/main 的 reflog 找到它旧的位置)')
sh(cl, "git reflog show origin/main --format='%gd: %gs' | head -3")
print('  rebase --onto 的典型用法:git rebase --onto origin/main $(git merge-base --fork-point origin/main topic) topic')
