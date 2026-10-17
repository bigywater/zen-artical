"""Gin 实验辅助:在 gtmp/<name>/ 下写真实的 Go 源码(Gin v1.12.0,go.mod/go.sum 取自 gtmp/gin_base),
用 go build / go test 编译运行(Go 1.27.1)。GOPROXY=off,依赖都在 gtmp/_gopath 的模块缓存里;
gsrcl() 把 Gin 自己的源码按行号打印出来(模块缓存里的原文,不是复述)。端口一律 9700+。"""
from gl import *
GINV = 'v1.12.0'
GINSRC = GT / '_gopath' / 'pkg' / 'mod' / 'github.com' / 'gin-gonic' / f'gin@{GINV}'
BASE = GT / 'gin_base'


def gin_dir(name, files, clean=True, patched=False):
    d = gdir(name, clean)
    if isinstance(files, str): files = {'main.go': files}
    write(d, files)
    if not (d / 'go.mod').exists():
        shutil.copy(BASE / 'go.mod', d / 'go.mod'); shutil.copy(BASE / 'go.sum', d / 'go.sum')
        if patched:  # 用带 DumpTree 的副本(见 nl_patch.py)
            with open(d / 'go.mod', 'a') as f: f.write('\nreplace github.com/gin-gonic/gin => ../gin_patched\n')
    return d


def gin(name, files, args=(), env=None, timeout=120, race=False, flags=(), stdin=None, clean=True, pkg='.', patched=False):
    """写源码 → go build → 运行。返回 dict(crc, cout, rc, out, d, bin)。运行时默认 GIN_MODE=release(要看 debug 输出时传 env=dict(GIN_MODE='debug'))。"""
    d = gin_dir(name, files, clean, patched)
    cmd = ['build', '-o', str(d / 'app')] + (['-race'] if race else []) + list(flags) + [pkg]
    crc, cout = go(d, *cmd, timeout=timeout)
    res = dict(crc=crc, cout=cout, rc=None, out='', d=d, bin=str(d / 'app'))
    if crc != 0: return res
    e = genv(GIN_MODE='release'); e.update({k: str(v) for k, v in (env or {}).items()})
    try:
        r = subprocess.run([str(d / 'app'), *args], cwd=d, env=e, capture_output=True, text=True, timeout=timeout, input=stdin)
        res.update(rc=r.returncode, out=tidy(r.stdout + r.stderr))
    except subprocess.TimeoutExpired as ex:
        o = ex.stdout.decode() if isinstance(ex.stdout, bytes) else (ex.stdout or '')
        res.update(rc=-9, out=tidy(o) + '\n(超时)')
    return res


def gtestn(name, files, args=('-v',), env=None, timeout=180, clean=True, pkg='./...', patched=False):
    d = gin_dir(name, files, clean, patched)
    e = dict(GIN_MODE='release'); e.update(env or {})
    rc, o = go(d, 'test', *args, pkg, env=e, timeout=timeout)
    return dict(rc=rc, out=o, d=d)


def out_lines(r, ind='  ', n=60, w=170):
    """打印一次 gin() 的结果(编译失败时打印编译器输出)。"""
    if r['crc'] != 0: print(ind + '编译失败:'); pr(r['cout'], n, ind + '  ', w); return
    pr(r['out'], n, ind, w)


def gsrcl(rel, a, b, ind='  ', title=None, w=150):
    """打印 Gin 源码 rel(如 'tree.go')第 a..b 行,带行号。"""
    L = (GINSRC / rel).read_text().split('\n')
    print(f'{ind}{title or rel}(Gin {GINV}):')
    for i in range(a - 1, min(b, len(L))): print(f'{ind}  {i + 1:>4} | {L[i].rstrip()[:w]}'.replace('\t', '    '))


def gfind(rel, pat, ind='  ', ctx=0, maxn=8, w=150):
    """在 Gin 源码 rel 里找含 pat 的行并带行号打印。"""
    L = (GINSRC / rel).read_text().split('\n'); n = 0
    for i, l in enumerate(L):
        if re.search(pat, l):
            for j in range(max(0, i - ctx), min(len(L), i + ctx + 1)): print(f'{ind}{rel}:{j + 1:>4} | {L[j].rstrip()[:w]}'.replace('\t', '    '))
            n += 1
            if n >= maxn: break


def gfunc(rel, name, ind='  ', w=150, maxn=60, title=None):
    """打印 Gin 源码 rel 里名为 name 的函数全文(从含 'func ... name(' 的行到行首的 '}'),带行号。"""
    L = (GINSRC / rel).read_text().split('\n')
    a = next(i for i, l in enumerate(L) if re.match(rf'func (\([^)]*\) )?{re.escape(name)}\(', l))
    b = next(i for i in range(a, len(L)) if L[i] == '}')
    print(f'{ind}{title or rel + " 的 " + name}(Gin {GINV}):')
    for i in range(a, min(b + 1, a + maxn)): print(f'{ind}  {i + 1:>4} | {L[i].rstrip()[:w]}'.replace('\t', '    '))


def setup():
    """(重新)准备环境:创建 gtmp/gin_base(go.mod/go.sum,下载 Gin 与依赖,经代理)和 gtmp/gin_patched(只读 dump 函数的 Gin 副本)。已存在则跳过。"""
    if not (BASE / 'go.mod').exists():
        d = gdir('gin_base'); write(d, {'main.go': 'package main\nimport _ "github.com/gin-gonic/gin"\nfunc main(){}\n'}); mod(d, 'lab', '1.27')
        px = dict(GOPROXY='https://proxy.golang.org', HTTPS_PROXY='http://127.0.0.1:1087')
        print(goget(d, f'github.com/gin-gonic/gin@{GINV}')[1][-200:])
        print(go(d, 'mod', 'tidy', env=px)[1][-200:])
    if not (GT / 'gin_patched' / 'zz_dump.go').exists():
        import nl_patch; nl_patch.make()
