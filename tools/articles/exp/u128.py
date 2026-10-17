import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u128'); R = {}
MAIN = '''
    use rayon::prelude::*; use std::collections::HashMap;
    fn main() {
        let v: Vec<u64> = (0..1_000_000).collect();
        let s: u64 = v.par_iter().map(|x| x * x % 7).sum();
        let mut m: HashMap<String, usize> = HashMap::new(); for i in 0..1000 { *m.entry(format!("k{}", i % 17)).or_default() += i; }
        let mut keys: Vec<_> = m.iter().collect(); keys.sort();
        println!("{} {:?}", s, &keys[..3]);
    }
'''
variants = [
    ('release(默认)', ''),
    ('+ strip = true', '[profile.release]\nstrip = true'),
    ('+ lto = "thin"', '[profile.release]\nlto = "thin"'),
    ('+ lto = "fat"', '[profile.release]\nlto = "fat"'),
    ('+ lto fat + codegen-units = 1', '[profile.release]\nlto = "fat"\ncodegen-units = 1'),
    ('+ panic = "abort"', '[profile.release]\npanic = "abort"'),
    ('+ opt-level = "s"', '[profile.release]\nopt-level = "s"'),
    ('+ opt-level = "z"', '[profile.release]\nopt-level = "z"'),
    ('全套:fat+cgu1+abort+z+strip', '[profile.release]\nlto = "fat"\ncodegen-units = 1\npanic = "abort"\nopt-level = "z"\nstrip = true'),
]
print('== 一:同一个使用了 rayon + HashMap + format! 的程序,在不同 release profile 下的二进制大小、编译时间与运行时间(各变体全量重编)')
print(f'  {"配置":<32}{"大小(字节)":>12}{"相对默认":>8}{"编译(s)":>9}{"运行(ms)":>10}')
base = None; R['rows'] = []
for name, extra in variants:
    d = proj('u128', {'src/main.rs': MAIN}, toml_extra=extra, deps='rayon = "1"')
    shutil.rmtree(TG / 'release', ignore_errors=True)
    t0 = time.perf_counter(); rc, o = cargo(['build', '--release', '--quiet'], d, timeout=900); tb = time.perf_counter() - t0
    binp = TG / 'release' / 'u128'; sz = binp.stat().st_size
    ts = []
    for _ in range(5):
        t = time.perf_counter(); rc2, so, se, _ = run(binp); ts.append((time.perf_counter() - t) * 1e3)
    if base is None: base = sz
    print(f'  {name:<32}{sz:>12,}{sz / base:>8.2f}{tb:>9.1f}{min(ts):>10.1f}'); R['rows'].append([name, sz, round(tb, 1), round(min(ts), 1), rc2])
save('u128', R)
