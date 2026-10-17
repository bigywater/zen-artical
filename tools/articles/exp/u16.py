import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u16'); R = {}
print('== 一:赋值给另一个变量 = 移动;原变量不能再用')
r = tryit('u16a', '''
    fn main() {
        let s1 = String::from("hello");
        let s2 = s1;
        println!("{s2}");
        println!("{s1}");
    }
''', maxlines=30); R['e_move'] = r['diag'].split('\n')[0]
print()
print('== 二:移动的是什么?String 的三个字(指针、长度、容量)被拷贝,堆上的数据不动')
r = tryit('u16b', '''
    fn main() {
        let s1 = String::from("hello");
        let p1 = s1.as_ptr();
        let s2 = s1;                      // 移动
        println!("移动后堆数据地址不变:{}", p1 == s2.as_ptr());
        let s3 = s2.clone();              // 克隆
        println!("克隆得到新的堆缓冲区:{}(地址不同)", s2.as_ptr() != s3.as_ptr());
        println!("size_of::<String>() = {} 字节", std::mem::size_of::<String>());
    }
''', quiet_src=False)
print()
print('== 三:传给函数也是移动;函数可以把所有权还回来')
r = tryit('u16c', '''
    fn takes(s: String) { println!("函数里:{s}"); }       // s 在函数结束时被 drop
    fn gives_back(s: String) -> String { s }
    fn main() {
        let a = String::from("a");
        takes(a);
        // println!("{a}");       // 取消注释会报 E0382
        let b = String::from("b");
        let b = gives_back(b);
        println!("拿回来了:{b}");
    }
''', quiet_src=False)
r = tryit('u16d', '''
    fn takes(s: String) { println!("{s}"); }
    fn main() {
        let a = String::from("a");
        takes(a);
        println!("{a}");
    }
''', maxlines=30, quiet_src=True)
print()
print('== 四:循环里移动;条件移动')
r = tryit('u16e', '''
    fn consume(_s: String) {}
    fn main() {
        let s = String::from("x");
        for _ in 0..2 { consume(s); }
    }
''', maxlines=30); R['e_loop'] = r['diag'].split('\n')[0]
print()
print('== 五:部分移动:从结构体里移走一个字段,其余字段仍可用;被移动的值由新所有者负责 drop')
r = tryit('u16f', '''
    struct D(&'static str);
    impl Drop for D { fn drop(&mut self) { println!("  drop {}", self.0); } }
    struct Pair { a: D, b: D }
    fn main() {
        let p = Pair { a: D("a"), b: D("b") };
        let moved = p.a;                         // 只移走字段 a
        println!("移走 a 之后,p.b 还能用:{}", p.b.0);
        {
            let _inner = moved;                  // 新所有者在这个块结束时 drop
            println!("进入内层块");
        }
        println!("内层块已结束,main 马上结束");
    }
''', quiet_src=False, flags=('-A', 'unused'))
save('u16', R)
