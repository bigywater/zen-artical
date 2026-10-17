import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u47'); R = {}
print('== 一:孤儿规则:trait 与类型至少有一个是本 crate 的(六种情形各编译一次)')
cases = [
    ('外部 trait + 外部类型(Display for Vec<u8>)', 'use std::fmt; impl fmt::Display for Vec<u8> { fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result { write!(f, "v") } } fn main() {}'),
    ('本地 trait + 外部类型(MyTr for Vec<u8>)', 'trait MyTr { fn hi(&self) -> u8; } impl MyTr for Vec<u8> { fn hi(&self) -> u8 { self.len() as u8 } } fn main() { println!("{}", vec![1u8, 2].hi()); }'),
    ('外部 trait + 本地类型(Display for Local)', 'use std::fmt; struct Local; impl fmt::Display for Local { fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result { write!(f, "L") } } fn main() { println!("{}", Local); }'),
    ('外部 trait + 外部类型,但 trait 的类型参数是本地类型(From<Local> for Vec<u8>)', 'struct Local(u8); impl From<Local> for Vec<u8> { fn from(l: Local) -> Vec<u8> { vec![l.0] } } fn main() { let v: Vec<u8> = Local(7).into(); println!("{:?}", v); }'),
    ('外部 trait + Box<本地类型>(Box 是 #[fundamental])', 'use std::fmt; struct Local; impl fmt::Display for Box<Local> { fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result { write!(f, "boxed") } } fn main() { println!("{}", Box::new(Local)); }'),
    ('外部 trait + Vec<本地类型>(Vec 不是 fundamental)', 'use std::fmt; struct Local; impl fmt::Display for Vec<Local> { fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result { write!(f, "v") } } fn main() {}'),
]
res = []
for i, (name, code) in enumerate(cases):
    ok, diag, b, _ = rustc(f'u47c{i}', code)
    first = [l for l in diag.split('\n') if l.startswith('error')][:1]
    res.append((name, ok)); print(f'  {name}\n      → ' + ('编译通过' if ok else '失败:' + (first[0] if first else diag[:80])))
R['cases'] = res
print()
print('== 二:一致性(coherence):同一个类型对同一个 trait 的实现不能重叠;泛型的 blanket 实现与具体实现冲突')
r = tryit('u47a', '''
    trait Describe { fn d(&self) -> String; }
    impl<T: std::fmt::Display> Describe for T { fn d(&self) -> String { format!("显示:{}", self) } }
    impl Describe for i32 { fn d(&self) -> String { "整数".into() } }
    fn main() {}
''', maxlines=26); R['e119'] = r['diag'].split('\n')[0]
print()
print('== 三:为什么连「现在不满足 Display」的类型也不能再写一个具体实现:上游将来可能加上它')
r = tryit('u47b', '''
    trait Describe { fn d(&self) -> String; }
    impl<T: std::fmt::Display> Describe for T { fn d(&self) -> String { format!("显示:{}", self) } }
    impl Describe for Vec<u8> { fn d(&self) -> String { "字节向量".into() } }
    fn main() {}
''', maxlines=30); R['e119b'] = [l for l in r['diag'].split('\n') if 'upstream' in l or l.startswith('error')][:2]
r = tryit('u47c', '''
    trait Describe { fn d(&self) -> String; }
    impl<T: std::fmt::Display> Describe for T { fn d(&self) -> String { format!("显示:{}", self) } }
    struct Mine;                                            // 本地类型:上游永远不会给它实现 Display
    impl Describe for Mine { fn d(&self) -> String { "我的类型".into() } }
    fn main() { println!("{} {}", Mine.d(), 5.d()); }
''', quiet_src=False)
print()
print('== 四:绕开孤儿规则的办法:newtype 包装,或者自己定义 trait')
r = tryit('u47d', '''
    use std::fmt;
    struct Bytes(Vec<u8>);                                                      // newtype
    impl fmt::Display for Bytes { fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result { write!(f, "{} 字节", self.0.len()) } }
    trait Hex { fn hex(&self) -> String; }                                      // 自己的 trait,可以为外部类型实现
    impl Hex for Vec<u8> { fn hex(&self) -> String { self.iter().map(|b| format!("{b:02x}")).collect() } }
    fn main() { println!("{} / {}", Bytes(vec![1, 2, 3]), vec![0xde, 0xad].hex()); }
''', quiet_src=False)
save('u47', R)
