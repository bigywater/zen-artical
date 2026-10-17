import sys, os, random; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l31')
d = lab('l31')
print('== 一:index 里每个文件都存了一份 stat 信息:ctime、mtime、dev、ino、权限、uid、gid、大小')
ci(d, '起点', {'a.txt': 'hello\n', 'src/b.txt': 'bbbbbb\n', 'src/deep/c.txt': 'c\n'}, t=0)
ver, ents, exts = parse_index(d / '.git' / 'index'); print(f'  index 版本 {ver},{len(ents)} 个条目,扩展块: {exts}')
print(f'  {"路径":<16}{"size":>5} {"mtime(秒.纳秒)":>22}  ino      mode    与 stat 一致?')
for e in ents:
    st = os.stat(d / e['path']); ok = (e['size'] == st.st_size and e['mtime'] == (st.st_mtime_ns // 10**9, st.st_mtime_ns % 10**9) and e['ino'] == st.st_ino % 2**32 and e['mode'] == 0o100000 | (st.st_mode & 0o777) and e['ctime'] == (st.st_ctime_ns // 10**9, st.st_ctime_ns % 10**9))
    print(f'  {e["path"]:<16}{e["size"]:>5} {e["mtime"][0]}.{e["mtime"][1]:09d}  {e["ino"]:<9}{e["mode"]:o}  {ok}')
print('== 二:git status 怎么判断“没改”:所有 stat 字段都和 index 里一致,就不去读文件内容')
print('  只 touch(内容不变,mtime 变了):status 无输出,但要重新读文件算 hash,再把新的 stat 写回 index')
a0 = parse_index(d / '.git' / 'index')[1][0]['mtime']
time.sleep(1.1); os.utime(d / 'a.txt', None)
sh(d, 'git status --short; echo "(status 为空:内容没变)"')
a1 = parse_index(d / '.git' / 'index')[1][0]['mtime']; print(f'  a.txt 在 index 里的 mtime: {a0[0]}.{a0[1]:09d} → {a1[0]}.{a1[1]:09d}(git status 顺手刷新了 index)')
print('== 三:stat 缓存的盲点:内容改了、大小不变、mtime 手工恢复,git status 看不出来(需要 core.trustctime=false,否则 ctime 会暴露)')
def fresh_orig():
    time.sleep(1.1); run(d, 'git status --short')   # 等过 racy 窗口,让 index 里的 stat 是干净的
    st = os.stat(d / 'a.txt'); return (st.st_atime_ns, st.st_mtime_ns)
def corrupt(orig):
    with open(d / 'a.txt', 'r+b') as f: f.write(b'HELLO\n')   # 同样 6 个字节,原地改写
    os.utime(d / 'a.txt', ns=orig)                           # 把 mtime 恢复成原来的
orig = fresh_orig(); corrupt(orig)
sh(d, 'cat a.txt; git status --short; echo "(默认配置:原地改写会更新 ctime,git 发现 stat 不同,重新比较内容,报告 M)"')
run(d, 'git checkout -q -- a.txt'); orig = fresh_orig(); corrupt(orig)
sh(d, 'git config core.trustctime false; git config core.checkStat minimal; cat a.txt; git status --short; echo "(trustctime=false + checkStat=minimal:只比较 mtime 和 size,没有任何输出,看不出改动)"; git diff --stat | wc -l')
sh(d, 'echo "工作区文件的 blob hash : $(git hash-object a.txt | cut -c1-12)"; echo "index 里记的 blob hash : $(git rev-parse :a.txt | cut -c1-12)"; echo "(两者不同:内容确实变了,只是 git status 的 stat 比较没发现)"')
sh(d, 'git config --unset core.trustctime; git config --unset core.checkStat; git status --short; echo "(恢复默认比较后,ctime 暴露了改动)"')
run(d, 'git config --unset core.trustctime; git config --unset core.checkStat; git checkout -q -- a.txt')
print('== 四:stat 缓存有多重要:10,000 个小文件,git status 的耗时(3 次中位数)')
d2 = lab('l31b'); rnd = random.Random(31)
W(d2, {f'd{i // 100:02d}/f{i:05d}.txt': f'内容 {i} ' + 'x' * rnd.randint(200, 800) + '\n' for i in range(10000)}); ci(d2, '10000 个文件', t=0)
def bench(cmd, n=3):
    ts = []
    for _ in range(n):
        t0 = time.perf_counter(); run(d2, cmd); ts.append((time.perf_counter() - t0) * 1000)
    return median(ts)
t_warm = bench('git status --short')
def touch_all():
    now = time.time_ns()
    for p in (d2).rglob('*.txt'): os.utime(p, ns=(now, now))
ts = []
for _ in range(3):
    touch_all(); t0 = time.perf_counter(); run(d2, 'git status --short'); ts.append((time.perf_counter() - t0) * 1000)
t_cold = median(ts); time.sleep(1.1); run(d2, 'git status --short'); t_after = bench('git status --short')   # 等过 racy 窗口(见下一篇 racy git)再测
print(f'  stat 缓存有效:git status {t_warm:.0f} ms')
print(f'  把 10,000 个文件的 mtime 全部改掉(内容不变)后的第一次 git status(要重读全部文件算 hash){t_cold:.0f} ms')
print(f'  等过 1 秒、再跑一次让 index 刷新之后的 git status(原因见下一篇 racy git:刚被改过的文件会被认为“可能 racy”){t_after:.0f} ms')
print('== 五:cp -a 搬走整个仓库:inode 变了,index 里的 ino 全部失效')
shutil.rmtree(LT / 'l31c', ignore_errors=True); run(LT, 'cp -a l31b l31c')
t0 = time.perf_counter(); run(LT / 'l31c', 'git status --short'); t_cp = (time.perf_counter() - t0) * 1000
t0 = time.perf_counter(); run(LT / 'l31c', 'git status --short'); t_cp2 = (time.perf_counter() - t0) * 1000
print(f'  cp -a 之后第一次 git status {t_cp:.0f} ms,第二次 {t_cp2:.0f} ms')
shutil.rmtree(LT / 'l31c', ignore_errors=True); run(LT, 'cp -a l31b l31c')
run(LT / 'l31c', 'git config core.checkStat minimal; git config core.trustctime false')
t0 = time.perf_counter(); run(LT / 'l31c', 'git status --short'); t_min = (time.perf_counter() - t0) * 1000
print(f'  同样 cp -a,设置 core.checkStat=minimal(只看 mtime 和 size)和 core.trustctime=false 之后第一次 git status {t_min:.0f} ms')
