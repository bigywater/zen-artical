import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u22'); R = {}
print('== 一:NLL:借用到最后一次使用为止,而不是到作用域结束')
r = tryit('u22a', '''
    fn main() {
        let mut v = vec![1, 2, 3];
        let first = &v[0];
        println!("first = {first}");      // first 的最后一次使用
        v.push(4);                         // 旧的「按作用域」规则会拒绝这一行;NLL 允许
        println!("{:?}", v);
        let r = &mut v;
        r.push(5);
        v.push(6);                         // r 已经不再使用
        println!("{:?}", v);
    }
''', quiet_src=False)
print()
print('== 二:借用在分支里:只在用到它的路径上存活')
r = tryit('u22b', '''
    fn main() {
        let mut s = String::from("a");
        let r = &s;
        let flag = std::env::args().count() > 5;
        if flag { println!("{r}"); }       // 只有这条路径用 r
        else { s.push('b'); }             // 另一条路径里 r 已经死了
        println!("{s}");
    }
''', quiet_src=False)
print()
print('== 三:两阶段借用:v.push(v.len()) 合法,先 &mut v 但尚未激活')
r = tryit('u22c', '''
    fn main() {
        let mut v = vec![1, 2, 3];
        v.push(v.len());
        println!("{:?}", v);
    }
''', quiet_src=False)
r = tryit('u22d', '''
    fn main() {
        let mut v = vec![1, 2, 3];
        let r = &mut v;
        r.push(v.len());     // 先取走了 &mut,再读 v:冲突
    }
''', maxlines=24); R['e_two_phase'] = r['diag'].split('\n')[0]
print()
print('== 四:NLL 不会缩短「有 Drop 的持有者」的借用:Drop 里可能还会用到引用')
r = tryit('u22e', '''
    struct Guard<'a>(&'a mut Vec<i32>);
    impl Drop for Guard<'_> { fn drop(&mut self) { println!("Guard 释放,vec 长度 {}", self.0.len()); } }
    fn main() {
        let mut v = vec![1];
        let g = Guard(&mut v);
        v.push(2);
    }
''', maxlines=30); R['e_drop'] = r['diag'].split('\n')[0]
r = tryit('u22f', '''
    struct Guard<'a>(&'a mut Vec<i32>);
    impl Drop for Guard<'_> { fn drop(&mut self) { println!("Guard 释放,vec 长度 {}", self.0.len()); } }
    fn main() {
        let mut v = vec![1];
        { let _g = Guard(&mut v); }      // 缩小 Guard 的作用域
        v.push(2);
        println!("{:?}", v);
    }
''', quiet_src=False)
print()
print('== 五:rustc 里的 NLL 区域(-Z dump-mir=nll):看借用区域覆盖了哪些 MIR 位置')
f = src_file('u22g', '''
    fn main() {
        let mut v = vec![1];
        let first = &v[0];
        println!("{first}");
        v.push(2);
    }
''')
dd = RS / 'mirdump'; shutil.rmtree(dd, ignore_errors=True)
rc, o, e = sh(['rustc', '--edition=2024', '-Z', 'dump-mir=main', '-Z', f'dump-mir-dir={dd}', '--emit=metadata', str(f), '-o', str(RS / 'bin' / 'x.rmeta')], env=dict(ENVB, RUSTC_BOOTSTRAP='1'))
fs = sorted(p.name for p in dd.glob('*nll*')) if dd.exists() else []; print('  生成的 NLL 相关 MIR 转储文件:', fs[:3], f'(共 {len(fs)} 个)')
if fs:
    t = (dd / fs[0]).read_text().split('\n'); reg = [l.strip() for l in t if l.strip().startswith('| \'?')][:8]
    print('  NLL 区域信息(借用区域 \'?N 覆盖的 MIR 位置)节选:'); print('\n'.join('    ' + l[:150] for l in reg)); R['regions'] = reg
save('u22', R)
