"""Git 实验辅助:在 ltmp/<name>/ 下新建真实的 git 仓库,用系统的 git(2.54.0, Apple Git-157)跑真实命令。
隔离:HOME 和全局配置指向 ltmp/_home(不读用户自己的 ~/.gitconfig),GIT_CONFIG_NOSYSTEM=1;
作者/提交者与时间固定(默认 2026-01-01T10:00:00Z,t=N 表示再加 N 分钟),所以 commit hash 可复现。
网络类实验只用本机 file:// 或 git daemon(端口 9800+),绝不碰任何远程仓库。ltmp/ 整体可删。"""
import os, sys, subprocess, shutil, pathlib, textwrap, time, json, re, socket, signal, threading, statistics, hashlib, zlib, struct, datetime
HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy'): os.environ.pop(k, None)
os.environ['NO_PROXY'] = '127.0.0.1,localhost'
from rl import tee, save
from fl import free_port, ms, median, pr
LT = HERE / 'ltmp'; LT.mkdir(exist_ok=True)
HOME = LT / '_home'; HOME.mkdir(exist_ok=True)
GIT = '/usr/bin/git'
BASE_T = datetime.datetime(2026, 1, 1, 10, 0, 0, tzinfo=datetime.timezone.utc)
(HOME / '.gitconfig').write_text('[init]\n\tdefaultBranch = main\n[maintenance]\n\tauto = false\n[gc]\n\tauto = 0\n[pack]\n\tthreads = 1\n')


def stamp(t=0):
    if t == 'now': return ''
    return (BASE_T + datetime.timedelta(minutes=t)).strftime('%Y-%m-%dT%H:%M:%S+0000')


def lenv(t=0, who='Alice', **extra):
    e = {'PATH': '/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin', 'HOME': str(HOME), 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': str(HOME / '.gitconfig'),
         'LC_ALL': 'C', 'LANG': 'C', 'GIT_PAGER': 'cat', 'PAGER': 'cat', 'GIT_TERMINAL_PROMPT': '0', 'TERM': 'dumb', 'NO_COLOR': '1',
         'GIT_AUTHOR_NAME': who, 'GIT_AUTHOR_EMAIL': f'{who.lower()}@example.com', 'GIT_COMMITTER_NAME': who, 'GIT_COMMITTER_EMAIL': f'{who.lower()}@example.com',
         'GIT_AUTHOR_DATE': stamp(t), 'GIT_COMMITTER_DATE': stamp(t), 'TMPDIR': str(LT), 'GIT_EDITOR': ':', 'GIT_MERGE_AUTOEDIT': 'no'}
    if t == 'now':  # 用真实时间(reflog 过期、对象宽限期等依赖当前时间的实验)
        e.pop('GIT_AUTHOR_DATE'); e.pop('GIT_COMMITTER_DATE')
    e.update({k: str(v) for k, v in extra.items()}); return e


def tidy(t):
    t = re.sub(r'\x1b\[[0-9;]*m', '', t).replace(str(LT), '/work').replace(str(HERE.parent), '<scratch>').replace(str(HERE), '<实验目录>')
    t = re.sub(r'/private/tmp/claude-501/[^\s"\':]*?/scratchpad', '<scratch>', t)
    t = t.replace('/private/work', '/work')
    return '\n'.join(l.rstrip() for l in t.rstrip().split('\n')).lstrip('\n')


def ldir(name, clean=True):
    d = LT / name
    if clean: shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True, exist_ok=True); return d


def lab(name, *init_args, clean=True):
    """新建目录并 git init(静默)。init_args 如 '--object-format=sha256'。"""
    d = ldir(name, clean)
    r = subprocess.run([GIT, 'init', '-q', *init_args], cwd=d, env=lenv(), capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return d


def W(d, files, mode=None):
    """写文件 {相对路径: 内容};内容 str 原样写入(不 dedent),bytes 原样写入。"""
    for p, c in files.items():
        f = pathlib.Path(d) / p; f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(c if isinstance(c, bytes) else c.encode())
        if mode: f.chmod(mode)


def run(d, cmd, t=0, who='Alice', timeout=120, env=None, stdin=None):
    """静默运行 shell 命令,返回 (rc, 整理过的 stdout+stderr)。"""
    e = lenv(t, who, **(env or {}))
    try:
        r = subprocess.run(['/bin/bash', '-c', cmd], cwd=d, env=e, capture_output=True, text=True, errors='replace', timeout=timeout, input=stdin)
        return r.returncode, tidy(r.stdout + r.stderr)
    except subprocess.TimeoutExpired as ex:
        o = ex.stdout.decode() if isinstance(ex.stdout, bytes) else (ex.stdout or '')
        return -9, tidy(o) + '\n(超时)'


def sh(d, cmd, t=0, who='Alice', n=40, w=170, show=True, env=None, ind='  ', stdin=None, timeout=120, prompt='$ '):
    """运行并打印 '$ cmd' 与输出;返回输出字符串。退出码非 0 时追加一行 (退出码 N)。"""
    rc, o = run(d, cmd, t, who, timeout, env, stdin)
    if show:
        print(f'{ind}{prompt}{tidy(cmd)}'.rstrip())
        if o: pr(o, n, ind, w)
        if rc != 0: print(f'{ind}(退出码 {rc})')
    return o


def out1(d, cmd, t=0, env=None):
    """静默运行,返回去掉末尾换行的输出。"""
    return run(d, cmd, t, env=env)[1]


def ci(d, msg, files=None, t=0, who='Alice', add='-A', extra=''):
    """写文件(可选)→ git add → git commit,静默;返回新 commit 的完整 hash。"""
    if files: W(d, files)
    rc, o = run(d, f'git add {add} && git commit -q {extra} -m {shq(msg)}', t, who)
    assert rc == 0, o
    return out1(d, 'git rev-parse HEAD')


def shq(s): return "'" + s.replace("'", "'\\''") + "'"


def hexdump(b, n=96, ind='  '):
    """16 字节一行的十六进制 + ASCII。"""
    for i in range(0, min(len(b), n), 16):
        ch = b[i:i + 16]
        print(f"{ind}{i:04x}  {' '.join(f'{c:02x}' for c in ch):<47}  {''.join(chr(c) if 32 <= c < 127 else '.' for c in ch)}")
    if len(b) > n: print(f'{ind}…(共 {len(b)} 字节)')


def loose(d, sha, algo='sha1'):
    """读松散对象并解压,返回原始字节(含 '类型 长度\\0' 头)。"""
    p = pathlib.Path(d) / '.git' / 'objects' / sha[:2] / sha[2:]
    return zlib.decompress(p.read_bytes())


def sec_(title):
    print(f'== {title}')


# ---------- packfile 解析(只读,纯 Python) ----------
PTYPES = {1: 'commit', 2: 'tree', 3: 'blob', 4: 'tag', 6: 'ofs-delta', 7: 'ref-delta'}


def parse_pack(data, hashlen=20):
    """解析 packfile 字节,返回 (版本, 对象数, [dict(off,type,size,base,raw,clen)])。"""
    assert data[:4] == b'PACK'
    ver, n = struct.unpack('>II', data[4:12]); pos = 12; ents = []
    for _ in range(n):
        start = pos; b = data[pos]; pos += 1; typ = (b >> 4) & 7; size = b & 15; shift = 4
        while b & 0x80:
            b = data[pos]; pos += 1; size |= (b & 0x7f) << shift; shift += 7
        base = None
        if typ == 6:
            b = data[pos]; pos += 1; off = b & 0x7f
            while b & 0x80:
                b = data[pos]; pos += 1; off = ((off + 1) << 7) | (b & 0x7f)
            base = start - off
        elif typ == 7:
            base = data[pos:pos + hashlen].hex(); pos += hashlen
        z = zlib.decompressobj(); raw = z.decompress(data[pos:]); used = len(data) - pos - len(z.unused_data); pos += used
        ents.append(dict(off=start, type=typ, size=size, base=base, raw=raw, clen=used, hdr=pos - used - start))
    return ver, n, ents


def _vi(delta, pos):
    v = 0; s = 0
    while True:
        b = delta[pos]; pos += 1; v |= (b & 0x7f) << s; s += 7
        if not b & 0x80: return v, pos


def apply_delta(base, delta, trace=None):
    """应用 git delta:先是源长度、目标长度两个变长整数,然后是 copy(最高位为 1)与 insert 指令。"""
    src, pos = _vi(delta, 0); dst, pos = _vi(delta, pos)
    assert src == len(base), (src, len(base))
    out = bytearray()
    while pos < len(delta):
        op = delta[pos]; pos += 1
        if op & 0x80:
            off = 0; sz = 0
            for i in range(4):
                if op & (1 << i): off |= delta[pos] << (8 * i); pos += 1
            for i in range(3):
                if op & (0x10 << i): sz |= delta[pos] << (8 * i); pos += 1
            if sz == 0: sz = 0x10000
            out += base[off:off + sz]
            if trace is not None: trace.append(('copy', off, sz))
        elif op:
            out += delta[pos:pos + op]; pos += op
            if trace is not None: trace.append(('insert', op, bytes(delta[pos - op:pos])))
        else: raise ValueError('delta 指令 0')
    assert len(out) == dst, (len(out), dst)
    return bytes(out), src, dst


def obj_sha(typ, data, algo=hashlib.sha1):
    return algo(typ.encode() + b' ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def fast_import(d, n, merges_every=0, fname='f.txt', branch='main', start_t=0):
    """用 git fast-import 一口气造 n 个提交(线性;merges_every>0 时每隔这么多个提交从上一个提交拉一条 1 个提交的侧枝再合并)。返回最后一个提交的 hash。"""
    out = []; mark = 0; last = None; t0 = int(BASE_T.timestamp()) + start_t * 60
    def commit(ref, msg, parents, body):
        nonlocal mark
        mark += 1; t = t0 + mark
        out.append(f'commit {ref}\nmark :{mark}\nauthor Alice <alice@example.com> {t} +0000\ncommitter Alice <alice@example.com> {t} +0000\ndata {len(msg.encode())}\n{msg}\n')
        if parents:
            out.append(f'from :{parents[0]}\n')
            for p in parents[1:]: out.append(f'merge :{p}\n')
        out.append(f'M 100644 inline {body[0]}\ndata {len(body[1].encode())}\n{body[1]}\n\n')
        return mark
    for i in range(1, n + 1):
        if merges_every and i % merges_every == 0 and last:
            s = commit(f'refs/heads/side{i}', f'侧枝 {i}', [last], (f'side{i}.txt', f'side {i}\n'))
            last = commit(f'refs/heads/{branch}', f'合并 {i}', [last, s], (fname(i) if callable(fname) else fname, f'版本 {i}\n'))
        else:
            last = commit(f'refs/heads/{branch}', f'提交 {i}', [last] if last else [], (fname(i) if callable(fname) else fname, f'版本 {i}\n'))
    r = subprocess.run([GIT, 'fast-import', '--quiet'], cwd=d, env=lenv(), input=''.join(out).encode(), capture_output=True)
    assert r.returncode == 0, r.stderr.decode()
    return out1(d, f'git rev-parse {branch}')


def ewah(data, pos):
    """解码一个 EWAH 压缩位图,返回 (整数位图, 位数, 新位置)。第 n 位 = 第 n//64 个字的第 n%64 位。"""
    bit_size, nwords = struct.unpack('>II', data[pos:pos + 8]); pos += 8
    words = struct.unpack('>%dQ' % nwords, data[pos:pos + 8 * nwords]); pos += 8 * nwords
    pos += 4  # 最后一个 RLW 的位置
    val = 0; cur = 0; i = 0
    while i < nwords:
        rlw = words[i]; i += 1
        run = rlw & 1; rl = (rlw >> 1) & 0xFFFFFFFF; lit = rlw >> 33
        if run: val |= ((1 << (64 * rl)) - 1) << cur
        cur += 64 * rl
        for _ in range(lit):
            val |= words[i] << cur; cur += 64; i += 1
    return val & ((1 << bit_size) - 1), bit_size, pos


def parse_index(path):
    """解析 .git/index(v2/v3;v4 不处理)。返回 (版本, 条目列表 [dict(ctime, mtime, dev, ino, mode, uid, gid, size, sha, flags, path)], 扩展名列表)。"""
    b = pathlib.Path(path).read_bytes()
    sig, ver, n = struct.unpack('>4sII', b[:12]); assert sig == b'DIRC' and ver in (2, 3), (sig, ver)
    pos = 12; ents = []
    for _ in range(n):
        f = struct.unpack('>10I', b[pos:pos + 40]); sha = b[pos + 40:pos + 60].hex(); fl = struct.unpack('>H', b[pos + 60:pos + 62])[0]; q = pos + 62
        xfl = 0
        if ver == 3 and fl & 0x4000: xfl = struct.unpack('>H', b[q:q + 2])[0]; q += 2
        end = b.index(b'\0', q); name = b[q:end].decode()
        ents.append(dict(ctime=(f[0], f[1]), mtime=(f[2], f[3]), dev=f[4], ino=f[5], mode=f[6], uid=f[7], gid=f[8], size=f[9], sha=sha, flags=fl, xflags=xfl, path=name))
        pos += (62 + (q - pos - 62) + len(name.encode()) + 8) & ~7
    exts = []
    # 扩展:4 字节名字 + 4 字节长度 + 数据,最后 20 字节是整个文件的 SHA-1
    while pos < len(b) - 20:
        nm = b[pos:pos + 4]; ln = struct.unpack('>I', b[pos + 4:pos + 8])[0]; exts.append((nm.decode('latin1'), ln)); pos += 8 + ln
    return ver, ents, exts
