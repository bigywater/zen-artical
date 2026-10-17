import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u129'); R = {}
def gen(n_mod=200, per=25, tweak=0):
    files = {}
    mods = ''.join(f'mod m{i};\n' for i in range(n_mod))
    calls = ' + '.join(f'm{i}::f0({i})' for i in range(n_mod))
    files['src/main.rs'] = mods + f'fn main() {{ let t: u64 = {calls}; println!("{{}}", t); }}\n'
    for i in range(n_mod):
        body = '\n'.join(f'pub fn f{j}(x: u64) -> u64 {{ let mut v: Vec<u64> = (0..{j + 5}).map(|k| k * x + {j}).collect(); v.sort(); v.iter().sum::<u64>() + {"f%d(x)" % (j - 1) if j > 0 else "x"} }}' for j in range(per))
        files[f'src/m{i}.rs'] = body + '\n'
    files['src/m0.rs'] = files['src/m0.rs'].replace('f0(x: u64) -> u64 { let mut v', f'f0(x: u64) -> u64 {{ let tweak = {tweak}; let mut v', 1)
    return files
def build(d, env_extra, release=False):
    env = dict(ENVB, **env_extra); t0 = time.perf_counter(); rc, o, e = sh(['cargo', 'build', '--quiet'] + (['--release'] if release else []), cwd=d, env=env, timeout=900); return time.perf_counter() - t0
def dirsize(p): return du(p) if p.exists() else 0
print('== 一:增量编译开 / 关:200 个模块 × 25 个函数(5000 个函数)的 crate;首次全量编译、没有改动、改动一个函数体后的重新编译时间(dev profile)')
R['rows'] = {}
for label, inc in (('CARGO_INCREMENTAL=1(dev 默认)', '1'), ('CARGO_INCREMENTAL=0', '0')):
    d = proj('u129', gen(), edition='2024'); shutil.rmtree(TG / 'debug', ignore_errors=True)
    env = {'CARGO_INCREMENTAL': inc}
    t_full = build(d, env); t_noop = build(d, env)
    ts = []
    for k in range(1, 4):
        (d / 'src' / 'm0.rs').write_text(gen(tweak=k)['src/m0.rs']); ts.append(build(d, env))
    inc_dir = dirsize(TG / 'debug' / 'incremental')
    print(f'  {label:<32} 首次 {t_full:>5.2f} s   没改动 {t_noop:>5.2f} s   改一个函数体后 {min(ts):>5.2f} s(3 次最小)   target/debug/incremental 大小 {inc_dir / 1e6:.1f} MB')
    R['rows'][label] = [round(t_full, 2), round(t_noop, 2), round(min(ts), 2), round(inc_dir / 1e6, 1)]
print()
print('== 二:release profile 默认不开增量;强制开(CARGO_INCREMENTAL=1)后看重编时间(只比较编译时间,没有比较产物的运行速度)')
R['rel'] = {}
for label, inc in (('release 默认(无增量)', '0'), ('release + CARGO_INCREMENTAL=1', '1')):
    d = proj('u129r', gen(), edition='2024'); shutil.rmtree(TG / 'release', ignore_errors=True); env = {'CARGO_INCREMENTAL': inc}
    t_full = build(d, env, True); ts = []
    for k in range(1, 3):
        (d / 'src' / 'm0.rs').write_text(gen(tweak=k)['src/m0.rs']); ts.append(build(d, env, True))
    print(f'  {label:<32} 首次 {t_full:>5.2f} s   改一个函数体后 {min(ts):>5.2f} s'); R['rel'][label] = [round(t_full, 2), round(min(ts), 2)]
save('u129', R)
