import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u1'); R = {}
P = RS / 'proj'; P.mkdir(exist_ok=True); shutil.rmtree(P / 'hello', ignore_errors=True); shutil.rmtree(TG, ignore_errors=True)
def tree(d, depth=0):
    out = []
    for f in sorted(pathlib.Path(d).iterdir()):
        if f.name in ('.git', 'target') and depth == 0 and f.name == 'target': out.append('  ' * depth + f.name + '/'); continue
        if f.name == '.git': out.append('  ' * depth + '.git/ (git 仓库)'); continue
        out.append('  ' * depth + f.name + ('/' if f.is_dir() else f'  ({f.stat().st_size} B)'))
        if f.is_dir(): out += tree(f, depth + 1)
    return out
print('== 一:cargo new hello 生成了什么')
rc, o = cargo(['new', 'hello'], P); print('  $ cargo new hello'); print('\n'.join('  ' + l for l in o.splitlines()))
print('  目录树:'); print('\n'.join('    ' + l for l in tree(P / 'hello')))
print('  Cargo.toml:'); print('\n'.join('    ' + l for l in (P / 'hello' / 'Cargo.toml').read_text().splitlines()))
print('  src/main.rs:'); print('\n'.join('    ' + l for l in (P / 'hello' / 'src' / 'main.rs').read_text().splitlines()))
print('  .gitignore:', (P / 'hello' / '.gitignore').read_text().strip())
print()
print('== 二:第一次编译与运行(debug 模式),以及什么都不改时再编译一次')
H = P / 'hello'; env = ENVB
t0 = time.perf_counter(); rc, o = cargo(['build'], H); t1 = time.perf_counter() - t0
print(f'  $ cargo build   (第 1 次,{t1:.2f} s)'); print('\n'.join('  ' + l for l in o.splitlines()))
t0 = time.perf_counter(); rc, o = cargo(['build'], H); t2 = time.perf_counter() - t0
print(f'  $ cargo build   (什么都没改,{t2:.2f} s)'); print('\n'.join('  ' + l for l in o.splitlines()))
rc, o = cargo(['run'], H); print('  $ cargo run'); print('\n'.join('  ' + l for l in o.splitlines()))
R['t_first'] = t1; R['t_noop'] = t2
print('  Cargo.lock(此刻出现):'); print('\n'.join('    ' + l for l in (H / 'Cargo.lock').read_text().splitlines()))
print()
print('== 三:target/ 里是什么;改一行源码后的重新编译')
print('  target/ 的结构(两层):')
for f in sorted((TG / 'debug').iterdir()): print('    debug/' + f.name + ('/' if f.is_dir() else f'  ({f.stat().st_size} B)'))
bin_ = TG / 'debug' / 'hello'; print(f'  可执行文件 target/debug/hello:{bin_.stat().st_size} 字节({human(bin_.stat().st_size)})'); R['debug_size'] = bin_.stat().st_size
(H / 'src' / 'main.rs').write_text('fn main() {\n    println!("Hello, rust! v2");\n}\n')
t0 = time.perf_counter(); rc, o = cargo(['build'], H); t3 = time.perf_counter() - t0
print(f'  改一行字符串后 $ cargo build({t3:.2f} s):'); print('\n'.join('  ' + l for l in o.splitlines())); R['t_edit'] = t3
print()
print('== 四:debug 与 release:编译耗时与二进制大小;cargo check 只检查不生成代码')
t0 = time.perf_counter(); rc, o = cargo(['build', '--release'], H); t4 = time.perf_counter() - t0
print(f'  $ cargo build --release({t4:.2f} s)'); print('\n'.join('  ' + l for l in o.splitlines()))
rb = TG / 'release' / 'hello'; print(f'  release 可执行文件:{rb.stat().st_size} 字节;debug:{bin_.stat().st_size} 字节'); R['release_size'] = rb.stat().st_size; R['t_release'] = t4
(H / 'src' / 'main.rs').write_text('fn main() {\n    println!("Hello, rust! v3");\n}\n')
t0 = time.perf_counter(); rc, o = cargo(['check'], H); t5 = time.perf_counter() - t0
print(f'  改源码后 $ cargo check({t5:.2f} s):'); print('\n'.join('  ' + l for l in o.splitlines()))
t0 = time.perf_counter(); rc, o = cargo(['build'], H); t6 = time.perf_counter() - t0
print(f'  改源码后 $ cargo build({t6:.2f} s)'); R['t_check'] = t5; R['t_build_after'] = t6
print('  $ target/release/hello 直接运行(不经过 cargo):', run(rb)[1].strip())
save('u1', R)
