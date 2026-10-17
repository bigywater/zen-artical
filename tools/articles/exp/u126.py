import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u126'); R = {}
def mono(name, code, flags=()):
    f = src_file(name, code); rc, o, e = sh(['rustc', '--edition=2024', '--crate-type=lib', '-C', 'opt-level=0', '-C', 'debuginfo=0', '--emit=metadata', '-Z', 'print-mono-items=lazy', '-o', str(RS / 'bin' / f'{name}.rmeta'), *flags, str(f)], env=dict(ENVB, RUSTC_BOOTSTRAP='1')); return (o + e).splitlines()
print('== 一:-Z print-mono-items:rustc 自己列出「单态化出来的每一个函数实例」')
code = '''
    pub fn largest<T: PartialOrd + Copy>(a: T, b: T) -> T { if a > b { a } else { b } }
    pub fn use_all() -> (i32, f64, u8, char) { (largest(1, 2), largest(1.5, 0.5), largest(3u8, 4u8), largest('a', 'b')) }
'''
f = src_file('u126a', code); rc, o, e = sh(['rustc', '--edition=2024', '--crate-type=lib', '-C', 'opt-level=0', '-C', 'debuginfo=0', '-Z', 'print-mono-items=yes', '--emit=obj', '-o', str(RS / 'bin' / 'u126a.o'), str(f)], env=dict(ENVB, RUSTC_BOOTSTRAP='1'))
L = [l for l in (o + e).splitlines() if l.startswith('MONO_ITEM')]
for l in L: print('  ' + l[:150])
R['items'] = L; print(f'  共 {len(L)} 个单态化实例:largest 被实例化了 {sum("largest" in l for l in L)} 次(i32、f64、u8、char 各一份)')
print()
print('== 二:每个泛型实例是独立的机器码:取 largest::<i32> 与 largest::<f64> 的汇编(-O),比较指令')
code = '''
    #[inline(never)] pub fn largest<T: PartialOrd + Copy>(a: T, b: T) -> T { if a > b { a } else { b } }
    #[unsafe(no_mangle)] pub fn ci(a: i32, b: i32) -> i32 { largest(a, b) }
    #[unsafe(no_mangle)] pub fn cf(a: f64, b: f64) -> f64 { largest(a, b) }
    #[unsafe(no_mangle)] pub fn cu(a: u32, b: u32) -> u32 { largest(a, b) }
'''
_, txt = asm_of('u126b', code, None)
def body_of(label):
    m = re.search(r'^' + re.escape(label) + r':\n(.*?)(?=^\S+:|\Z)', txt, re.S | re.M)
    return [re.sub(r'\s+', ' ', l.strip()) for l in (m.group(1) if m else '').splitlines() if l.strip() and not l.strip().startswith(('.', ';', 'L'))]
labels = re.findall(r'^(_[^\s:]*largest[^\s:]*):', txt, re.M)
R['bodies'] = {}
for lab in labels:
    kind = {'l': 'i32', 'd': 'f64', 'm': 'u32'}.get(re.search(r'largest(\w)E', lab).group(1), '?'); bd = body_of(lab)
    print(f'  largest::<{kind}>({len(bd)} 条指令):{" ; ".join(bd)}'); R['bodies'][kind] = bd
R['syms'] = len(labels); print(f'  汇编里 largest 的符号:{len(labels)} 个(i32、f64、u32 各一份;u32 与 i32 比较指令不同,所以没有被合并)')
print()
print('== 三:相同机器码的实例会被合并:i32 与 u32 的加法 —— LLVM 把完全相同的函数合并成别名(_a = _b)')
code = '''
    #[inline(never)] pub fn add_pair<T: std::ops::Add<Output = T> + Copy>(a: T, b: T) -> T { a + b }
    #[unsafe(no_mangle)] pub fn add_i32(a: i32, b: i32) -> i32 { add_pair(a, b) }
    #[unsafe(no_mangle)] pub fn add_u32(a: u32, b: u32) -> u32 { add_pair(a, b) }
    #[unsafe(no_mangle)] pub fn add_f32(a: f32, b: f32) -> f32 { add_pair(a, b) }
'''
f = src_file('u126c', code); out = RS / 'bin' / 'u126c.s'; sh(['rustc', '--edition=2024', '--crate-type=lib', '--emit=asm', '-C', 'opt-level=3', '-C', 'debuginfo=0', '-o', str(out), str(f)]); t = out.read_text()
alias = re.findall(r'^(_\w+) = (_\w+)', t, re.M); defs = re.findall(r'^(_[\w$.]+):', t, re.M)
print(f'  汇编里别名(_x = _y):{[(a, b) for a, b in alias if "add" in a or "add" in b][:4]}'); print(f'  实际定义的函数标签:{[d for d in defs if "add" in d][:6]}'); R['alias'] = [[a, b] for a, b in alias if 'add' in a or 'add' in b][:4]; R['defs'] = [d for d in defs if 'add' in d][:6]
print()
print('== 四:代码体积随实例数增长:对同一个泛型函数实例化 1 / 4 / 16 个类型(--emit=obj,-O),与 &dyn 版本对比')
types = ['u8', 'i8', 'u16', 'i16', 'u32', 'i32', 'u64', 'i64', 'u128', 'i128', 'usize', 'isize', 'f32', 'f64', 'char', 'bool']
def objsize(name, src):
    f = src_file(name, src); out = RS / 'obj' / f'{name}.o'; out.parent.mkdir(exist_ok=True); sh(['rustc', '--edition=2024', '--crate-type=lib', '--emit=obj', '-C', 'opt-level=3', '-C', 'codegen-units=1', '-C', 'debuginfo=0', '-o', str(out), str(f)]); return out.stat().st_size
rows = []
print(f'  {"实例数":>6} {"泛型版 .o 字节":>16} {"&dyn 版 .o 字节":>16}')
for n in (1, 4, 16):
    calls = ' '.join(f'#[unsafe(no_mangle)] pub fn g{i}(x: {t}) -> String {{ describe(x) }}' for i, t in enumerate(types[:n]))
    callsd = ' '.join(f'#[unsafe(no_mangle)] pub fn g{i}(x: {t}) -> String {{ describe_dyn(&x) }}' for i, t in enumerate(types[:n]))
    gen = f'#[inline(never)] pub fn describe<T: std::fmt::Debug>(x: T) -> String {{ format!("<{{:?}}>", x) }} {calls}'
    dyn = f'#[inline(never)] pub fn describe_dyn(x: &dyn std::fmt::Debug) -> String {{ format!("<{{:?}}>", x) }} {callsd}'
    a, b = objsize(f'u126g{n}', gen), objsize(f'u126d{n}', dyn); rows.append([n, a, b]); print(f'  {n:>6} {a:>16,} {b:>16,}')
R['sizes'] = rows
save('u126', R)
