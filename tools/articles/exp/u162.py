import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
import difflib, hashlib
tee('u162'); R = {}
base = RS / 'proj' / 'u162'; shutil.rmtree(base, ignore_errors=True); (base / 'src').mkdir(parents=True)
(base / 'Cargo.toml').write_text('[package]\nname = "fmt"\nversion = "0.1.0"\nedition = "2024"\n')
UGLY = textwrap.dedent('''
    use std::collections::HashMap;use std::fmt;
    use std::io::{self,Read};
    struct Point{x:i32,y:i32}
    impl fmt::Display for Point{fn fmt(&self,f:&mut fmt::Formatter)->fmt::Result{write!(f,"({}, {})",self.x,self.y)}}
    fn long_function_name_with_many_parameters(first_parameter: i32, second_parameter: String, third_parameter: Vec<u8>, fourth: Option<i32>) -> i32 { first_parameter + second_parameter.len() as i32 + third_parameter.len() as i32 + fourth.unwrap_or(0) }
    fn main(){
        let mut m=HashMap::new();m.insert("a",1);
        let v=vec![1,2,3];   let total:i32=v.iter().map(|x|x*2).sum();
        if total>5{println!("big {}",total);}else{println!("small")}
        let p=Point{x:1,y:2};println!("{}",p);
        let _=io::stdin().read(&mut []);let _=long_function_name_with_many_parameters(1,"x".to_string(),vec![1],None);
    }
''')
(base / 'src' / 'main.rs').write_text(UGLY)
print('== 一:rustfmt --check:不改文件,只报告差异并用退出码表示(0 已格式化,1 有差异);CI 里的 cargo fmt --check')
rc, o, e = sh(['rustfmt', '--edition', '2024', '--check', str(base / 'src' / 'main.rs')], env=ENVB); print(f'  退出码 {rc};输出行数 {len(o.splitlines())}'); o = re.sub(r'\x1b\[[0-9;]*m|\x1b\(B', '', o); print('\n'.join('    ' + l.replace(str(RS), '<实验目录>')[:150] for l in o.splitlines()[:14])); R['check'] = [rc, [l.replace(str(RS), '<实验目录>')[:150] for l in o.splitlines()[:14]]]
print()
print('== 二:格式化之后:代码变整齐了,而程序的含义完全不变(编译产物逐字节相同吗?对比汇编)')
def asm_hash(p):
    out = RS / 'bin' / 'u162.s'; sh(['rustc', '--edition=2024', '--crate-type=bin', '--emit=asm', '-C', 'opt-level=2', '-C', 'debuginfo=0', '-o', str(out), str(p)]); t = out.read_text(); t = '\n'.join(l for l in t.splitlines() if not l.strip().startswith(('.file', '.loc', '.section', '.ident', '.cfi')) and 'u162' not in l and '.rs' not in l); return hashlib.sha256(t.encode()).hexdigest()[:12], len(t.splitlines())
before = asm_hash(base / 'src' / 'main.rs'); rc, o, e = sh(['rustfmt', '--edition', '2024', str(base / 'src' / 'main.rs')], env=ENVB); after = asm_hash(base / 'src' / 'main.rs')
print(f'  格式化前 汇编哈希 {before[0]}({before[1]} 行)  格式化后 {after[0]}({after[1]} 行)  相同: {before == after}'); R['asm'] = [before, after, before == after]
fmt1 = (base / 'src' / 'main.rs').read_text(); print(f'  格式化后的代码({len(UGLY.splitlines())} 行 → {len(fmt1.splitlines())} 行):'); print('\n'.join('    ' + l for l in fmt1.splitlines()[:22])); R['formatted'] = fmt1.splitlines()
print()
print('== 三:幂等:对已经格式化的代码再格式化一次,不会有任何变化')
rc, o, e = sh(['rustfmt', '--edition', '2024', str(base / 'src' / 'main.rs')], env=ENVB); fmt2 = (base / 'src' / 'main.rs').read_text(); print(f'  第二次格式化后是否与第一次相同:{fmt1 == fmt2}'); R['idem'] = fmt1 == fmt2
rc, o, e = sh(['rustfmt', '--edition', '2024', '--check', str(base / 'src' / 'main.rs')], env=ENVB); print(f'  再 --check:退出码 {rc}'); R['check2'] = rc
print()
print('== 四:rustfmt.toml:max_width 改变换行;同一函数在 max_width = 40 / 100(默认)/ 140 下的样子')
(base / 'src' / 'main.rs').write_text(UGLY)
sample = 'fn main() { let values = vec![1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000]; let total: i32 = values.iter().map(|x| x * 2).filter(|x| *x > 3000).sum(); println!("total is {}", total); }\n'
R['widths'] = {}
for w in (40, 100, 140):
    f = RS / 'src' / f'u162w{w}.rs'; f.write_text(sample); (RS / 'src' / 'rustfmt.toml').write_text(f'max_width = {w}\n')
    rc, o, e = sh(['rustfmt', '--edition', '2024', '--config-path', str(RS / 'src'), str(f)], env=ENVB); out = f.read_text(); R['widths'][str(w)] = out.splitlines(); print(f'  max_width = {w:<4} → {len(out.splitlines())} 行'); print('\n'.join('      ' + l for l in out.splitlines()[:16]))
print()
print('== 五:#[rustfmt::skip] 让某段代码保持手工排版(例如对齐的矩阵);无效的配置项在稳定版里的行为')
(RS / 'src' / 'rustfmt.toml').unlink(missing_ok=True)
sk = 'fn main() {\n    #[rustfmt::skip]\n    let m = [\n        1,0,0,\n        0,1,0,\n        0,0,1,\n    ];\n    let n = [\n        1,0,0,\n        0,1,0,\n    ];\n}\n'
f = RS / 'src' / 'u162sk.rs'; f.write_text(sk); sh(['rustfmt', '--edition', '2024', str(f)], env=ENVB); print('  格式化后:'); print('\n'.join('    ' + l for l in f.read_text().splitlines())); R['skip'] = f.read_text().splitlines()
(RS / 'src' / 'rustfmt.toml').write_text('imports_granularity = "Crate"\nmax_width = 90\n'); f.write_text('use std::fmt;\nfn main(){}\n')
rc, o, e = sh(['rustfmt', '--edition', '2024', '--config-path', str(RS / 'src'), str(f)], env=ENVB); print('  在 rustfmt.toml 里写 nightly 才有的选项 imports_granularity:'); print('    ' + (o + e).strip().replace('\n', '\n    ').replace(str(RS), '<实验目录>')[:300]); R['unstable'] = (o + e).strip().replace(str(RS), '<实验目录>')[:300]
(RS / 'src' / 'rustfmt.toml').unlink(missing_ok=True)
save('u162', R)
