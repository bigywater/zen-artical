import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u14'); R = {}
print('== 一:模块、可见性:默认私有,pub 才对外;私有项在模块外访问报错')
r = tryit('u14a', '''
    mod bank {
        pub struct Account { pub owner: String, balance: i64 }
        impl Account {
            pub fn new(owner: &str) -> Self { Account { owner: owner.into(), balance: 0 } }
            pub fn deposit(&mut self, n: i64) { self.balance += n; }
            pub fn balance(&self) -> i64 { self.balance }
        }
        fn audit() {}            // 私有函数
    }
    fn main() {
        let mut a = bank::Account::new("ann");
        a.deposit(50);
        println!("{} 的余额 {}", a.owner, a.balance());
        println!("{}", a.balance);       // 私有字段
        bank::audit();                   // 私有函数
    }
''', maxlines=40); R['errs'] = re.findall(r'error\[(E\d+)\]', r['diag'])
print()
print('== 二:pub(crate)、pub(super)、pub(in path) 与 use 路径')
r = tryit('u14b', '''
    mod outer {
        pub mod inner {
            pub(crate) fn crate_wide() -> &'static str { "pub(crate):整个 crate 可见" }
            pub(super) fn parent_only() -> &'static str { "pub(super):只有父模块 outer 可见" }
            pub fn everyone() -> &'static str { "pub:到处可见" }
        }
        pub fn call_parent_only() -> &'static str { inner::parent_only() }
    }
    use outer::inner::{self, everyone};
    fn main() {
        println!("{}", inner::crate_wide());
        println!("{}", everyone());
        println!("{}", outer::call_parent_only());
    }
''', quiet_src=False)
r = tryit('u14c', '''
    mod outer { pub mod inner { pub(super) fn parent_only() {} } }
    fn main() { outer::inner::parent_only(); }
''', maxlines=16); R['e_super'] = r['diag'].split('\n')[0]
print()
print('== 三:同一个 crate 内,子模块可以访问祖先模块的私有项;反过来不行')
r = tryit('u14d', '''
    mod parent {
        fn secret() -> &'static str { "父模块的私有函数" }
        pub mod child {
            pub fn peek() -> &'static str { super::secret() }   // 子模块访问祖先的私有项
            fn hidden() -> &'static str { "子模块的私有函数" }
        }
        pub fn call_child_private() -> &'static str { child::hidden() }   // 祖先访问子模块的私有项
    }
    fn main() { println!("{}", parent::child::peek()); println!("{}", parent::call_child_private()); }
''', maxlines=24); R['e_child'] = r['diag'].split('\n')[0]
print()
print('== 四:文件模块:mod foo; 对应 foo.rs 或 foo/mod.rs;用 cargo 项目验证目录结构')
d = proj('modtest', {'src/main.rs': 'mod util;\nmod net;\nfn main() { println!("{}", util::hello()); println!("{}", net::client::ping()); }\n',
                       'src/util.rs': 'pub fn hello() -> &\'static str { "来自 util.rs" }\n',
                       'src/net/mod.rs': 'pub mod client;\n', 'src/net/client.rs': 'pub fn ping() -> &\'static str { "来自 net/client.rs" }\n'})
shutil.rmtree(TG, ignore_errors=True); rc, o = cargo(['run', '-q'], d)
print('  目录:src/main.rs  src/util.rs  src/net/mod.rs  src/net/client.rs'); print('  $ cargo run -q'); print('\n'.join('    ' + l for l in o.splitlines()))
d2 = proj('modmissing', {'src/main.rs': 'mod nothere;\nfn main() {}\n'}); rc, o = cargo(['build'], d2)
print('  mod nothere; 但没有 nothere.rs:'); print('\n'.join('    ' + l for l in o.splitlines()[:10])); R['e_missing'] = [l for l in o.splitlines() if l.startswith('error')][:1]
save('u14', R)
