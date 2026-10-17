import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u161'); R = {}
def lint_names(o): return re.findall(r'rust-clippy/[^#]*/index\.html#([a-z_0-9]+)', o)
base = RS / 'proj' / 'u161'; shutil.rmtree(base, ignore_errors=True); (base / 'src').mkdir(parents=True)
(base / 'Cargo.toml').write_text('[package]\nname = "lint"\nversion = "0.1.0"\nedition = "2024"\n')
SRC = textwrap.dedent('''
    pub fn sum_first(v: &Vec<i32>) -> i32 {                    // ptr_arg:参数应该是 &[i32]
        let mut s = 0;
        for i in 0..v.len() { s += v[i]; }                      // needless_range_loop
        return s;                                               // needless_return
    }
    pub fn is_empty_len(v: &[u8]) -> bool { v.len() == 0 }      // len_zero
    pub fn flag(b: bool) -> i32 { if b == true { 1 } else { 0 } }  // bool_comparison + bool_to_int_with_if
    pub fn double(o: Option<i32>) -> Option<i32> { match o { Some(x) => Some(x * 2), None => None } }   // manual_map
    pub fn copy_clone(x: i32) -> i32 { x.clone() }              // clone_on_copy
    pub fn nested(a: bool, b: bool) -> i32 { if a { if b { 1 } else { 0 } } else { 0 } }   // collapsible_if? (含 else 时不适用)
    pub fn same(x: i32) -> bool { x == x }                      // eq_op:两边相同(deny 级别)
    pub fn absurd(x: u32) -> bool { x < 0 }                     // absurd_extreme_comparisons:无符号数永远不小于 0(deny 级别)
    pub fn st(s: &String) -> usize { s.len() }                  // ptr_arg:应为 &str
''')
(base / 'src' / 'lib.rs').write_text(SRC)
def clippy(args=(), env=None):
    rc, o, e = sh(['cargo', 'clippy', '--quiet', *args], cwd=base, env=env or ENVB, timeout=600); return rc, o + e
print('== 一:cargo clippy 的默认输出:每个警告带有 lint 名、所属的组与修改建议(默认启用 clippy::all:correctness、suspicious、style、complexity、perf)')
rc, o = clippy(); L = o.splitlines()
lints = re.findall(r'(warning|error): (.*)\n\s+--> src/lib.rs:(\d+):', o)
names = lint_names(o); groups = {}
for m in re.finditer(r'(warning|error): .*\n.*\n(?:.*\n)*?\s+= (?:help|note): .*clippy/.*#([a-z_]+)', o): pass
print(f'  退出码 {rc};共 {len(lints)} 条诊断(clippy 的 lint {len(set(names))} 个)'); print('  触发的 lint:', sorted(set(names))); R['rc'] = rc; R['names'] = sorted(set(names)); R['diag_n'] = len(lints)
print('  前几条完整诊断:')
blocks = o.split('\n\n'); [print('\n'.join('    ' + l.replace(str(RS), '<实验目录>') for l in b.splitlines())) for b in blocks[:3]]; R['blocks'] = [b.replace(str(RS), '<实验目录>') for b in blocks[:3]]
print()
print('== 二:有些 lint 默认就是 deny(错误):x == x 与 u32 < 0 让 cargo clippy 失败,其余是警告')
errs = [l for l in o.splitlines() if l.startswith('error') and 'could not compile' not in l]; deny = re.findall(r'`#\[deny\(clippy::([a-z_]+)\)\]`', o); warns = [l for l in o.splitlines() if l.startswith('warning') and 'generated' not in l]; print(f'  error {len(errs)} 条:{errs[:3]};deny 级别的 lint:{deny};cargo clippy 退出码 {rc}'); print(f'  warning 行 {len(warns)} 条'); R['err'] = errs[:3]; R['deny'] = deny; R['warn_n'] = len(warns)
print()
print('== 三:lint 组与等级:同一份代码在不同配置下的诊断数 —— 默认 / -W clippy::pedantic / -A clippy::all')
for label, args in [('默认', []), ('-W clippy::pedantic', ['--', '-W', 'clippy::pedantic']), ('-A clippy::all(全部允许)', ['--', '-A', 'clippy::all'])]:
    rc2, o2 = clippy(args); n = len(re.findall(r'(?:warning|error): .*\n\s+--> src/lib.rs', o2)); ns = sorted(set(lint_names(o2))); print(f'  {label:<28} 诊断 {n} 条;lint 数 {len(ns)};退出码 {rc2}'); R.setdefault('levels', {})[label] = [n, len(ns), rc2]
rc2, o2 = clippy(['--', '-W', 'clippy::pedantic']); extra = sorted(set(lint_names(o2)) - set(R['names'])); print('  pedantic 额外触发的 lint:', extra); R['pedantic_extra'] = extra
print()
print('== 四:在代码里关闭某条 lint:#[allow(clippy::...)];以及 -D warnings 让 CI 把所有警告当错误')
(base / 'src' / 'lib.rs').write_text(SRC.replace('pub fn same', '#[allow(clippy::eq_op)]\n    pub fn same').replace('pub fn absurd', '#[allow(clippy::absurd_extreme_comparisons)]\n    pub fn absurd').replace('pub fn is_empty_len', '#[allow(clippy::len_zero)]\n    pub fn is_empty_len'))
rc3, o3 = clippy(); ns3 = sorted(set(lint_names(o3))); print(f'  加了 #[allow] 后退出码 {rc3};剩下的 lint:{ns3}'); R['after_allow'] = [rc3, ns3]
rc4, o4 = clippy(['--', '-D', 'warnings']); print(f'  再加 -D warnings:退出码 {rc4}(警告变成错误,CI 会失败)'); R['dw'] = rc4
print()
print('== 五:cargo clippy --fix:自动应用「machine-applicable」的建议;看修复前后的代码差别')
(base / 'src' / 'lib.rs').write_text(SRC.replace('x == x', 'true').replace('x < 0', 'false'))
before = (base / 'src' / 'lib.rs').read_text()
rc5, o5, e5 = sh(['cargo', 'clippy', '--fix', '--allow-dirty', '--allow-no-vcs', '--quiet'], cwd=base, env=ENVB, timeout=600)
after = (base / 'src' / 'lib.rs').read_text(); import difflib
d = [l for l in difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm='', n=0) if not l.startswith(('---', '+++', '@@'))]; print(f'  --fix 退出码 {rc5};修改了 {len([l for l in d if l.startswith("+")])} 行:'); print('\n'.join('    ' + l for l in d)); R['fix'] = d
rc6, o6 = clippy(); R['after_fix'] = sorted(set(lint_names(o6))); print(f'  修复后再跑 clippy:剩下的 lint {R["after_fix"]}')
save('u161', R)
