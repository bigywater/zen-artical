import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u24'); R = {}
print('== 一:只有一个输入引用时,返回的引用自动借自它(省略规则)')
r = tryit('u24a', '''
    fn first_word(s: &str) -> &str { s.split(' ').next().unwrap_or("") }
    fn main() {
        let text = String::from("hello world");
        let w = first_word(&text);
        println!("first_word = {w}");
        drop(text);               // text 被释放之后还用 w 吗?
    }
''', quiet_src=False)
r = tryit('u24b', '''
    fn first_word(s: &str) -> &str { s.split(' ').next().unwrap_or("") }
    fn main() {
        let text = String::from("hello world");
        let w = first_word(&text);
        drop(text);
        println!("{w}");
    }
''', maxlines=26, quiet_src=True); R['e505'] = r['diag'].split('\n')[0]
print()
print('== 二:方法里 &self 与其它引用参数同时存在:返回值借自 self')
r = tryit('u24c', '''
    struct Config { name: String }
    impl Config {
        fn name_or<'a>(&'a self, fallback: &str) -> &'a str { if self.name.is_empty() { "(空)" } else { &self.name } }
        fn pick(&self, _other: &str) -> &str { &self.name }       // 省略规则:返回值借自 &self
    }
    fn main() {
        let c = Config { name: "prod".into() };
        let n;
        {
            let tmp = String::from("临时参数");
            n = c.pick(&tmp);          // tmp 比 n 先死,不影响 n:n 借自 c
        }
        println!("n = {n}");
    }
''', quiet_src=False, flags=('-A', 'unused'))
print()
print('== 三:不能返回指向函数自己拥有的数据的引用')
r = tryit('u24d', '''
    fn make<'a>() -> &'a str {
        let s = String::from("本地");
        s.as_str()
    }
    fn main() { println!("{}", make()); }
''', maxlines=26); R['e515'] = r['diag'].split('\n')[0]
r = tryit('u24e', '''
    fn consume_and_view(s: String) -> &'static str { &s }
    fn main() { println!("{}", consume_and_view("x".into())); }
''', maxlines=26); R['e515b'] = r['diag'].split('\n')[0]
print()
print('== 四:返回借自集合的引用,生命周期绑在集合上,不是绑在查找的 key 上')
r = tryit('u24f', '''
    fn find<'a>(v: &'a [String], key: &str) -> Option<&'a String> { v.iter().find(|s| s.as_str() == key) }
    fn main() {
        let names = vec!["ann".to_string(), "bob".to_string()];
        let found;
        {
            let key = String::from("bob");         // key 在内层块里,先死
            found = find(&names, &key);
        }
        println!("{:?}", found);                    // found 借自 names,没问题
    }
''', quiet_src=False)
r = tryit('u24g', '''
    fn find<'a>(v: &'a [String], key: &str) -> Option<&'a String> { v.iter().find(|s| s.as_str() == key) }
    fn main() {
        let found;
        {
            let names = vec!["ann".to_string(), "bob".to_string()];
            found = find(&names, "bob");
        }
        println!("{:?}", found);
    }
''', maxlines=26); R['e597'] = r['diag'].split('\n')[0]
print()
print('== 五:返回 &\'static:字符串字面量与 static 变量')
r = tryit('u24h', '''
    static NAME: &str = "全局名字";
    fn greeting(formal: bool) -> &'static str { if formal { "您好" } else { "嗨" } }
    fn name() -> &'static str { NAME }
    fn main() {
        let g = { let flag = true; greeting(flag) };     // flag 已经出作用域,g 仍然有效
        println!("{g} {}", name());
    }
''', quiet_src=False)
save('u24', R)
