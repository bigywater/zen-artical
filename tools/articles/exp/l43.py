import sys, os, random; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l43')
def content(k, n=100, changed=0):
    L = [f'文件{k}的第{i:03d}行:' + ''.join(random.Random(k * 1000 + i).choice('abcdefghijklmnopqrstuvwxyz') for _ in range(30)) + '\n' for i in range(n)]
    for i in range(changed): L[i * (n // max(changed, 1))] = f'改动过的第{i}行 文件{k} ' + ''.join(random.Random(k * 7 + i).choice('ABCDEFGHIJ') for _ in range(30)) + '\n'
    return ''.join(L)
print('== 一:git 不记录“改名”,每个提交只是新的 tree。改名是比较两个 tree 时才推断出来的')
d = lab('l43a'); ci(d, '基础', {'old.txt': content(1)}, t=0)
run(d, 'git mv old.txt new.txt'); run(d, 'git commit -q -m 改名', 1)
sh(d, 'git cat-file -p HEAD^{tree}; git cat-file -p HEAD~1^{tree}')
sh(d, 'git diff --name-status HEAD~1 HEAD; git diff --name-status --no-renames HEAD~1 HEAD')
print('  (内容完全相同时 blob 的 hash 相同,所以 100% 的改名只要比 hash,不用比内容)')
print('== 二:改名同时改了 N% 的行:相似度分数,以及默认阈值 50% 上下的检测结果')
d = lab('l43b'); files = {f'f{k:02d}.txt': content(k) for k in range(10)}; ci(d, '基础', files, t=0)
run(d, 'for k in 00 01 02 03 04 05 06 07 08 09; do git mv f$k.txt g$k.txt; done')
for k in range(10): W(d, {f'g{k:02d}.txt': content(k, changed=k * 10)})
run(d, 'git add -A; git commit -q -m 改名并修改', 1)
o = out1(d, 'git diff -M --name-status HEAD~1 HEAD').split('\n')
print('  默认(-M,50%):'); [print('    ' + x) for x in o]
print('  改动行数  默认 -M(50%)    -M30%    -M70%    -M90%')
def kind(opt):
    r = {}
    for l in out1(d, f'git diff {opt} --name-status HEAD~1 HEAD').split('\n'):
        p = l.split('\t')
        if p[0].startswith('R'): r[int(p[2][1:3])] = p[0]
        elif p[0] == 'A': r[int(p[1][1:3])] = r.get(int(p[1][1:3]), 'D+A')
    return r
rows = {opt: kind(opt) for opt in ['-M', '-M30%', '-M70%', '-M90%']}
for k in range(10):
    print(f'  {k * 10:>5}%   ' + '   '.join(f'{rows[o].get(k, "D+A"):>8}' for o in ['-M', '-M30%', '-M70%', '-M90%']))
print('== 三:没被识别成改名的,日志里怎么表现:git log 不加 --follow 就只看到新名字的那一个提交')
d = lab('l43c'); ci(d, '创建', {'doc.txt': content(5)}, t=0); ci(d, '修改', {'doc.txt': content(5, changed=5)}, t=1)
run(d, 'git mv doc.txt manual.txt'); W(d, {'manual.txt': content(5, changed=8)}); run(d, 'git add -A; git commit -q -m 改名并大改', 2)
sh(d, 'git log --oneline -- manual.txt | sed -E "s/^[0-9a-f]+ //"; echo "--- --follow:"; git log --oneline --follow -- manual.txt | sed -E "s/^[0-9a-f]+ //"')
sh(d, 'git diff --name-status HEAD~1 HEAD')
d = lab('l43d'); ci(d, '创建', {'doc.txt': content(5)}, t=0); run(d, 'git mv doc.txt manual.txt'); W(d, {'manual.txt': content(5, changed=60)}); run(d, 'git add -A; git commit -q -m "改名并改了60%"', 2)
sh(d, 'git diff --name-status HEAD~1 HEAD; echo "--- --follow:"; git log --oneline --follow -- manual.txt | sed -E "s/^[0-9a-f]+ //"')
print('== 四:renameLimit:要比较的 (删除 × 新增) 对数超过上限时,git 放弃不精确的改名检测')
d = lab('l43e'); N = 1200
W(d, {f'd/a{i:04d}.txt': content(i, n=20) for i in range(N)}); ci(d, '1200 个文件', t=0)
run(d, 'mkdir e; for i in $(seq -w 0 1199); do git mv d/a0$i.txt e/b$i.txt 2>/dev/null || git mv d/a$i.txt e/b$i.txt; done 2>/dev/null')
for i in range(N): W(d, {f'e/b{i:04d}.txt': content(i, n=20, changed=2)})
run(d, 'git add -A; git commit -q -m 全部改名并轻微修改', 1)
sh(d, 'git diff --name-status HEAD~1 HEAD 2>&1 | cut -c1-1 | sort | uniq -c; git diff --name-status HEAD~1 HEAD 2>&1 >/dev/null | head -2')
sh(d, 'git diff -l2000 --name-status HEAD~1 HEAD 2>&1 | cut -c1-1 | sort | uniq -c')
sh(d, 'git -c diff.renameLimit=2000 diff --name-status HEAD~1 HEAD | cut -c1-1 | sort | uniq -c')
t0 = time.perf_counter(); run(d, 'git diff -l2000 --name-status HEAD~1 HEAD'); print(f'  -l2000 的检测耗时: {(time.perf_counter() - t0) * 1000:.0f} ms')
print('== 五:合并时同样靠相似度:改名后内容变化太大,另一边的修改就找不到它了(modify/delete)')
for nm, ch in [('改动 20%', 20), ('改动 70%', 70)]:
    d = lab('l43f'); ci(d, '基础', {'doc.txt': content(7)}, t=0); run(d, 'git checkout -q -b ren'); run(d, 'git mv doc.txt manual.txt'); W(d, {'manual.txt': content(7, changed=ch)}); run(d, 'git add -A; git commit -q -m 改名', 1)
    run(d, 'git checkout -q main'); W(d, {'doc.txt': content(7).replace('文件7的第050行', '文件7的第050行(main 改)')}); run(d, 'git commit -qam main改', 2)
    rc, o = run(d, 'git merge ren 2>&1 | head -3')
    print(f'  改名时改动 {nm}:', o.replace('\n', ' | '))
