"""Go 实验辅助:在 gtmp/<name>/ 下写真实的 .go 源码,用 go build / go run / go test 编译运行(Go 1.27.1,brew)。
GOTOOLCHAIN=local(绝不自动下载别的工具链);GOPATH / GOCACHE 都在 gtmp/ 里,整体可删。
需要第三方模块时用 goget() 经代理(127.0.0.1:1087)从 proxy.golang.org 下载。绝不碰 6379、8181/9101/9333 与用户自己的数据库;自己起的服务用 9600+ 端口。"""
import os, sys, subprocess, shutil, pathlib, textwrap, time, json, re, socket, signal, threading, statistics, hashlib
HERE = pathlib.Path(__file__).parent
GT = HERE / 'gtmp'; GT.mkdir(exist_ok=True)
sys.path.insert(0, str(HERE))
for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy'): os.environ.pop(k, None)
os.environ['NO_PROXY'] = '127.0.0.1,localhost'
import rl
from rl import tee, save
from fl import free_port, numbered, show, ms, median, pr
GOROOT = '/opt/homebrew/Cellar/go/1.27.1/libexec'
GO = '/opt/homebrew/bin/go'


def tidy(t):
    t = re.sub(r'\x1b\[[0-9;]*m', '', t).replace(str(GT), '<gtmp>').replace(str(HERE.parent), '<scratch>').replace(str(HERE), '<实验目录>').replace(GOROOT, '<GOROOT>')
    t = re.sub(r'/private/tmp/claude-501/[^\s"\':]*?/scratchpad', '<scratch>', t)
    return '\n'.join(l.rstrip() for l in t.rstrip().split('\n')).lstrip('\n')


def genv(**extra):
    e = dict(os.environ)
    e.update(GOTOOLCHAIN='local', GOFLAGS='', GOPATH=str(GT / '_gopath'), GOCACHE=str(GT / '_gocache'), GOPROXY='off', GOSUMDB='off', GOTELEMETRY='off', GO111MODULE='on')
    e['PATH'] = '/opt/homebrew/bin:' + e['PATH']
    e.update({k: str(v) for k, v in extra.items()}); return e


def gdir(name, clean=True):
    d = GT / name
    if clean: shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True, exist_ok=True); return d


def write(d, files):
    for p, c in files.items():
        f = d / p; f.parent.mkdir(parents=True, exist_ok=True); f.write_text(textwrap.dedent(c).lstrip('\n'))


def mod(d, name='lab', go='1.27', extra=''):
    (d / 'go.mod').write_text(f'module {name}\n\ngo {go}\n{extra}')


def go(d, *args, env=None, timeout=180, stdin=None):
    """在目录 d 里运行 go <args>,返回 (rc, 整理过的 stdout+stderr)。"""
    try:
        r = subprocess.run([GO, *args], cwd=d, env=genv(**(env or {})), capture_output=True, text=True, timeout=timeout, input=stdin)
        return r.returncode, tidy(r.stdout + r.stderr)
    except subprocess.TimeoutExpired as ex:
        o = ex.stdout.decode() if isinstance(ex.stdout, bytes) else (ex.stdout or '')
        return -9, tidy(o) + '\n(超时)'


def goget(d, *mods, timeout=300):
    """经代理下载第三方模块(只有这一步联网)。"""
    return go(d, 'get', *mods, env=dict(GOPROXY='https://proxy.golang.org', GOSUMDB='off', HTTPS_PROXY='http://127.0.0.1:1087'), timeout=timeout)


def grun(name, files, args=(), env=None, flags=(), gcflags=None, ldflags=None, race=False, timeout=120, pkg='.', clean=True, tags=None, mainargs_env=None):
    """写源码 → go build → 运行二进制。返回 dict(crc, cout, rc, out, d, bin)。"""
    d = gdir(name, clean); write(d, files)
    if not (d / 'go.mod').exists(): mod(d)
    cmd = ['build', '-o', str(d / 'app')]
    if gcflags: cmd += ['-gcflags', gcflags]
    if ldflags: cmd += ['-ldflags', ldflags]
    if race: cmd += ['-race']
    if tags: cmd += ['-tags', tags]
    cmd += list(flags) + [pkg]
    crc, cout = go(d, *cmd, env=env, timeout=timeout)
    res = dict(crc=crc, cout=cout, rc=None, out='', d=d, bin=str(d / 'app'))
    if crc != 0: return res
    try:
        r = subprocess.run([str(d / 'app'), *args], cwd=d, env=genv(**(mainargs_env or env or {})), capture_output=True, text=True, timeout=timeout)
        res.update(rc=r.returncode, out=tidy(r.stdout + r.stderr))
    except subprocess.TimeoutExpired as ex:
        o = ex.stdout.decode() if isinstance(ex.stdout, bytes) else (ex.stdout or '')
        res.update(rc=-9, out=tidy(o) + '\n(超时)')
    return res


def gtest(name, files, args=('-v',), env=None, timeout=180, clean=True, pkg='./...'):
    d = gdir(name, clean); write(d, files)
    if not (d / 'go.mod').exists(): mod(d)
    rc, o = go(d, 'test', *args, pkg, env=env, timeout=timeout)
    return dict(rc=rc, out=o, d=d)


def gshow(r, n=40, w=170):
    if r['crc'] != 0: print('  编译失败:'); pr(r['cout'], n, '    ', w); return
    pr(r['out'], n, '    ', w)


def gsrc(files, title=None):
    for p, c in files.items():
        print(f'  {title or p}:'); print('\n'.join('    ' + l for l in numbered(c).split('\n')))


def clean_all():
    """整体删除 gtmp(含 GOPATH / GOCACHE)。"""
    shutil.rmtree(GT, ignore_errors=True)


def gdiag(cout, src, keep=None, drop=None):
    """把编译器诊断(./main.go:L:C: msg)配上源码行,返回多行文本。keep/drop 是子串元组。"""
    lines = textwrap.dedent(src).lstrip('\n').split('\n'); res = []
    for l in cout.split('\n'):
        m = re.match(r'(?:\./)?([\w./]+\.go):(\d+):(\d+): (.*)', l)
        if not m: continue
        f, ln, col, msg = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
        if keep and not any(k in msg for k in keep): continue
        if drop and any(k in msg for k in drop): continue
        code = lines[ln - 1].strip() if 0 < ln <= len(lines) else ''
        res.append(f'  {f}:{ln}:{col}: {msg}    ← {code[:90]}')
    return '\n'.join(res)


GBENCH = r'''
func bench(name string, f func(b *testing.B)) {
	var xs []float64
	for i := 0; i < 7; i++ {
		br := testing.Benchmark(f)
		xs = append(xs, float64(br.T.Nanoseconds())/float64(br.N))
	}
	sort.Float64s(xs)
	fmt.Printf("  %-36s 中位 %.2f ns/op(最小 %.2f / 最大 %.2f)\n", name, xs[3], xs[0], xs[6])
}
'''  # 需要 import "fmt" "sort" "testing";每个变体 7 轮取中位数


def asm_fn(cout, fn, pats, pkg='main'):
    """从 go build -gcflags=-S 输出里取函数 pkg.fn 的汇编行,只保留含 pats 之一的行(去掉地址与路径)。"""
    blocks = re.split(r'\n(?=%s\.\S+ STEXT)' % re.escape(pkg), cout)
    b = [x for x in blocks if x.startswith(f'{pkg}.{fn} STEXT')]
    if not b: return []
    if pats == 'HEADER': return [b[0].split('\n')[0][:200]]
    res = []
    for l in b[0].split('\n'):
        if l.strip().startswith('rel ') or 'morestack' in l: continue
        if any(p in l for p in pats):
            res.append(re.sub(r'^\s*0x[0-9a-f]+ \d+ \(', '(', l).replace(str(GT) + '/', '').strip()[:150])
    return res
