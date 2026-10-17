import sys, os, random; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l55')
d = lab('l55')
ci(d, 'C1 新增 foo 的调用', {'a.txt': 'start\nresult = foo(1)\nend\n'}, t=0)
ci(d, 'C2 改参数 foo(1) → foo(2)', {'a.txt': 'start\nresult = foo(2)\nend\n'}, t=1)
ci(d, 'C3 把 foo 这行挪到末尾', {'a.txt': 'start\nend\nresult = foo(2)\n'}, t=2)
ci(d, 'C4 再加一处 foo 调用', {'a.txt': 'start\nend\nresult = foo(2)\nother = foo(3)\n'}, t=3)
ci(d, 'C5 删掉第一处 foo', {'a.txt': 'start\nend\nother = foo(3)\n'}, t=4)
ci(d, 'C6 删掉全部 foo', {'a.txt': 'start\nend\n'}, t=5)
LG = "git log --format=%s --reverse"
print('== 一:-S 数的是“字符串出现的次数有没有变”;-G 看的是“diff 里被增删的行是否匹配正则”')
for opt in ["-S'foo'", "-G'foo'", "-S'foo(2)'", "-G'foo\\(2\\)'"]:
    print(f'  git log {opt:<14}→ ' + ' | '.join(out1(d, f'{LG} {opt}').split('\n')))
print('  逐个提交 foo 的出现次数(整个文件):')
for c in out1(d, 'git log --format=%h --reverse').split('\n'):
    n = out1(d, f"git show {c}:a.txt | grep -o 'foo' | wc -l").strip(); print(f'    {out1(d, f"git log -1 --format=%s {c}")}  → {n} 次')
print('  C2(改参数)和 C3(挪行)的 foo 次数没变,-S 看不到,-G 能看到;C4 增加一次、C5/C6 减少,两者都能看到')
print('== 二:-S 加 -p:看到的是每个命中的提交里增删 foo 的那些行')
sh(d, "git log -S'foo(3)' -p --format='%s' | grep -E '^(C[0-9]|[+-][^+-])'")
print('== 三:--pickaxe-regex 让 -S 的参数按正则处理;-G 默认就是正则')
for opt in ["-S'foo\\(.\\)' --pickaxe-regex", "-G'foo\\(.\\)'", "-S'foo\\(.\\)'"]:
    print(f'  git log {opt:<36}→ ' + ' | '.join((out1(d, f'{LG} {opt}') or '(无)').split('\n')))
print('== 四:--pickaxe-all:命中的提交里,默认只显示匹配的文件,加它显示整个提交的所有改动')
d2 = lab('l55b'); ci(d2, 'base', {'a.txt': 'a\n', 'b.txt': 'b\n'}, t=0); ci(d2, '同时改 a.txt(加 needle)和 b.txt', {'a.txt': 'a\nneedle\n', 'b.txt': 'b\nb2\n'}, t=1)
sh(d2, "git log -S'needle' --stat --format='%s'; echo ---; git log -S'needle' --pickaxe-all --stat --format='%s'")
print('== 五:大历史上的耗时:3000 个提交,100 个文件,每个提交改其中一个;在第 2345 个提交里引入了字符串 “UNIQUE_TOKEN”')
d3 = lab('l55c')
fl = lambda i: f'f{i % 100:02d}.txt'
out = []; t0 = int(BASE_T.timestamp()); mark = 0
for i in range(1, 3001):
    mark += 1; body = f'版本 {i} 的内容\n' + ''.join(f'line {j} of file {i % 100}\n' for j in range(50)) + ('UNIQUE_TOKEN here\n' if i == 2345 else '')
    out.append(f'commit refs/heads/main\nmark :{mark}\ncommitter A <a@e> {t0 + i * 60} +0000\ndata 2\nx\n' + (f'from :{mark - 1}\n' if mark > 1 else '') + f'M 100644 inline {fl(i)}\ndata {len(body.encode())}\n{body}\n')
r = subprocess.run([GIT, 'fast-import', '--quiet'], cwd=d3, env=lenv(), input=''.join(out).encode(), capture_output=True); assert r.returncode == 0, r.stderr
run(d3, 'git checkout -q -f main')
def bench(cmd, n=5):
    ts = []
    for _ in range(n):
        t0 = time.perf_counter(); o = run(d3, cmd)[1]; ts.append((time.perf_counter() - t0) * 1000)
    return median(ts), o
for nm, cmd in [("git log -S'UNIQUE_TOKEN'", "git log -S'UNIQUE_TOKEN' --format=%h"), ("git log -G'UNIQUE_TOKEN'", "git log -G'UNIQUE_TOKEN' --format=%h"), ("git log -p | grep(笨办法)", "git log -p | grep -c UNIQUE_TOKEN"), ("git log --format=%h(不比较内容)", "git log --format=%h | tail -1")]:
    t, o = bench(cmd); print(f'  {nm:<34} {t:>8.0f} ms   输出: {o.split(chr(10))[0][:10]}')
hits = out1(d3, "git log -S'UNIQUE_TOKEN' --format=%H").split(); allc = out1(d3, 'git log --format=%H --reverse').split()
print('  -S 命中了 %d 个提交,在历史里分别排第 %s 个(从最早数起):第 2345 个引入了这个字符串;第 2445 个是同一个文件 f45.txt 下一次被改写,把它删掉了' % (len(hits), '、'.join(str(allc.index(h) + 1) for h in reversed(hits))))
