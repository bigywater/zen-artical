import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u125'); R = {}
code = '''
    #[inline(never)] pub fn sum(v: &[i32]) -> i32 { let mut s = 0; for x in v { s += *x; } s }
    #[inline(never)] pub fn square(x: i32) -> i32 { x * x }
    #[inline(never)] pub fn caller(a: i32, b: i32) -> i32 { helper(a) + helper(b) }
    fn helper(x: i32) -> i32 { square_inline(x) + 1 }
    #[inline] fn square_inline(x: i32) -> i32 { x * x }
'''
def ll(level_flags, name):
    f = src_file(name, code); out = RS / 'bin' / f'{name}.ll'; out.unlink(missing_ok=True)
    rc, o, e = sh(['rustc', '--edition=2024', '--crate-type=lib', '--emit=llvm-ir', '-C', 'debuginfo=0', *level_flags, '-o', str(out), str(f)]); return out.read_text()
def fn_body(t, name):
    m = re.search(r'define [^\n]*@\S*' + re.escape(name) + r'\w*\([^\n]*\{\n(.*?)\n\}', t, re.S); return m.group(1) if m else ''
print('== 一:同一个求和函数的 LLVM IR:O0 与 O3。O0 里每个变量都是栈槽(alloca / load / store);O3 变成寄存器值(phi)并向量化')
for name, flags in [('O0', ['-C', 'opt-level=0']), ('O3', ['-C', 'opt-level=3'])]:
    t = ll(flags, 'u125' + name); b = fn_body(t, '3sum'); L = [l for l in b.splitlines() if l.strip() and not l.strip().startswith(';')]
    stats = {'行数': len(L), 'alloca': sum('alloca' in l for l in L), 'load': sum(' load ' in l for l in L), 'store': sum(' store ' in l for l in L), 'phi': sum(' phi ' in l for l in L), '向量类型 <4 x i32>': sum('<4 x i32>' in l for l in L), 'add': sum(re.search(r'\badd\b', l) is not None for l in L)}
    print(f'  {name}:' + '  '.join(f'{k} {v}' for k, v in stats.items())); R['stats_' + name] = stats
    R['ir_' + name] = L[:40]
print('  O3 的 sum 里与向量相关的几行:')
for l in R['ir_O3']:
    if '<4 x i32>' in l or 'vector' in l: print('    ' + l.strip()[:130]); break
print()
print('== 二:O0 的 sum 函数 IR(前 18 行)')
print('\n'.join('    ' + l[:130] for l in R['ir_O0'][:18]))
print()
print('== 三:内联:caller 调用 helper(helper 再调用 square_inline)。O0 时 helper 仍是单独的函数、被 call;O3 时 helper 与 square_inline 都被内联进 caller')
for name, flags in [('O0', ['-C', 'opt-level=0']), ('O3', ['-C', 'opt-level=3'])]:
    t = ll(flags, 'u125i' + name); b = fn_body(t, '6caller'); L = [l for l in b.splitlines() if l.strip() and not l.strip().startswith(';')]
    calls = [re.search(r'@(\S+?)\(', l).group(1) for l in L if ' call ' in l]; short = [re.search(r'\d+([a-z_]+)(?:B\w+)?$', c).group(1) if re.search(r'\d+([a-z_]+)(?:B\w+)?$', c) else c for c in calls]
    print(f'  {name}:caller 的 IR {len(L)} 行,call 指令 {len(calls)} 条:{short}'); R['inl_' + name] = [len(L), short]
print()
print('== 四:优化级别对代码尺寸的影响(--emit=asm,同一个小库;各级别汇编指令条数)')
code5 = code
R['levels'] = {}
for lv in ('0', '1', '2', '3', 's', 'z'):
    f = src_file('u125l', code5); out = RS / 'bin' / 'u125l.s'; out.unlink(missing_ok=True)
    rc, o, e = sh(['rustc', '--edition=2024', '--crate-type=lib', '--emit=asm', '-C', f'opt-level={lv}', '-C', 'debuginfo=0', '-o', str(out), str(f)]); L = out.read_text().splitlines()
    ins = [l for l in L if l.startswith('\t') and not l.startswith(('\t.', '\t;'))]; R['levels'][lv] = len(ins); print(f'  opt-level={lv}:汇编指令 {len(ins):>3} 条')
save('u125', R)
