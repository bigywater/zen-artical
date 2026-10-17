import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u123'); R = {}
code = '''
    use std::collections::HashMap;
    #[derive(Debug, Clone)] struct Item { id: u32, name: String }
    fn total(items: &[Item]) -> u32 { items.iter().map(|i| i.id).sum() }
    fn main() {
        let items: Vec<Item> = (0..5).map(|i| Item { id: i, name: format!("n{}", i) }).collect();
        let mut m: HashMap<u32, &Item> = HashMap::new(); for i in &items { m.insert(i.id, i); }
        println!("{} {}", total(&items), m.len());
    }
'''
f = src_file('u123a', code)
print('== 一:rustc 一次编译会产出哪些东西:逐个 --emit 选项(文件类型与大小)')
rows = []
for kind, ext in [('dep-info', 'd'), ('metadata', 'rmeta'), ('mir', 'mir'), ('llvm-ir', 'll'), ('asm', 's'), ('obj', 'o')]:
    out = RS / 'bin' / f'u123a.{ext}'; out.unlink(missing_ok=True)
    rc, o, e = sh(['rustc', '--edition=2024', '--crate-type=' + ('lib' if kind == 'metadata' else 'bin'), f'--emit={kind}', '-C', 'debuginfo=0', '-o', str(out), str(f)])
    sz = out.stat().st_size if out.exists() else -1; rows.append((kind, ext, sz)); print(f'  --emit={kind:<9} → .{ext:<6} {sz:>8,} 字节')
R['emit'] = rows
print()
print('== 二:各阶段耗时(-Z time-passes,RUSTC_BOOTSTRAP=1):按出现顺序列出占时最多的阶段')
rc, o, e = sh(['rustc', '--edition=2024', '--crate-type=bin', '-Z', 'time-passes', '-o', str(RS / 'bin' / 'u123t'), str(f)], env=dict(ENVB, RUSTC_BOOTSTRAP='1'))
lines = [l for l in (o + e).splitlines() if re.match(r'time:\s+[\d.]+;', l.strip())]
phases = []
for l in lines:
    m = re.match(r'time:\s+([\d.]+); rss:\s+(\d+)MB.*?\s+([A-Za-z_][\w ,:()\-\[\]./]*)$', l.strip())
    if m: phases.append((float(m.group(1)), m.group(3).strip()))
top = sorted(phases, key=lambda x: -x[0])[:12]
print(f'  共 {len(phases)} 个计时条目;耗时最长的 12 个(秒):')
for t, n in top: print(f'    {t:>7.3f} s  {n}')
R['top'] = [[t, n] for t, n in top]; R['nphases'] = len(phases)
total_line = [l for l in (o + e).splitlines() if 'total' in l and 'time' in l][:1]; print('  ', total_line); R['total'] = total_line
print()
print('== 三:time-passes 的全部条目(按出现顺序,秒;条目是嵌套的,不能直接相加)')
for t, n in phases: print(f'  {t:>7.3f}  {n}')
R['all'] = [[t, n] for t, n in phases]
print()
print('== 四:同一个程序 debug 与 release:time-passes 里 LLVM_passes 与 total 的变化(各取 3 次最小)')
def passes(flags):
    best = {}
    for _ in range(3):
        rc, o, e = sh(['rustc', '--edition=2024', '--crate-type=bin', *flags, '-Z', 'time-passes', '-o', str(RS / 'bin' / 'u123b'), str(f)], env=dict(ENVB, RUSTC_BOOTSTRAP='1'))
        for l in (o + e).splitlines():
            m = re.match(r'time:\s+([\d.]+);.*?\s(LLVM_passes|total|link_binary|type_check_crate)$', l.strip())
            if m: best[m.group(2)] = min(best.get(m.group(2), 9e9), float(m.group(1)))
    return best
R['cmp'] = {}
for name, flags in [('debug(opt-level=0)', []), ('release(-O)', ['-O'])]:
    b = passes(flags); R['cmp'][name] = b; print(f'  {name:<20} total {b.get("total", 0):.3f} s   LLVM_passes {b.get("LLVM_passes", 0):.3f} s   type_check_crate {b.get("type_check_crate", 0):.3f} s   link_binary {b.get("link_binary", 0):.3f} s')
save('u123', R)
