import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u160'); R = {}
base = RS / 'proj' / 'u160'; shutil.rmtree(base, ignore_errors=True); (base / 'benches').mkdir(parents=True); (base / 'src').mkdir()
(base / 'Cargo.toml').write_text('[package]\nname = "cb"\nversion = "0.1.0"\nedition = "2024"\n[dev-dependencies]\ncriterion = { version = "0.7", default-features = false, features = ["cargo_bench_support"] }\n[[bench]]\nname = "b"\nharness = false\n')
(base / 'src' / 'lib.rs').write_text('pub fn mix(n: u64) -> u64 { let mut x = 88172645463325252u64; let mut s = 0u64; for _ in 0..n { x ^= x << 13; x ^= x >> 7; x ^= x << 17; s = s.wrapping_add(x); } s }\npub fn mix_slow(n: u64) -> u64 { let mut x = 88172645463325252u64; let mut s = 0u64; for _ in 0..n { x ^= x << 13; x ^= x >> 7; x ^= x << 17; s = s.wrapping_add(x); std::hint::black_box(s); } s }\n')
(base / 'benches' / 'b.rs').write_text('''
use criterion::{criterion_group, criterion_main, Criterion, BenchmarkId, Throughput};\nuse std::hint::black_box;
fn bench(c: &mut Criterion) {
    c.bench_function("mix_1000", |b| b.iter(|| cb::mix(black_box(1000))));
    let mut g = c.benchmark_group("mix_scaling");
    for n in [100u64, 1_000, 10_000] { g.throughput(Throughput::Elements(n)); g.bench_with_input(BenchmarkId::from_parameter(n), &n, |b, &n| b.iter(|| cb::mix(black_box(n)))); }
    g.finish();
}
criterion_group!(benches, bench); criterion_main!(benches);
''')
env = dict(ENVB)
def bench(extra=()):
    t = time.perf_counter(); rc, o, e = sh(['cargo', 'bench', '--bench', 'b', *extra, '--', '--warm-up-time', '1', '--measurement-time', '2'], cwd=base, env=env, timeout=1800); return rc, o + e, time.perf_counter() - t
print('== 一:Criterion 在稳定版上运行(harness = false):每个基准先预热、再采样 100 次,给出时间的置信区间 [下界 估计 上界]')
shutil.rmtree(TG / 'criterion', ignore_errors=True)
rc, o, el = bench(); print(f'  (含下载编译 criterion,第一次约 {el:.0f} s)'); L = [l for l in o.splitlines() if l.strip() and (l.strip().startswith(('mix_', 'thrpt', 'time')) or 'outliers' in l or l.strip()[0].isdigit())]
print('\n'.join('  ' + l for l in L[:30])); R['first'] = L[:30]
if rc != 0: print(o[-800:])
print()
print('== 二:不改代码再跑一次:Criterion 把这次与上一次比较,给出 change 与 p 值 —— 看它怎么处理纯粹的机器噪声')
rc, o, el = bench(); L = [l for l in o.splitlines() if l.strip() and ('time:' in l or 'change:' in l or 'No change' in l or 'within noise' in l or 'regressed' in l or 'improved' in l or l.strip().startswith(('mix_1000', 'mix_scaling')) or 'p =' in l)]; print('\n'.join('  ' + l for l in L[:20])); R['second'] = L[:20]
print()
print('== 三:换成另一个实现(mix_slow:循环里每轮多一次 black_box)再测:Criterion 给出变化百分比与 p 值')
(base / 'benches' / 'b.rs').write_text((base / 'benches' / 'b.rs').read_text().replace('cb::mix(black_box(1000))', 'cb::mix_slow(black_box(1000))').replace('cb::mix(black_box(n))', 'cb::mix_slow(black_box(n))'))
rc, o, el = bench(); L = [l for l in o.splitlines() if l.strip() and ('time:' in l or 'change:' in l or 'No change' in l or 'regressed' in l or 'improved' in l or l.strip().startswith(('mix_1000', 'mix_scaling')) or 'p =' in l)]; print('\n'.join('  ' + l for l in L[:22])); R['third'] = L[:22]
print()
print('== 四:Criterion 写到 target/criterion 下的数据:每个基准的 estimates.json(均值/中位数/标准差)')
import json
est = sorted((TG / 'criterion').rglob('new/estimates.json')); print(f'  找到 {len(est)} 个 estimates.json:', [str(p.relative_to(TG / 'criterion')) for p in est][:6])
if est:
    j = json.loads([p for p in est if 'mix_1000' in str(p)][0].read_text()); print('  mix_1000 的 mean:', {k: (round(v, 1) if isinstance(v, float) else v) for k, v in j['mean'].items() if k in ('point_estimate',)}, ' 置信区间(ns):', [round(j['mean']['confidence_interval'][k], 1) for k in ('lower_bound', 'upper_bound')], ' median:', round(j['median']['point_estimate'], 1), ' std_dev:', round(j['std_dev']['point_estimate'], 1)); R['est'] = {'mean': j['mean']['point_estimate'], 'ci': [j['mean']['confidence_interval']['lower_bound'], j['mean']['confidence_interval']['upper_bound']], 'median': j['median']['point_estimate'], 'std': j['std_dev']['point_estimate']}
save('u160', R)
