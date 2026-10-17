import sys, os, re, random; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ll import *
tee('l61')
import ll as _ll
def run(d, cmd, t='now', **k): return _ll.run(d, cmd, t, **k)
def sh(d, cmd, t='now', **k): return _ll.sh(d, cmd, t, **k)
def ci(d, msg, files=None, t='now', **k): return _ll.ci(d, msg, files, t, **k)
rnd = random.Random(61)
def commits(d, ref, n, start, tag, parent_ref=None):
    """用 fast-import 在 ref 上追加 n 个提交(每个改 f.txt)。"""
    out = []; t0 = int(BASE_T.timestamp()) + start * 60
    for i in range(n):
        body = f'{tag} {i}\n'
        out.append(f'commit {ref}\ncommitter A <a@e> {t0 + i} +0000\ndata {len(f"{tag}{i}".encode())}\n{tag}{i}\n' + (f'from {parent_ref}^0\n' if (i == 0 and parent_ref) else '') + f'M 100644 inline {tag}.txt\ndata {len(body.encode())}\n{body}\n')
    subprocess.run([GIT, 'fast-import', '--quiet'], cwd=d, env=lenv(), input=''.join(out).encode(), check=True)
def tr(d, cmd):
    rc, o = run(d, f'GIT_TRACE_PACKET=1 {cmd} 2>&1 >/dev/null | grep "packet:"')
    return [l for l in o.split('\n') if l]
srv = lab('l61srv'); commits(srv, 'refs/heads/main', 1000, 0, 'base'); R = LT / 'l61remote.git'; shutil.rmtree(R, ignore_errors=True); run(srv, f'git clone -q --bare . {R}')
def newclient(name):
    c = LT / name; shutil.rmtree(c, ignore_errors=True); run(LT, f'git clone -q file://{R} {name}'); return c
print('== 一:客户端只是落后:服务端多了 50 个提交,客户端没有本地提交。协商一轮就结束,但第一轮就发了一批 have')
c = newclient('l61a'); commits(srv, 'refs/heads/main', 50, 2000, 'srv1', 'refs/heads/main'); run(srv, f'git push -q {R} +main:main')
L = tr(c, 'git fetch origin')
print(f'  客户端发出的 have: {sum(1 for l in L if re.search(r"fetch> have ", l))} 个;fetch 命令 {sum(1 for l in L if "fetch> command=fetch" in l)} 次;want {sum(1 for l in L if re.search(r"fetch> want ", l))} 个')
sh(c, 'git fetch -q 2>&1; git rev-list --count origin/main..origin/main; git log --oneline origin/main | wc -l | sed "s/^ */origin\\/main 现在的提交数: /"')
print('== 二:客户端有很多服务端不知道的本地提交(500 个),服务端也有新提交:客户端不知道哪个是共同祖先,要发很多个 have')
res = {}
for alg in ['(未设置)', 'consecutive', 'skipping', 'noop']:
    c = newclient('l61b'); commits(c, 'refs/heads/local', 500, 50000, 'loc', 'refs/heads/main')   # 本地独有的 500 个提交(时间比服务端的任何提交都新,协商按时间从新到旧走)
    commits(srv, 'refs/heads/main', 50, 4000 + len(res) * 100, f'srv{len(res) + 2}', 'refs/heads/main'); run(srv, f'git push -q {R} +main:main')
    szf = lambda: sum(f.stat().st_size for f in (c / '.git' / 'objects').rglob('*') if f.is_file())
    s0 = szf()
    L = tr(c, ('git ' if alg == '(未设置)' else f'git -c fetch.negotiationAlgorithm={alg} ') + 'fetch origin main')
    haves = sum(1 for l in L if re.search(r'fetch> have ', l)); rounds = sum(1 for l in L if 'fetch> command=fetch' in l)
    res[alg] = (haves, rounds, int(out1(c, "git count-objects -v | awk '/^in-pack|^count/{s+=$2} END{print s}'")))
    print(f'  fetch.negotiationAlgorithm={alg:<14}客户端发出 have {haves:>4} 个,fetch 命令 {rounds} 轮;对象库增加 {(szf() - s0) / 1024:.0f} KB')
print('  (consecutive:沿着本地历史一个个往前发 have;skipping:跳着发,间隔越来越大,更快找到共同点;noop:一个 have 都不发——只适合 partial clone 之类的场合,会下载更多)')
print('== 三:--negotiation-tip 限制协商只从某些提交出发,本地分支再多也不影响')
c = newclient('l61c'); commits(c, 'refs/heads/local', 500, 50000, 'loc', 'refs/heads/main'); commits(srv, 'refs/heads/main', 50, 6000, 'srv9', 'refs/heads/main'); run(srv, f'git push -q {R} +main:main')
L = tr(c, 'git fetch --negotiation-tip=origin/main origin main')
print(f'  git fetch --negotiation-tip=origin/main:客户端发出 have {sum(1 for l in L if re.search(r"fetch> have ", l))} 个,fetch 命令 {sum(1 for l in L if "fetch> command=fetch" in l)} 轮')
print('== 四:服务端只发缺的对象;对已有文件的小改动用 thin pack(对客户端已有的对象做 delta)')
big = LT / 'l61big_src'; shutil.rmtree(big, ignore_errors=True); bs = lab('l61big_src')
BIG = ''.join(''.join(rnd.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(70)) + '\n' for _ in range(3000))   # 约 210 KB 的随机文本
ci(bs, 'v1', {'big.txt': BIG}, t=0); RB = LT / 'l61big.git'; shutil.rmtree(RB, ignore_errors=True); run(bs, f'git clone -q --bare . {RB}')
cb = LT / 'l61bigc'; shutil.rmtree(cb, ignore_errors=True); run(LT, f'git clone -q file://{RB} l61bigc')
ci(bs, 'v2 只改一行', {'big.txt': BIG.replace(BIG.split('\n')[100], 'CHANGED ' + BIG.split('\n')[100])}, t=1); run(bs, f'git push -q {RB} main')
r = subprocess.run('git fetch --progress origin 2>&1 | tr "\\r" "\\n" | grep -E "remote: Total"', shell=True, cwd=cb, env=lenv(), capture_output=True, text=True)
print('  服务端打包的摘要:', r.stdout.strip()[:110])
nb = lambda opt: int(subprocess.run(f'printf "main\\n^main~1\\n" | git pack-objects --revs {opt} --stdout 2>/dev/null | wc -c', shell=True, cwd=bs, env=lenv(), capture_output=True, text=True).stdout.strip())
print(f'  模拟服务端要发的 pack(只含 v2 这一个提交的新对象):--thin(可以引用客户端已有的 v1 blob 做 delta){nb("--thin"):,} 字节;不用 thin(对象必须自包含){nb(""):,} 字节;整个文件压缩后约 {len(zlib.compress(BIG.encode())):,} 字节')
