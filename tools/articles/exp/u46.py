import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u46'); R = {}
print('== 一:只实现 Iterator 的 next,就免费得到几十个默认方法')
r = tryit('u46a', '''
    struct Countdown(u32);
    impl Iterator for Countdown {
        type Item = u32;
        fn next(&mut self) -> Option<u32> { if self.0 == 0 { None } else { self.0 -= 1; Some(self.0 + 1) } }
    }
    fn main() {
        println!("collect:{:?}", Countdown(5).collect::<Vec<_>>());
        println!("map + filter + sum:{}", Countdown(10).filter(|n| n % 2 == 0).map(|n| n * n).sum::<u32>());
        println!("zip:{:?}", Countdown(3).zip(Countdown(3).map(|n| n * 10)).collect::<Vec<_>>());
        println!("max:{:?},min:{:?},count:{},last:{:?}", Countdown(7).max(), Countdown(7).min(), Countdown(7).count(), Countdown(7).last());
        println!("fold:{},any:{},all:{},position:{:?}", Countdown(4).fold(0, |a, b| a + b), Countdown(4).any(|x| x == 3), Countdown(4).all(|x| x > 0), Countdown(9).position(|x| x == 5));
        println!("take_while + skip + step_by:{:?}", Countdown(20).skip(2).step_by(4).take_while(|&x| x > 3).collect::<Vec<_>>());
    }
''', quiet_src=False)
print()
print('== 二:实现者可以覆盖默认方法(为了更高效或更合适的语义);PartialEq 只需要 eq,ne 是默认的')
r = tryit('u46b', '''
    struct Slow { left: u32, calls: u32 }
    struct Fast { left: u32, calls: u32 }
    trait Count { fn next_value(&mut self) -> Option<u32>; fn count_all(&mut self) -> u32 { let mut n = 0; while self.next_value().is_some() { n += 1; } n } }
    impl Count for Slow { fn next_value(&mut self) -> Option<u32> { self.calls += 1; if self.left == 0 { None } else { self.left -= 1; Some(self.left) } } }     // 用默认的 count_all:逐个数
    impl Count for Fast { fn next_value(&mut self) -> Option<u32> { self.calls += 1; if self.left == 0 { None } else { self.left -= 1; Some(self.left) } } fn count_all(&mut self) -> u32 { let n = self.left; self.left = 0; n } }   // 覆盖:直接返回
    struct Q(i32);
    impl PartialEq for Q { fn eq(&self, o: &Q) -> bool { self.0 == o.0 } }          // 只实现 eq
    fn main() {
        let mut s = Slow { left: 1000, calls: 0 }; let mut f = Fast { left: 1000, calls: 0 };
        let (a, b) = (s.count_all(), f.count_all());
        println!("默认实现:count_all = {},调用了 next_value {} 次", a, s.calls);
        println!("覆盖实现:count_all = {},调用了 next_value {} 次", b, f.calls);
        println!("Q(1) != Q(2) 来自 PartialEq 的默认方法 ne:{}", Q(1) != Q(2));
    }
''', quiet_src=False)
print()
print('== 三:两个默认方法互相调用,实现者一个都没覆盖:编译通过,运行时无限递归')
ok, diag, b, _ = rustc('u46c', '''
    trait Parity {
        fn is_even(&self) -> bool { !self.is_odd() }       // 默认实现互相依赖,实现者必须至少覆盖一个
        fn is_odd(&self) -> bool { !self.is_even() }
    }
    #[allow(dead_code)] struct N(u32);
    impl Parity for N {}                                    // 一个都没实现!
    fn main() { println!("{}", N(3).is_even()); }
''')
print('  编译:', '成功' if ok else '失败'); print('  警告/错误:', diag.split('\n')[0] if diag else '(无)')
rc, o, e, t = run(b); print(f'  运行:退出码 {rc}(负数表示被信号终止:{ -rc if rc < 0 else "-"});stderr 第一行:{e.strip().splitlines()[0] if e.strip() else "(空)"}'); R['recursion'] = dict(rc=rc, err=e.strip().splitlines()[:2])
print()
print('== 四:默认方法也在 vtable 里:通过 trait 对象调用,实现者覆盖了的用覆盖版本,没覆盖的用默认版本')
r = tryit('u46d', '''
    trait Greeter {
        fn name(&self) -> String;
        fn greet(&self) -> String { format!("你好,{}!", self.name()) }
    }
    struct Plain; struct Formal;
    impl Greeter for Plain { fn name(&self) -> String { "小明".into() } }
    impl Greeter for Formal { fn name(&self) -> String { "王先生".into() } fn greet(&self) -> String { format!("{} 您好,欢迎光临。", self.name()) } }
    fn main() {
        let list: Vec<Box<dyn Greeter>> = vec![Box::new(Plain), Box::new(Formal)];
        for g in &list { println!("{}", g.greet()); }
    }
''', quiet_src=False)
save('u46', R)
