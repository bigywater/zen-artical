import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u157'); R = {}
def mk(base, files):
    for p, c in files.items(): f = base / p; f.parent.mkdir(parents=True, exist_ok=True); f.write_text(textwrap.dedent(c).lstrip('\n'))
base = RS / 'proj' / 'u157'; shutil.rmtree(base, ignore_errors=True)
mk(base, {
 'Cargo.toml': '[package]\nname = "calc"\nversion = "0.1.0"\nedition = "2024"\n',
 'src/lib.rs': '''
   //! 一个小库:公开 `add`,私有 `secret`
   pub fn add(a: i32, b: i32) -> i32 { a + b }
   #[allow(dead_code)] fn secret(n: i32) -> i32 { n * 42 }
   pub fn div(a: i32, b: i32) -> i32 { if b == 0 { panic!("除数不能为 0") } a / b }
   #[cfg(test)]
   mod tests {
       use super::*;
       #[test] fn add_works() { assert_eq!(add(2, 3), 5); }
       #[test] fn can_test_private() { assert_eq!(secret(2), 84); }          // 单元测试在同一个模块树里,能访问私有函数
       #[test] #[should_panic(expected = "除数不能为 0")] fn div_by_zero() { div(1, 0); }
       #[test] #[ignore = "很慢"] fn slow_test() { std::thread::sleep(std::time::Duration::from_millis(300)); }
       #[test] fn prints_something() { println!("这行 stdout 默认被捕获,只有失败或 --nocapture 才显示"); }
   }
 ''',
 'tests/api.rs': '''
   use calc::add;
   #[test] fn public_api() { assert_eq!(add(10, 20), 30); }
   #[test] fn failing_example() { assert_eq!(add(1, 1), 3, "故意失败的断言"); }
 ''',
 'tests/second.rs': 'use calc::div;\n#[test] fn div_ok() { assert_eq!(div(9, 3), 3); }\n',
})
def ct(args, cwd=base, env=None): return cargo(['test'] + args, cwd, timeout=600, env=env)
def clean(o): return [l.replace(str(RS), '<实验目录>') for l in o.splitlines() if l.strip() and 'Compiling' not in l and 'Finished' not in l]
print('== 一:cargo test 运行哪几类测试:每个测试目标各自一个可执行文件,输出各自的汇总行(此处 api.rs 里有一个故意失败的测试,先把它忽略掉看全貌)')
rc, o = ct(['--', '--skip', 'failing_example']); L = clean(o); print('\n'.join('  ' + l for l in L)); R['all'] = L
print()
print('== 二:integration 测试只能用公开 API:试图调用私有函数 secret 会编译失败(E0603)')
(base / 'tests' / 'priv.rs').write_text('use calc::secret;\n#[test] fn t() { assert_eq!(secret(1), 42); }\n')
rc, o = ct(['--test', 'priv']); L = [l for l in clean(o) if 'error' in l or 'private' in l][:3]; print('\n'.join('  ' + l for l in L)); R['priv'] = L; (base / 'tests' / 'priv.rs').unlink()
print()
print('== 三:过滤、忽略与 should_panic:按名字过滤、--ignored 运行被忽略的、--include-ignored、--list')
rc, o = ct(['--lib', '--', '--list']); print('  --list 列出的单元测试:', [l.strip() for l in o.splitlines() if ': test' in l]); R['list'] = [l.strip() for l in o.splitlines() if ': test' in l]
for label, args in [('按名字过滤 add', ['--lib', 'add']), ('--ignored 只跑被忽略的', ['--lib', '--', '--ignored']), ('默认(被忽略的显示为 ignored)', ['--lib'])]:
    rc, o = ct(args); L = [l.strip() for l in clean(o) if l.strip().startswith(('test ', 'test result'))]; print(f'  {label}:'); print('\n'.join('    ' + l for l in L)); R.setdefault('filter', {})[label] = L
print()
print('== 四:失败的测试:退出码与失败信息;输出捕获:通过的测试 println! 看不到,失败的测试会把捕获的输出一起打印')
rc, o = ct(['--test', 'api']); L = clean(o); print(f'  cargo test --test api 退出码 {rc}'); print('\n'.join('  ' + l for l in L[:30])); R['fail'] = [rc, L[:30]]
rc, o = ct(['--lib', '--', '--nocapture', 'prints_something']); print('  --nocapture 时:', [l.strip() for l in o.splitlines() if '捕获' in l]); R['nocapture'] = [l.strip() for l in o.splitlines() if '捕获' in l]
rc, o = ct(['--lib', '--', 'prints_something']); print('  不加 --nocapture(通过的测试):', [l.strip() for l in o.splitlines() if '捕获' in l]); R['capture'] = [l.strip() for l in o.splitlines() if '捕获' in l]
print()
print('== 五:测试默认并行(每个测试一个线程);用共享状态观察,与 --test-threads=1 对比')
mk(base, {'tests/par.rs': '''
   use std::{sync::atomic::{AtomicUsize, Ordering::SeqCst}, thread, time::Duration};
   static RUNNING: AtomicUsize = AtomicUsize::new(0); static MAX: AtomicUsize = AtomicUsize::new(0);
   fn work() { let n = RUNNING.fetch_add(1, SeqCst) + 1; MAX.fetch_max(n, SeqCst); thread::sleep(Duration::from_millis(100)); RUNNING.fetch_sub(1, SeqCst); }
   #[test] fn a() { work(); } #[test] fn b() { work(); } #[test] fn c() { work(); } #[test] fn d() { work(); }
   #[test] fn zz_report() { thread::sleep(Duration::from_millis(400)); println!("同时运行的 work() 最多 {} 个", MAX.load(SeqCst)); }
'''})
for label, args in [('默认并行', []), ('--test-threads=1', ['--test-threads=1'])]:
    t = time.perf_counter(); rc, o = ct(['--test', 'par', '--', '--nocapture'] + args); el = time.perf_counter() - t
    L = [l.strip() for l in o.splitlines() if '最多' in l]; fin = re.search(r'finished in ([\d.]+)s', o).group(1); print(f'  {label:<18} {L}  测试汇总行里的 finished in {fin} s'); R.setdefault('par', {})[label] = [L, float(fin)]
save('u157', R)
