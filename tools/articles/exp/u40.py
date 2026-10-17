import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u40'); R = {}
print('== 一:单态化:同一个泛型函数,每用一种具体类型就生成一份机器码(数符号)')
code = '''
    use std::fmt::Display;
    #[inline(never)] pub fn describe<T: Display + Copy>(x: T) -> String { let s = x.to_string(); format!("<{}:{}>", s, s.len()) }
    #[unsafe(no_mangle)] pub fn use_types(a: u8, b: i16, c: i32, d: i64, e: f32, f: f64, g: char, h: &str) -> usize {
        describe(a).len() + describe(b).len() + describe(c).len() + describe(d).len() + describe(e).len() + describe(f).len() + describe(g).len() + describe(h).len()
    }
'''
_, txt = asm_of('u40a', code, None)
syms = re.findall(r'^(__R[^\s:]*describe[^\s:]*):', txt, re.M)
print(f'  describe 在 8 种类型上使用,汇编里生成的 describe 函数符号:{len(syms)} 个')
for sy in syms: print('   ', sy)
R['n_syms'] = len(syms)
print()
print('== 二:代码体积随不同类型的个数增长(--emit=obj,-O),与用 &dyn 的版本对比')
def obj_size(name, src):
    f = src_file(name, src); out = RS / 'obj' / f'{name}.o'; out.parent.mkdir(exist_ok=True)
    rc, o, e = sh(['rustc', '--edition=2024', '--crate-type=lib', '--emit=obj', '-O', '-C', 'debuginfo=0', '-C', 'codegen-units=1', str(f), '-o', str(out)])
    return out.stat().st_size if out.exists() else -1, e
types = ['u8', 'i16', 'i32', 'i64', 'u16', 'u32', 'u64', 'i8']
rows = []
print(f'  {"不同类型数":>8} {"泛型版 .o 字节":>16} {"&dyn 版 .o 字节":>16}')
for n in (1, 2, 4, 8):
    calls = ' + '.join(f'describe(0 as {t}).len()' for t in types[:n]); calls_dyn = ' + '.join(f'describe_dyn(&(0 as {t})).len()' for t in types[:n])
    gen = f'''
        use std::fmt::Display;
        #[inline(never)] pub fn describe<T: Display + Copy>(x: T) -> String {{ let s = x.to_string(); format!("<{{}}:{{}}>", s, s.len()) }}
        #[unsafe(no_mangle)] pub fn go() -> usize {{ {calls} }}
    '''
    dyn = f'''
        use std::fmt::Display;
        #[inline(never)] pub fn describe_dyn(x: &dyn Display) -> String {{ let s = x.to_string(); format!("<{{}}:{{}}>", s, s.len()) }}
        #[unsafe(no_mangle)] pub fn go() -> usize {{ {calls_dyn} }}
    '''
    a, ea = obj_size(f'u40g{n}', gen); b, eb = obj_size(f'u40d{n}', dyn)
    rows.append((n, a, b)); print(f'  {n:>8} {a:>16,} {b:>16,}')
R['sizes'] = rows
print()
print('== 三:编译时间也随之增长(rustc -O,每个配置取 3 次中位数)')
import statistics
def tm(name, src, k=3):
    ts = []
    for _ in range(k):
        t0 = time.perf_counter(); f = src_file(name, src); sh(['rustc', '--edition=2024', '--crate-type=lib', '--emit=obj', '-O', '-C', 'codegen-units=1', str(f), '-o', str(RS / 'obj' / f'{name}.o')]); ts.append(time.perf_counter() - t0)
    return statistics.median(ts)
tg1 = tm('u40t1', open(RS / 'src' / 'u40g1.rs').read()); tg8 = tm('u40t8', open(RS / 'src' / 'u40g8.rs').read()); td8 = tm('u40td8', open(RS / 'src' / 'u40d8.rs').read())
print(f'  泛型版 1 种类型:{tg1*1000:.0f} ms;泛型版 8 种类型:{tg8*1000:.0f} ms;&dyn 版 8 种类型:{td8*1000:.0f} ms'); R['times'] = (tg1, tg8, td8)
save('u40', R)
