import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u130'); R = {}
print('== 一:一个空的 Rust 程序的入口:谁是真正的入口、main 是怎么被调用的(nm / otool 看符号与依赖)')
ok, d, binp, _ = rustc('u130a', 'fn main() {}', release=True)
rc, o, e = sh(['nm', str(binp)]); syms = o.splitlines()
lang = [l.split()[-1] for l in syms if 'lang_start' in l][:4]; entry = [l.split()[-1] for l in syms if l.endswith(' _main') or l.endswith('__mh_execute_header')][:2]
print(f'  nm 里与启动相关的符号:{lang}  入口:{entry}')
rc, o, e = sh(['otool', '-L', str(binp)]); libs = [l.strip().split(' (')[0] for l in o.splitlines()[1:]]
print(f'  动态依赖(otool -L):{libs}'); R['syms'] = lang; R['libs'] = libs
rc, o, e = sh(['otool', '-l', str(binp)]); m = re.search(r'LC_MAIN.*?entryoff (\d+)', o, re.S); print(f'  Mach-O 的 LC_MAIN 入口偏移:{m.group(1) if m else "?"}(指向 C 风格的 main,它再调 lang_start)'); R['entryoff'] = m.group(1) if m else None
print()
print('== 二:Rust 在 main 之前做了什么:用 lldb 不方便,改用现象证明 —— (a) std::env::args 已经可用 (b) SIGPIPE 被设成忽略')
r = tryit('u130b', '''
    fn main() {
        let a: Vec<String> = std::env::args().collect(); println!("参数在 main 开始时就已就绪:{} 个", a.len());
        for i in 0..100000 { if let Err(e) = std::io::Write::write_all(&mut std::io::stdout(), format!("line {}\\n", i).as_bytes()) { eprintln!("写第 {} 行时出错:{:?}", i, e.kind()); std::process::exit(3); } }
    }
''', quiet_src=True, show_run=False)
p = subprocess.run(f'{r["bin"]} | head -1; echo "Rust 程序退出码(PIPESTATUS):${{PIPESTATUS[0]:-n/a}}"', shell=True, capture_output=True, text=True, executable='/bin/bash')
print('  Rust 往被 head 提前关掉的管道里写:'); print('    ' + (p.stdout + p.stderr).strip().replace('\n', '\n    ')); R['sigpipe_rust'] = (p.stdout + p.stderr).strip()
(RS / 'src' / 'u130c.c').write_text('#include <stdio.h>\nint main(void) { for (int i = 0; i < 100000; i++) { printf("line %d\\n", i); } return 0; }\n')
sh(['clang', '-O2', '-o', str(RS / 'bin' / 'u130c'), str(RS / 'src' / 'u130c.c')])
p = subprocess.run(f'{RS / "bin" / "u130c"} | head -1; echo "C 程序退出码(PIPESTATUS):${{PIPESTATUS[0]}}"', shell=True, capture_output=True, text=True, executable='/bin/bash')
print('  对照:C 程序同样的事:'); print('    ' + (p.stdout + p.stderr).strip().replace('\n', '\n    ')); R['sigpipe_c'] = (p.stdout + p.stderr).strip()
print()
print('== 三:启动时间:fork+exec+退出 1000 次的平均耗时,空的 Rust main、Rust no_main、C main')
(RS / 'src' / 'u130d.c').write_text('int main(void) { return 0; }\n'); sh(['clang', '-O2', '-o', str(RS / 'bin' / 'u130d'), str(RS / 'src' / 'u130d.c')])
ok, d, nm_bin, _ = rustc('u130e', '#![no_main]\n#[unsafe(no_mangle)] pub extern "C" fn main(_argc: i32, _argv: *const *const u8) -> i32 { 0 }\n', release=True)
ok, d, rs_bin, _ = rustc('u130f', 'fn main() {}', release=True)
def spawn_time(binp, n=1000):
    best = 9e9
    for _ in range(3):
        t = time.perf_counter()
        for _ in range(n): subprocess.run([str(binp)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        best = min(best, (time.perf_counter() - t) / n * 1e6)
    return best
res = {}
for name, b in [('C 空 main', RS / 'bin' / 'u130d'), ('Rust #![no_main]', nm_bin), ('Rust 空 main(std 的 lang_start)', rs_bin)]:
    res[name] = round(spawn_time(b), 0); print(f'  {name:<28} 平均 {res[name]:.0f} µs / 次(含 Python subprocess 的 fork+exec+wait 开销)')
R['spawn'] = res
sizes = {n: Path(b).stat().st_size for n, b in [('C 空 main', RS / 'bin' / 'u130d'), ('Rust #![no_main]', nm_bin), ('Rust 空 main', rs_bin)]} if False else None
import pathlib
R['sizes'] = {n: pathlib.Path(b).stat().st_size for n, b in [('C 空 main', RS / 'bin' / 'u130d'), ('Rust #![no_main]', nm_bin), ('Rust 空 main', rs_bin)]}
print('  二进制大小:', {k: f'{v:,}' for k, v in R['sizes'].items()})
print()
print('== 四:main 之后:main 返回 ExitCode 时局部变量照常析构、退出码生效;process::exit 则不运行析构')
r = tryit('u130g', '''
    use std::process::ExitCode;
    struct D; impl Drop for D { fn drop(&mut self) { println!("D 被 drop"); } }
    fn main() -> ExitCode { let _d = D; println!("main 里"); ExitCode::from(7) }
''', quiet_src=True)
r2 = tryit('u130h', '''
    struct D; impl Drop for D { fn drop(&mut self) { println!("D 被 drop"); } }
    fn main() { let _d = D; println!("main 里,调用 process::exit(5)"); std::process::exit(5); }
''', quiet_src=True)
R['exit'] = [r['rc'], r['out'], r2['rc'], r2['out']]
save('u130', R)
