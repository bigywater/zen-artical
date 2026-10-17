import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u124'); R = {}
def mir_of(name, code, fn, flags=()):
    f = src_file(name, code); out = RS / 'bin' / f'{name}.mir'; out.unlink(missing_ok=True)
    rc, o, e = sh(['rustc', '--edition=2024', '--crate-type=lib', '--emit=mir', *flags, '-C', 'debuginfo=0', '-o', str(out), str(f)])
    txt = out.read_text() if out.exists() else (o + e); L = txt.splitlines(); st = [i for i, l in enumerate(L) if re.match(rf'fn {fn}\(', l)]
    if not st: return []
    i = st[0]; j = i
    while j < len(L) and L[j] != '}': j += 1
    return [l for l in L[i:j + 1] if l.strip() and not l.strip().startswith('//')]
print('== 一:一个带分支的函数的 MIR:基本块(bb)、局部变量(_N)、终结符(switchInt / return)')
code = '''
    pub fn pick(x: i32) -> i32 { if x > 10 { x * 2 } else { x + 1 } }
'''
m = mir_of('u124a', code, 'pick', flags=('-Z', 'mir-opt-level=0')) if False else None
rc, o, e = sh(['rustc', '--edition=2024', '--crate-type=lib', '--emit=mir', '-C', 'debuginfo=0', '-o', str(RS / 'bin' / 'u124a.mir'), str(src_file('u124a', code))], env=dict(ENVB, RUSTC_BOOTSTRAP='1'))
txt = (RS / 'bin' / 'u124a.mir').read_text(); L = txt.splitlines(); i = [k for k, l in enumerate(L) if l.startswith('fn pick(')][0]; j = i
while L[j] != '}': j += 1
seg = [l for l in L[i:j + 1] if l.strip() and not l.strip().startswith('//')]
print('  源码:  pub fn pick(x: i32) -> i32 { if x > 10 { x * 2 } else { x + 1 } }'); print('  MIR:'); print('\n'.join('    ' + l for l in seg)); R['pick'] = seg
bbs = len([l for l in seg if re.match(r'\s*bb\d+', l)]); print(f'  基本块数 {bbs};switchInt 出现 {sum("switchInt" in l for l in seg)} 次;checked 溢出断言 assert 出现 {sum("assert(" in l for l in seg)} 次(debug 构建的溢出检查是 MIR 里的 assert)'); R['pick_stats'] = [bbs, sum('switchInt' in l for l in seg), sum('assert(' in l for l in seg)]
print()
print('== 二:Drop 与所有权在 MIR 里是显式的:drop(_N) 终结符,还有 unwind 路径(panic 时的清理)')
code = '''
    pub fn make(n: usize) -> usize { let s = String::from("hello"); let t = s.len() + n; t }
'''
rc, o, e = sh(['rustc', '--edition=2024', '--crate-type=lib', '--emit=mir', '-C', 'debuginfo=0', '-o', str(RS / 'bin' / 'u124b.mir'), str(src_file('u124b', code))], env=dict(ENVB, RUSTC_BOOTSTRAP='1'))
L = (RS / 'bin' / 'u124b.mir').read_text().splitlines(); i = [k for k, l in enumerate(L) if l.startswith('fn make(')][0]; j = i
while L[j] != '}': j += 1
seg = [l for l in L[i:j + 1] if l.strip() and not l.strip().startswith('//')]
print('  源码:  pub fn make(n: usize) -> usize { let s = String::from("hello"); let t = s.len() + n; t }'); print('\n'.join('    ' + l for l in seg)); R['make'] = seg
print(f'  drop 终结符 {sum("drop(" in l for l in seg)} 次;unwind 路径(\"unwind\" 出现)  {sum("unwind" in l for l in seg)} 次;cleanup 块 {sum("cleanup" in l for l in seg)} 个'); R['make_stats'] = [sum('drop(' in l for l in seg), sum('unwind' in l for l in seg), sum('cleanup' in l for l in seg)]
print()
print('== 三:MIR 优化:常量折叠与死代码消除(同一函数,mir-opt-level=0 对比默认)')
code = '''
    pub fn folded() -> i32 { let a = 2 + 3; let b = a * 4; let unused = 99; b }
'''
for lvl in ('0', '2'):
    rc, o, e = sh(['rustc', '--edition=2024', '--crate-type=lib', '--emit=mir', '-C', 'debuginfo=0', '-C', 'opt-level=0', '-Z', f'mir-opt-level={lvl}', '-o', str(RS / 'bin' / f'u124c{lvl}.mir'), str(src_file('u124c', code))], env=dict(ENVB, RUSTC_BOOTSTRAP='1'))
    L = (RS / 'bin' / f'u124c{lvl}.mir').read_text().splitlines(); i = [k for k, l in enumerate(L) if l.startswith('fn folded(')][0]; j = i
    while L[j] != '}': j += 1
    seg = [l for l in L[i:j + 1] if l.strip() and not l.strip().startswith('//')]
    print(f'  mir-opt-level={lvl}:{len(seg)} 行'); print('\n'.join('    ' + l for l in seg)); R['fold_' + lvl] = seg
print()
print('== 四:借用错误的报告:编译器指出三个位置(不可变借用发生处、可变借用发生处、不可变借用之后被使用处)')
r = tryit('u124d', '''
    fn main() { let mut v = vec![1, 2, 3]; let first = &v[0]; v.push(4); println!("{}", first); }
''', maxlines=24); R['e0502'] = r['diag']
save('u124', R)
