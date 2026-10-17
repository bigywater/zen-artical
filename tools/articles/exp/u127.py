import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u127'); R = {}
MAIN = '''
    use std::collections::HashMap; use std::time::Instant;
    fn collatz(mut n: u64) -> u32 { let mut c = 0; while n != 1 { n = if n % 2 == 0 { n / 2 } else { 3 * n + 1 }; c += 1; } c }
    fn main() {
        println!("debug_assertions 开启: {}", cfg!(debug_assertions));
        let t = Instant::now(); let best = (1..300_000u64).map(|n| (collatz(n), n)).max().unwrap(); let t1 = t.elapsed().as_secs_f64() * 1e3;
        let t = Instant::now(); let mut m: HashMap<u64, u64> = HashMap::new(); for i in 0..500_000u64 { *m.entry(i % 1000).or_insert(0) += i; } let t2 = t.elapsed().as_secs_f64() * 1e3;
        let t = Instant::now(); let mut v: Vec<u64> = (0..1_000_000).map(|i| (i * 2654435761u64) % 1_000_003).collect(); v.sort(); let t3 = t.elapsed().as_secs_f64() * 1e3;
        println!("collatz 最长链 {:?}:{:.1} ms   HashMap 50 万次更新:{:.1} ms   100 万个数排序:{:.1} ms   (校验 {} {})", best, t1, t2, t3, m[&7], v[500_000]);
    }
'''
print('== 一:同一个程序用 cargo build(dev)与 cargo build --release:速度、二进制大小')
d = proj('u127', {'src/main.rs': MAIN})
res = {}
for prof in ('dev', 'release'):
    shutil.rmtree(TG / ('debug' if prof == 'dev' else 'release') / 'incremental', ignore_errors=True)
    t0 = time.perf_counter(); rc, o = cargo(['build'] + (['--release'] if prof == 'release' else []) + ['--quiet'], d, timeout=600); tb = time.perf_counter() - t0
    binp = TG / ('debug' if prof == 'dev' else 'release') / 'u127'; sz = binp.stat().st_size
    rc, so, se, _ = run(binp); res[prof] = {'build': round(tb, 2), 'size': sz, 'out': so.strip()}
    print(f'  [{prof}] 编译 {tb:.2f} s  二进制 {sz:,} 字节'); print('    ' + so.strip().replace('\n', '\n    '))
R['prof'] = res
print()
print('== 二:单独调整 Cargo profile:release 加 debug-assertions 与 overflow-checks;dev 提高 opt-level —— 看哪个开关决定了速度')
variants = {
    'dev(默认)': '', 'dev + opt-level=3': '[profile.dev]\nopt-level = 3', 'release(默认)': '',
    'release + overflow-checks': '[profile.release]\noverflow-checks = true', 'release + debug-assertions': '[profile.release]\ndebug-assertions = true',
}
R['var'] = {}
for name, extra in variants.items():
    prof = 'release' if name.startswith('release') else 'dev'
    d2 = proj('u127v', {'src/main.rs': MAIN}, toml_extra=extra)
    rc, o = cargo(['build'] + (['--release'] if prof == 'release' else []) + ['--quiet'], d2, timeout=600)
    binp = TG / ('release' if prof == 'release' else 'debug') / 'u127v'; rc, so, se, _ = run(binp)
    ts = re.findall(r'([\d.]+) ms', so); R['var'][name] = [float(x) for x in ts]; print(f'  {name:<26} collatz {ts[0]:>8} ms  HashMap {ts[1]:>7} ms  排序 {ts[2]:>7} ms  | {so.splitlines()[0]}')
print()
print('== 三:溢出行为差异的真实例子:同一段代码在 dev 里 panic,在 release 里回绕(上一篇 panic 里也出现过);这里用 Cargo 的两个 profile 直接验证')
d3 = proj('u127o', {'src/main.rs': '''
    fn main() { let n = std::env::args().count() as u8; let x: u8 = 250 + n * 6; println!("250 + {} * 6 = {}", n, x); }
'''})
for prof in ('dev', 'release'):
    cargo(['build'] + (['--release'] if prof == 'release' else []) + ['--quiet'], d3, timeout=600); rc, so, se, _ = run(TG / ('release' if prof == 'release' else 'debug') / 'u127o')
    last = [l for l in se.splitlines() if l.strip() and 'note: run' not in l][-1:]; print(f'  {prof:<8} 退出码 {rc}  stdout={so.strip()!r}  stderr 末行={last}'); R['ovf_' + prof] = [rc, so.strip(), last]
save('u127', R)
