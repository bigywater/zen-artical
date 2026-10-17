import sys, os, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l65')
import ll as _ll
def run(d, cmd, t='now', **k): return _ll.run(d, cmd, t, **k)
def sh(d, cmd, t='now', **k): return _ll.sh(d, cmd, t, **k)
def ci(d, msg, files=None, t='now', **k): return _ll.ci(d, msg, files, t, **k)
FB = 'FILTER_BRANCH_SQUELCH_WARNING=1'
def mk(name):
    d = lab(name); ci(d, 'C1 起点', {'a.txt': 'a1\n'}, t=0); ci(d, 'C2 加配置', {'cfg.txt': 'x=1\n'}, t=1)
    ci(d, 'C3 误提交了密码', {'secret.txt': 'password=hunter2\n'}, t=2); ci(d, 'C4 继续开发', {'a.txt': 'a2\n'}, t=3); ci(d, 'C5 又改了密码', {'secret.txt': 'password=hunter3\n'}, t=4); ci(d, 'C6 收尾', {'a.txt': 'a3\n'}, t=5)
    run(d, 'git tag v1 HEAD~2', 5); run(d, "git tag -a v2 -m 注解标签 HEAD~2", 5); return d
print('== 一:git filter-branch 会打印一大段警告,推荐改用 git filter-repo(本机没有安装,未实测)')
d = mk('l65a'); r = subprocess.run('git filter-branch --index-filter "true" HEAD 2>&1 | head -12', shell=True, cwd=d, env=lenv(), capture_output=True, text=True)
for l in r.stdout.split('\n')[:9]: print('  ' + _ll.tidy(l)[:150])
run(d, 'git update-ref -d refs/original/refs/heads/main'); run(d, 'git reset -q --hard ORIG_HEAD' if False else 'true')
print('== 二:--index-filter 从全部历史里删掉 secret.txt:每个提交的 tree 被重写,hash 随之改变')
d = mk('l65b'); old = out1(d, 'git log --format=%h --reverse').split(); oldsub = out1(d, 'git log --format=%s --reverse').split('\n')
sh(d, "git log --stat --format='%s' | grep -E '^(C[0-9]|.*secret)' | head -8")
run(d, f'{FB} git filter-branch -f --index-filter "git rm --cached --ignore-unmatch -q secret.txt" --prune-empty -- --all', 20)
new = out1(d, 'git log --format=%h --reverse').split(); newsub = out1(d, 'git log --format=%s --reverse').split('\n')
print(f'  提交数 {len(old)} → {len(new)}(--prune-empty 把只改了 secret.txt 的提交删掉了:C3 和 C5 里除了密码什么都没改?—— C3 只加了 secret.txt,C5 只改了它,所以消失)')
for i, s_ in enumerate(newsub): print(f'    {s_:<14} {new[i]}')
print(f'  原来的 hash: ' + ' '.join(old))
sh(d, "git log --stat --format='%s' | grep -c secret | sed 's/^ */当前历史里提到 secret 的行数: /'; git ls-files | tr '\\n' ' '; echo")
print('== 三:数据并没有消失:refs/original 备份、reflog、对象库都还保留着旧历史')
sh(d, 'git for-each-ref --format="%(refname)" | head; echo ---; git rev-parse refs/original/refs/heads/main | cut -c1-7 | sed "s/^/备份的旧 main = /"')
sec = out1(d, f"git rev-list --all --objects refs/original/refs/heads/main | grep secret.txt | head -1 | cut -d' ' -f1") or out1(d, "git rev-list --objects refs/original/refs/heads/main | grep secret | cut -d' ' -f1 | head -1")
oldmain = out1(d, 'git rev-parse refs/original/refs/heads/main'); blob = out1(d, f"git ls-tree {oldmain} secret.txt | awk '{{print $3}}'")
print(f'  旧历史里的密码 blob 还能读出来: {out1(d, f"git cat-file -p {blob}")!r}')
newc4 = new[2]; oldc4 = old[3]
print('  标签呢?-- --all 把所有 ref 都纳入改写。轻量标签 v1 被重写到新历史;但注解标签 v2 的 tag 对象本身没有被重写(没有 --tag-name-filter),仍指向旧的 C4:')
print(f'    v1(轻量)指向 {out1(d, "git rev-parse --short v1")}(新 C4 是 {newc4},旧 C4 是 {oldc4}):重写了: {out1(d, "git rev-parse --short v1") == newc4}')
print(f'    v2(注解)指向 {out1(d, "git rev-parse --short v2^{commit}")}:仍是旧 C4: {out1(d, "git rev-parse --short v2^{commit}") == oldc4}')
print(f'    旧历史里的 C3(第一次提交密码)可以从 v2 到达: {run(d, f"git merge-base --is-ancestor {old[2]} v2^{{commit}}")[0] == 0}')
print('== 四:要真正删掉密码,得清掉所有指向旧历史的引用(refs/original、没改写的标签),再 reflog expire + gc --prune=now')
run(d, "git for-each-ref --format='%(refname)' refs/original | xargs -n1 git update-ref -d; git reflog expire --expire=now --all; git gc -q --prune=now", 21)
print(f'  只清掉 refs/original 之后:旧 C3 提交还在吗: {run(d, f"git cat-file -e {old[2]}")[0] == 0}(v2 还引用着旧历史);旧密码 blob(hunter3,C5)还在吗: {run(d, f"git cat-file -e {blob}")[0] == 0}')
run(d, "git tag -d v2; git tag -a v2 -m 注解标签 v1", 22)
run(d, 'git reflog expire --expire=now --all; git gc -q --prune=now', 23)
print(f'  再把 v2 重建到新历史上之后:旧 C3 提交还在吗: {run(d, f"git cat-file -e {old[2]}")[0] == 0};旧密码 blob 还在吗: {run(d, f"git cat-file -e {blob}")[0] == 0}')
print('  (推送到别人已经克隆过的远程之后,别人手里的副本不会因此消失——这一步只清了本地)')
print('== 五:--tag-name-filter cat 让注解标签对象也跟着重写')
d = mk('l65c'); oldc4 = out1(d, 'git rev-parse --short v2^{commit}')
run(d, f'{FB} git filter-branch -f --tag-name-filter cat --index-filter "git rm --cached --ignore-unmatch -q secret.txt" -- --all', 20)
print(f'  v2(注解)指向的提交变了: {out1(d, "git rev-parse --short v2^{commit}") != oldc4};v2 的说明: {out1(d, "git log -1 --format=%s v2^{commit}")}')
print('== 六:速度:tree-filter 要把每个提交检出到磁盘,index-filter 只改暂存区;300 个提交、每个提交约 50 个文件')
d = lab('l65d'); W(d, {f'f{i:02d}.txt': f'{i}\n' for i in range(50)}); ci(d, '起点', t=0)
for i in range(1, 300): ci(d, f'提交 {i}', {f'f{i % 50:02d}.txt': f'版本 {i}\n'}, t=i) if False else None
out = []; t0 = int(BASE_T.timestamp()); mark = 0
for i in range(1, 300):
    mark += 1; body = f'版本 {i}\n'
    out.append(f'commit refs/heads/main\ncommitter A <a@e> {t0 + i * 60} +0000\ndata 2\nx\n' + ('from refs/heads/main^0\n' if i == 1 else '') + f'M 100644 inline f{i % 50:02d}.txt\ndata {len(body.encode())}\n{body}\n')
subprocess.run([GIT, 'fast-import', '--quiet'], cwd=d, env=lenv(), input=''.join(out).encode(), check=True); run(d, 'git checkout -q -f main')
n = int(out1(d, 'git rev-list --count HEAD'))
for nm, flt in [('--index-filter', '--index-filter "git rm --cached --ignore-unmatch -q f00.txt"'), ('--tree-filter', '--tree-filter "rm -f f00.txt"')]:
    dd = LT / 'l65e'; shutil.rmtree(dd, ignore_errors=True); shutil.copytree(d, dd, symlinks=True)
    t0_ = time.perf_counter(); run(dd, f'{FB} git filter-branch -f {flt} -- main', 40); t = (time.perf_counter() - t0_)
    print(f'  {nm:<14}{t:>6.1f} 秒(重写 {n} 个提交;f00.txt 还在历史里吗: {out1(dd, "git log --format=%H -- f00.txt | wc -l").strip() != "0"})')
