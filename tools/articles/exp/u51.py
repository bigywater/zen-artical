import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u51'); R = {}
print('== 一:Display 面向用户、Debug 面向开发者;{} 需要 Display,{:?} 需要 Debug')
r = tryit('u51a', '''
    #[derive(Debug)] struct P { x: i32, y: i32 }
    fn main() {
        let p = P { x: 1, y: 2 };
        println!("{:?}", p);
        println!("{}", p);
    }
''', maxlines=30); R['e277'] = r['diag'].split('\n')[0]
print()
print('== 二:同一个值的 Display 与 Debug 差别')
r = tryit('u51b', '''
    fn main() {
        println!("字符串   Display: {}   Debug: {:?}", "a\\"b\\n", "a\\"b\\n");
        println!("字符     Display: {}   Debug: {:?}", '\\'', '\\'');
        println!("浮点     Display: {}   Debug: {:?}", 1.0f64, 1.0f64);
        println!("浮点     Display: {}   Debug: {:?}", 1e21f64, 1e21f64);
        println!("Option   Debug: {:?}", Some("x"));
        println!("Vec      Debug: {:?}", vec![Some(1), None]);
        println!("元组     Debug: {:?}", (1, "a", 2.5));
        println!("{{:#?}} 分行缩进:\\n{:#?}", (1, vec![Some("a")]));
    }
''', quiet_src=False)
print()
print('== 三:格式化说明符:宽度、对齐、填充、精度、符号、进制')
r = tryit('u51c', '''
    fn main() {
        println!("[{:8}] [{:<8}] [{:>8}] [{:^8}] [{:*^8}] [{:->8}]", "ab", "ab", "ab", "ab", "ab", "ab");
        println!("[{:8}] [{:<8}] [{:08}] [{:+}] [{:+08.2}]", 42, 42, 42, 42, 3.14159);
        println!("[{:.2}] [{:8.3}] [{:<8.1}] [{:e}] [{:.1e}]", 3.14159, 3.14159, 3.14159, 1234.5, 1234.5);
        println!("[{:x}] [{:X}] [{:#x}] [{:#010x}] [{:b}] [{:#b}] [{:o}]", 255, 255, 255, 255, 5, 5, 8);
        let w = 6; let p = 2;
        println!("[{:w$.p$}] [{:>1$}] [{:.*}]", 2.71828, 7, 3, 1.23456);
        println!("位置参数 {0} {1} {0},命名参数 {name}", "a", "b", name = "n");
    }
''', quiet_src=False)
print()
print('== 四:自定义 Display 时,宽度与对齐默认被忽略(除非用 f.pad);Debug 用 debug_struct 手写')
r = tryit('u51d', '''
    use std::fmt;
    struct A(&'static str); struct B(&'static str);
    impl fmt::Display for A { fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result { write!(f, "{}", self.0) } }          // write!:宽度被忽略
    impl fmt::Display for B { fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result { f.pad(self.0) } }                      // f.pad:遵守宽度与对齐
    struct Secret { user: &'static str, pass: &'static str }
    impl fmt::Debug for Secret { fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result { f.debug_struct("Secret").field("user", &self.user).field("pass", &"***").finish() } }
    fn main() {
        println!("write!  实现:[{:>6}] [{:<6}]", A("ab"), A("ab"));
        println!("f.pad   实现:[{:>6}] [{:<6}]", B("ab"), B("ab"));
        println!("{:?}", Secret { user: "ann", pass: "hunter2" });
        println!("{:#?}", Secret { user: "ann", pass: "hunter2" });
    }
''', quiet_src=False, flags=('-A', 'dead_code'))
save('u51', R)
