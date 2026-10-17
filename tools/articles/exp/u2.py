import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u2'); R = {}
def sh2(c, **k): 
    r = subprocess.run(c, shell=True, capture_output=True, text=True, env=ENVB, **k); return clean((r.stdout + r.stderr).strip()), r.returncode
print('== 一:本机的三个角色:rustc、cargo、rustup')
for c in ('command -v rustc; command -v cargo; command -v rustup || echo "rustup: 本机没有"', 'rustc --version', 'cargo --version'):
    o, rc = sh2(c); print(f'  $ {c}'); print('\n'.join('    ' + l for l in o.splitlines()) or '    (无输出)', f'[退出码 {rc}]' if rc else '')
print('  $ rustc --version --verbose'); o, _ = sh2('rustc --version --verbose'); print('\n'.join('    ' + l for l in o.splitlines()))
host = re.search(r'host: (\S+)', o).group(1); R['host'] = host; R['ver'] = o.splitlines()[0]
print()
print('== 二:rustc 的 sysroot 里有什么(编译器自带的标准库在哪)')
sr = sh2('rustc --print sysroot')[0]; print('  $ rustc --print sysroot →', sr)
print('  sysroot 顶层:', sorted(os.listdir(sr))); rl_ = pathlib.Path(sr) / 'lib' / 'rustlib'
print('  lib/rustlib 下:', sorted(x.name for x in rl_.iterdir()))
tg = [x.name for x in rl_.iterdir() if x.is_dir() and x.name != 'src']; print('  已安装标准库的目标平台:', tg, '(只有宿主平台)')
std = sorted(f for f in (rl_ / host / 'lib').iterdir() if f.name.startswith('libstd-')); print('  标准库文件:', {f.suffix: f'{f.stat().st_size:,} 字节' for f in std}); R['std'] = {f.suffix: f.stat().st_size for f in std}
R['targets'] = tg; R['sysroot_dirs'] = sorted(os.listdir(sr))
o, _ = sh2('rustc --print target-list'); n_all = len(o.splitlines()); print(f'  $ rustc --print target-list → rustc 认识 {n_all} 个目标三元组(但只有 {len(tg)} 个装了标准库)'); R['n_targets'] = n_all
print()
print('== 三:cargo 其实是在调用 rustc:cargo build -v 展示真实的 rustc 命令行')
P = RS / 'proj'; P.mkdir(exist_ok=True); shutil.rmtree(P / 'verbose', ignore_errors=True); cargo(['new', 'verbose', '--vcs', 'none'], P); shutil.rmtree(TG, ignore_errors=True)
rc, o = cargo(['build', '-v'], P / 'verbose'); print('  $ cargo build -v'); 
for l in o.splitlines():
    if 'Running' in l:
        import shlex
        a = shlex.split(l.split('Running', 1)[1].strip().strip('`')); b = []; k = 0
        while k < len(a):
            if a[k] == '--check-cfg': k += 2; continue
            b.append(a[k]); k += 1
        print('    Running rustc 的参数(省略了 --check-cfg):'); print('      ' + '\n      '.join(textwrap.wrap(' '.join(b), 96, break_on_hyphens=False, break_long_words=False))); R_verbose = ' '.join(b)
    else: print('    ' + l)
R['verbose'] = R_verbose
print()
print('== 四:同一份源码,直接用 rustc 编译,与 cargo 的结果对比;以及换掉 cargo 调用的 rustc')
d = P / 'verbose'; t0 = time.perf_counter(); o, rc = sh2(f'rustc --edition=2024 --crate-name verbose {d}/src/main.rs -o {RS}/bin/verbose_direct'); t = time.perf_counter() - t0
print(f'  $ rustc --edition=2024 src/main.rs -o verbose_direct  ({t:.2f} s,退出码 {rc})'); print('  运行:', run(RS / 'bin' / 'verbose_direct')[1].strip(), '| 文件大小', (RS / 'bin' / 'verbose_direct').stat().st_size, '字节;cargo debug 产物', (TG / 'debug' / 'verbose').stat().st_size, '字节')
env2 = dict(ENVB, RUSTC='/nonexistent/rustc'); shutil.rmtree(TG, ignore_errors=True); rc, o2, e2 = sh(['cargo', 'build'], cwd=d, env=env2); print('  $ RUSTC=/nonexistent/rustc cargo build →'); print('\n'.join('    ' + l for l in tidy(e2 + o2).splitlines()[:4]))
R['rustc_missing'] = tidy(e2 + o2).splitlines()[:3]
print('  $ rustc +nightly src/main.rs("+toolchain" 是 rustup 的代理才认识的写法):'); o, rc = sh2(f'rustc +nightly {d}/src/main.rs -o {RS}/bin/x'); print('\n'.join('    ' + l for l in o.splitlines()[:3]), f'[退出码 {rc}]')
R['plus'] = o.splitlines()[:2]
save('u2', R)
