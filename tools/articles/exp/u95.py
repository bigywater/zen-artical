import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u95'); R = {}
base = RS / 'proj' / 'u95'; shutil.rmtree(base, ignore_errors=True)
def app(code, name='u95'):
    d = proj(name, {'src/main.rs': code}, deps='rayon = "1"'); return d
def run_proj(d, name, label=None, release=True, timeout=900):
    rc, o = cargo(['build'] + (['--release'] if release else []) + ['--quiet'], d, timeout=timeout)
    if rc != 0: return rc, o
    rc, so, se, _ = run(TG / ('release' if release else 'debug') / name); return rc, so.strip()
print('== 一:par_iter 与 iter 的结果相同,并且 collect 保持原顺序;线程数等于 CPU 核数')
d = app('''
    use rayon::prelude::*;
    fn main() {
        println!("可用并行度 {}  rayon 线程数 {}", std::thread::available_parallelism().unwrap(), rayon::current_num_threads());
        let v: Vec<u64> = (1..=20).collect();
        let sq: Vec<u64> = v.par_iter().map(|x| x * x).collect();
        println!("par_iter().map().collect() 保持原顺序: {}", sq == v.iter().map(|x| x * x).collect::<Vec<_>>());
        println!("par_iter().sum() = {}  iter().sum() = {}", v.par_iter().sum::<u64>(), v.iter().sum::<u64>());
        let seen = std::sync::Mutex::new(Vec::new());
        (0..16).into_par_iter().for_each(|i| { seen.lock().unwrap().push(i); });
        let mut s = seen.into_inner().unwrap(); let in_order = s.windows(2).all(|w| w[0] < w[1]); s.sort();
        println!("for_each 里的执行顺序按 0..16 排好: {}(并行执行,顺序不保证);内容齐全: {}", in_order, s == (0..16).collect::<Vec<_>>());
    }
''', 'u95a')
t0 = time.perf_counter(); rc, o = run_proj(d, 'u95a'); print(f'  (含下载编译 rayon,用时 {time.perf_counter() - t0:.0f} s)'); print('\n'.join('  ' + l for l in o.splitlines())); R['basic'] = o
print()
print('== 二:CPU 密集任务(对 2000 万个数做 sin 求和)串行 vs 并行(release,取 3 次最小)')
d = app('''
    use rayon::prelude::*; use std::time::Instant; use std::hint::black_box;
    fn main() {
        let v: Vec<f64> = (0..20_000_000).map(|i| i as f64 * 0.001).collect();
        let (mut ts, mut tp) = (f64::MAX, f64::MAX); let (mut rs, mut rp) = (0.0, 0.0);
        for _ in 0..3 {
            let t = Instant::now(); rs = black_box(&v).iter().map(|x| x.sin()).sum::<f64>(); ts = ts.min(t.elapsed().as_secs_f64() * 1e3);
            let t = Instant::now(); rp = black_box(&v).par_iter().map(|x| x.sin()).sum::<f64>(); tp = tp.min(t.elapsed().as_secs_f64() * 1e3);
        }
        println!("串行 iter    {:>8.1} ms  结果 {:.6}", ts, rs);
        println!("并行 par_iter {:>7.1} ms  结果 {:.6}  加速 {:.1}×", tp, rp, ts / tp);
        println!("浮点求和的结果在小数点后 {} 位一致(并行的加法顺序不同)", (1..12).take_while(|d| (rs - rp).abs() < 10f64.powi(-(*d as i32))).last().unwrap_or(0));
    }
''', 'u95b')
rc, o = run_proj(d, 'u95b'); print('\n'.join('  ' + l for l in o.splitlines())); R['heavy'] = o
print()
print('== 三:任务小时并行反而更慢:对 100 / 1 万 / 100 万 / 1 亿个 u64 求和,看串行与并行的交叉点')
d = app('''
    use rayon::prelude::*; use std::time::Instant; use std::hint::black_box;
    fn main() {
        for n in [100usize, 10_000, 1_000_000, 100_000_000] {
            let v: Vec<u64> = (0..n as u64).collect(); let reps = (200_000_000 / n).clamp(3, 20000);
            let t = Instant::now(); for _ in 0..reps { black_box(black_box(&v).iter().sum::<u64>()); } let ts = t.elapsed().as_secs_f64() * 1e6 / reps as f64;
            let t = Instant::now(); for _ in 0..reps { black_box(black_box(&v).par_iter().sum::<u64>()); } let tp = t.elapsed().as_secs_f64() * 1e6 / reps as f64;
            println!("n={:>10}: 串行 {:>10.2} µs   并行 {:>10.2} µs   {}", n, ts, tp, if tp < ts { "并行更快" } else { "串行更快" });
        }
    }
''', 'u95c')
rc, o = run_proj(d, 'u95c', timeout=900); print('\n'.join('  ' + l for l in o.splitlines())); R['small'] = o
print()
print('== 四:线程池大小对加速的影响(ThreadPoolBuilder 指定 1 / 2 / 4 / 8 / 全部核数 个线程)')
d = app('''
    use rayon::prelude::*; use std::time::Instant; use std::hint::black_box;
    fn main() {
        let v: Vec<f64> = (0..10_000_000).map(|i| i as f64 * 0.001).collect();
        let max = std::thread::available_parallelism().unwrap().get();
        let mut base = 0.0;
        for n in [1usize, 2, 4, 8, max] {
            if n > max { continue; }
            let pool = rayon::ThreadPoolBuilder::new().num_threads(n).build().unwrap();
            let mut best = f64::MAX;
            for _ in 0..3 { let t = Instant::now(); pool.install(|| black_box(black_box(&v).par_iter().map(|x| x.sin()).sum::<f64>())); best = best.min(t.elapsed().as_secs_f64() * 1e3); }
            if n == 1 { base = best; }
            println!("线程数 {:>2}: {:>8.1} ms  相对 1 线程 {:.1}×", n, best, base / best);
        }
    }
''', 'u95d')
rc, o = run_proj(d, 'u95d'); print('\n'.join('  ' + l for l in o.splitlines())); R['scale'] = o
print()
print('== 五:并行闭包里共享可变状态:Mutex 竞争把并行吃掉;用 reduce / fold 避免共享')
d = app('''
    use rayon::prelude::*; use std::{sync::Mutex, time::Instant, hint::black_box};
    fn main() {
        let v: Vec<u64> = (0..5_000_000).collect();
        let t = Instant::now(); let m = Mutex::new(0u64); black_box(&v).par_iter().for_each(|x| { *m.lock().unwrap() += x; }); let tm = t.elapsed().as_secs_f64() * 1e3; let rm = *m.lock().unwrap();
        let t = Instant::now(); let rr = black_box(&v).par_iter().copied().reduce(|| 0, |a, b| a + b); let tr = t.elapsed().as_secs_f64() * 1e3;
        let t = Instant::now(); let rs: u64 = black_box(&v).iter().sum(); let ts = t.elapsed().as_secs_f64() * 1e3;
        println!("par_iter + Mutex  {:>8.2} ms  结果 {}", tm, rm); println!("par_iter + reduce {:>8.2} ms  结果 {}", tr, rr); println!("串行 sum          {:>8.2} ms  结果 {}", ts, rs);
    }
''', 'u95e')
rc, o = run_proj(d, 'u95e'); print('\n'.join('  ' + l for l in o.splitlines())); R['mutex'] = o
print()
print('== 六:闭包捕获了不是 Send / Sync 的东西:编译器的错误')
d = app('''
    use rayon::prelude::*; use std::cell::RefCell;
    fn main() { let c = RefCell::new(0); (0..4).into_par_iter().for_each(|i| { *c.borrow_mut() += i; }); }
''', 'u95f')
rc, o = cargo(['build', '--quiet'], d, timeout=600); el = [l for l in o.splitlines() if l.strip()][:9]; print('\n'.join('  ' + l for l in el)); R['err'] = el
save('u95', R)
