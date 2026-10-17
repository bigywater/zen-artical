"""Rust 实验助手:单文件用 rustc 编译(捕获真实的编译器输出),需要依赖时用 cargo。
所有产物在 rsdata/(可整体删除);cargo 的 home 与 target 也放在 rsdata/ 里,避免占用用户的 ~/.cargo。"""
import os, sys, subprocess, time, re, pathlib, shutil, json, textwrap
HERE = pathlib.Path(__file__).parent
RS = HERE / 'rsdata'; RS.mkdir(exist_ok=True)
CH = RS / 'cargo_home'; TG = RS / 'target'
ENVB = dict(os.environ, CARGO_HOME=str(CH), CARGO_TARGET_DIR=str(TG), CARGO_TERM_COLOR='never', RUSTC_BOOTSTRAP='0')
ENVB.pop('CARGO_BUILD_JOBS', None)
ENVB.setdefault('HTTPS_PROXY', 'http://127.0.0.1:1087')  # crates.io 需要走代理(cargo fetch 实测可用)
def tee(name):
    sys.path.insert(0, str(HERE)); import rl; rl.tee(name)
def save(name, obj): (HERE / 'out' / f'{name}.json').write_text(json.dumps(obj, ensure_ascii=False, indent=1))
def clean(s): return s.replace(str(RS), '<实验目录>').replace(str(HERE), '<实验目录>')
def sh(cmd, cwd=None, env=None, timeout=300, check=False):
    r = subprocess.run(cmd, cwd=cwd, env=env or ENVB, capture_output=True, text=True, timeout=timeout)
    return r.returncode, clean(r.stdout), clean(r.stderr)
def src_file(name, code, d=None):
    d = pathlib.Path(d or RS / 'src'); d.mkdir(parents=True, exist_ok=True); f = d / f'{name}.rs'; f.write_text(textwrap.dedent(code).lstrip('\n')); return f
def rustc(name, code, release=False, flags=(), edition='2024', crate_type=None, boot=False, timeout=300):
    """编译单个文件,返回 (是否成功, 编译器输出(stderr), 可执行文件路径)。"""
    f = src_file(name, code); out = RS / 'bin' / name; out.parent.mkdir(exist_ok=True)
    cmd = ['rustc', f'--edition={edition}', '--color=never', str(f), '-o', str(out)] + (['-O'] if release else []) + list(flags)
    if crate_type: cmd += ['--crate-type', crate_type]
    env = dict(ENVB, RUSTC_BOOTSTRAP='1') if boot else ENVB
    t0 = time.perf_counter(); rc, o, e = sh(cmd, env=env, timeout=timeout); return rc == 0, tidy(o + e), out, time.perf_counter() - t0
def run(binpath, *args, timeout=60, stdin=None, env=None):
    t0 = time.perf_counter(); r = subprocess.run([str(binpath), *args], capture_output=True, text=True, timeout=timeout, input=stdin, env=env); return r.returncode, clean(r.stdout), clean(r.stderr), time.perf_counter() - t0
def tidy(t): return '\n'.join(l.rstrip() for l in t.rstrip().split('\n')).lstrip('\n')
def show(code): return textwrap.dedent(code).strip('\n')
def cargo(args, cwd, timeout=600, env=None): 
    rc, o, e = sh(['cargo', *args], cwd=cwd, env=env, timeout=timeout); return rc, tidy(e + o)
def proj(name, files, toml_extra='', edition='2024', deps=''):
    d = RS / 'proj' / name; shutil.rmtree(d, ignore_errors=True); (d / 'src').mkdir(parents=True)
    (d / 'Cargo.toml').write_text(f'[package]\nname = "{name}"\nversion = "0.1.0"\nedition = "{edition}"\n\n[dependencies]\n{deps}\n{toml_extra}\n')
    for p, c in files.items():
        f = d / p; f.parent.mkdir(parents=True, exist_ok=True); f.write_text(textwrap.dedent(c).lstrip('\n'))
    return d
def du(p): 
    p = pathlib.Path(p); return sum(f.stat().st_size for f in p.rglob('*') if f.is_file()) if p.is_dir() else p.stat().st_size
def human(n): return f'{n / 1024:.0f} KiB' if n < 1 << 20 else f'{n / (1 << 20):.1f} MiB'

def numbered(code): return '\n'.join(f'{i + 1:>3} | {l}' for i, l in enumerate(show(code).split('\n')))
def tryit(name, code, release=False, flags=(), edition='2024', boot=False, args=(), maxlines=40, quiet_src=False, show_run=True):
    """打印源码(带行号)、编译结果(成功则运行并打印输出);返回 dict(ok, diag, out, secs, bin)。"""
    ok, diag, binp, secs = rustc(name, code, release=release, flags=flags, edition=edition, boot=boot)
    if not quiet_src: print('  源码:'); print('\n'.join('    ' + l for l in numbered(code).split('\n')))
    r = dict(ok=ok, diag=diag, bin=binp, secs=secs, out='')
    if ok:
        print('  编译:成功' + (f';警告:' if diag else '')); 
        if diag: print('\n'.join('    ' + l for l in diag.split('\n')[:maxlines]))
        if show_run:
            rc, o, e, t = run(binp, *args); r.update(out=o, err=e, rc=rc, run_s=t)
            print(f'  运行(退出码 {rc}):'); print('\n'.join('    ' + l for l in (o + e).rstrip().split('\n')[:maxlines]) if (o + e).strip() else '    (无输出)')
    else:
        print('  编译:失败'); L = diag.split('\n'); print('\n'.join('    ' + l for l in L[:maxlines])); 
        if len(L) > maxlines: print(f'    …(共 {len(L)} 行)')
    return r
def asm_of(name, code, fn=None, flags=('-O',), edition='2024'):
    """生成汇编并取出函数体(去掉注释与指令前缀的空白)。"""
    f = src_file(name, code); out = RS / 'asm' / f'{name}.s'; out.parent.mkdir(exist_ok=True)
    rc, o, e = sh(['rustc', f'--edition={edition}', '--color=never', '--crate-type=lib', '--emit=asm', '-C', 'debuginfo=0', *flags, str(f), '-o', str(out)])
    t = out.read_text() if out.exists() else ''
    if fn:
        m = re.search(rf'^_?[^\n]*{fn}[^\n]*:\n(.*?)(?=^\s*\.cfi_endproc)', t, re.S | re.M)
        body = m.group(1) if m else ''
        return [l.strip() for l in body.split('\n') if l.strip() and not l.strip().startswith(('.', ';', '//'))], t
    return t.split('\n'), t

# ---- 隔离的 nightly 工具链(rustup 装在 rsdata/rustup_home,不碰 brew 的 rustc 和用户的 ~/.cargo)----
NH = RS / 'rustup_home'; NC = RS / 'rustup_cargo'
ENVN = dict(ENVB, RUSTUP_HOME=str(NH), CARGO_HOME=str(NC), PATH=str(NC / 'bin') + os.pathsep + os.environ['PATH'], CARGO_TARGET_DIR=str(RS / 'target_n'))
def ncargo(args, cwd, timeout=900, env=None, extra=None):
    e = dict(env or ENVN); e.update(extra or {})
    rc, o, e_ = sh(['cargo', *args], cwd=cwd, env=e, timeout=timeout); return rc, tidy(e_ + o)
