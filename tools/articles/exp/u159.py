import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u159'); R = {}
base = RS / 'proj' / 'u159'; shutil.rmtree(base, ignore_errors=True); (base / 'benches').mkdir(parents=True); (base / 'src').mkdir()
(base / 'Cargo.toml').write_text('[package]\nname = "bm"\nversion = "0.1.0"\nedition = "2024"\n')
(base / 'src' / 'lib.rs').write_text('pub fn sum_to(n: u64) -> u64 { (0..n).fold(0, |a, b| a.wrapping_add(b.wrapping_mul(b))) }\npub fn mix(n: u64) -> u64 { let mut x = 88172645463325252u64; let mut s = 0u64; for _ in 0..n { x ^= x << 13; x ^= x >> 7; x ^= x << 17; s = s.wrapping_add(x); } s }\npub fn sort_vec(v: &mut Vec<u32>) { v.sort(); }\n')
(base / 'benches' / 'b.rs').write_text(textwrap.dedent('''
    #![feature(test)]
    extern crate test;
    use test::{Bencher, black_box};
    #[bench] fn sum_squares_no_blackbox(b: &mut Bencher) { b.iter(|| { bm::sum_to(1000); }); }              // 结果没人用
    #[bench] fn sum_squares_with_blackbox(b: &mut Bencher) { b.iter(|| bm::sum_to(black_box(1000))); }      // 输入和输出都经过 black_box
    #[bench] fn mix_no_blackbox(b: &mut Bencher) { b.iter(|| { bm::mix(1000); }); }                        // 结果没人用
    #[bench] fn mix_with_blackbox(b: &mut Bencher) { b.iter(|| bm::mix(black_box(1000))); }                // 输入和输出都经过 black_box
    #[bench] fn sort_1000(b: &mut Bencher) { let src: Vec<u32> = (0..1000u32).map(|i| i.wrapping_mul(2654435761) % 10007).collect(); b.iter(|| { let mut v = src.clone(); bm::sort_vec(&mut v); v }); }
    #[bench] fn clone_only_1000(b: &mut Bencher) { let src: Vec<u32> = (0..1000u32).collect(); b.iter(|| src.clone()); }
'''))
env = dict(ENVB, RUSTC_BOOTSTRAP='1')
def bench(extra=()):
    rc, o, e = sh(['cargo', 'bench', '--quiet', *extra], cwd=base, env=env, timeout=900); return rc, o, e
print('== 一:#[bench](标准库自带的基准框架,需要 nightly 特性,这里用 RUSTC_BOOTSTRAP=1 打开):cargo bench 用 bench profile(与 release 同样优化)')
rc, o, e = bench(); L = [l for l in o.splitlines() if l.startswith('test ') or 'test result' in l]; print('\n'.join('  ' + l for l in L)); R['bench1'] = L
if rc != 0: print('  ', (o + e)[:500])
print()
print('== 二:基准里的结果没人用时优化器可能整个删掉计算;有 black_box 才量到真实耗时;但有些循环会被折叠成闭式公式')
vals = {l.split()[1]: float(re.search(r'([\d,.]+) ns/iter', l).group(1).replace(',', '')) for l in L if 'bench:' in l}
print(f'  mix(1000)(循环里 1000 次 xorshift,不能折叠成公式):没有 black_box {vals["mix_no_blackbox"]} ns/iter;有 black_box {vals["mix_with_blackbox"]} ns/iter(约 {vals["mix_with_blackbox"] / max(vals["mix_no_blackbox"], 0.01):.0f} 倍)')
print(f'  sum_to(1000)(平方和,即使加了 black_box 也只有 {vals["sum_squares_with_blackbox"]} ns/iter —— 远低于做 1000 次乘加所需的时间,说明优化器把循环变成了闭式公式)'); R['vals'] = vals
code_s = '#[unsafe(no_mangle)] pub fn sum_to(n: u64) -> u64 { (0..n).fold(0, |a, b| a.wrapping_add(b.wrapping_mul(b))) }\n#[unsafe(no_mangle)] pub fn mix(n: u64) -> u64 { let mut x = 88172645463325252u64; let mut s = 0u64; for _ in 0..n { x ^= x << 13; x ^= x >> 7; x ^= x << 17; s = s.wrapping_add(x); } s }'
for fn in ('sum_to', 'mix'):
    bl, _ = asm_of('u159a', code_s, fn); ins = [l for l in bl if l.strip() and not l.strip().startswith(('.', 'L', ';')) and not l.endswith(':')]; back = [l for l in bl if re.match(r'\s*b\.?\w*\s+LBB', l) or re.match(r'\s*cb\w*\s+\w+, LBB', l)]
    print(f'  汇编里 {fn}:{len(ins)} 条指令,{len(back)} 条跳转到本函数标签'); R.setdefault('asm', {})[fn] = [len(ins), len(back)]
    if fn == 'sum_to': print('  sum_to 的全部指令:', ' ; '.join(re.sub(r'\\s+', ' ', l.strip()) for l in ins)); R['sum_asm'] = [re.sub(r'\\s+', ' ', l.strip()) for l in ins]
print()
print('== 三:同一个基准重复运行的波动:连续跑 5 次,看 ns/iter 与 (+/- ) 的范围')
runs = []
for _ in range(5):
    rc, o, e = bench(); runs.append({l.split()[1]: l.split('bench:')[1].strip() for l in o.splitlines() if 'bench:' in l and ('sort_1000' in l or 'mix_with_blackbox' in l)})
for k in ('mix_with_blackbox', 'sort_1000'): print(f'  {k}:', [r[k] for r in runs])
R['runs'] = runs
print()
print('== 四:基准里把准备工作也算进去了:sort_1000 的耗时包含 clone;减去 clone_only_1000 才是排序本身')
c = vals['clone_only_1000']; s = vals['sort_1000']; print(f'  sort_1000 {s} ns/iter(含 clone 一个 1000 元素的 Vec)  clone_only_1000 {c} ns/iter  → 排序本身约 {s - c} ns,占 {100 * (s - c) / s:.0f}%'); R['sort'] = [s, c]
print()
print('== 五:不用 nightly 的写法:稳定版里用 std::hint::black_box 和 Instant 自己写(自适应迭代次数);与上面 #[bench] 结果对照')
ok, d, b, _ = rustc('u159m', '''
    use std::{hint::black_box, time::Instant};
    fn sum_to(n: u64) -> u64 { (0..n).fold(0, |a, b| a.wrapping_add(b.wrapping_mul(b))) }
    fn mix(n: u64) -> u64 { let mut x = 88172645463325252u64; let mut s = 0u64; for _ in 0..n { x ^= x << 13; x ^= x >> 7; x ^= x << 17; s = s.wrapping_add(x); } s }
    fn bench<F: FnMut() -> u64>(name: &str, mut f: F) {
        let mut iters = 1u64; loop { let t = Instant::now(); for _ in 0..iters { black_box(f()); } if t.elapsed().as_millis() >= 50 || iters > 1 << 30 { break; } iters *= 2; }
        let mut best = f64::MAX; for _ in 0..5 { let t = Instant::now(); for _ in 0..iters { black_box(f()); } best = best.min(t.elapsed().as_secs_f64() * 1e9 / iters as f64); }
        println!("{:<22} {:>9.1} ns/iter(迭代 {} 次,5 轮取最小)", name, best, iters);
    }
    fn main() { bench("sum_to(1000) 稳定版", || sum_to(black_box(1000))); bench("mix(1000) 稳定版", || mix(black_box(1000))); bench("空闭包(测量开销)", || black_box(0)); }
''', release=True); assert ok, d
rc, so, se, _ = run(b); print('\n'.join('  ' + l for l in so.strip().splitlines())); R['stable'] = so.strip().splitlines()
save('u159', R)
