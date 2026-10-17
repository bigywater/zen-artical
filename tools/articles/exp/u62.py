import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u62'); R = {}
print('== 一:只调用 map 不消费:闭包一次都不会执行,编译器还会警告 unused')
r = tryit('u62a', '''
    fn main() {
        let v = vec![1, 2, 3];
        v.iter().map(|x| { println!("闭包执行了 x={}", x); x * 2 });
        println!("上一行之后,没有任何「闭包执行了」输出");
    }
''', quiet_src=False); R['nothing'] = r['out']
print()
print('== 二:一个元素一个元素地走完整条链(交错执行),而不是一个阶段处理完所有元素再进入下一个阶段')
r = tryit('u62b', '''
    fn main() {
        let r: Vec<i32> = (1..=4)
            .inspect(|x| println!("  源      产出 {}", x))
            .filter(|x| { let keep = x % 2 == 0; println!("  filter  {} -> {}", x, keep); keep })
            .map(|x| { println!("  map     {} -> {}", x, x * 10); x * 10 })
            .collect();
        println!("结果 {:?}", r);
    }
''', quiet_src=False); R['interleave'] = r['out']
print()
print('== 三:短路:take / find / any 一旦满足就停止,后面的元素根本不会被产生(用计数器验证)')
r = tryit('u62c', '''
    use std::cell::Cell;
    fn main() {
        let produced = Cell::new(0);
        let src = || (1..=1_000_000).inspect(|_| produced.set(produced.get() + 1));
        let a: Vec<i32> = src().filter(|x| x % 3 == 0).take(3).collect();
        println!("filter(%3==0).take(3) = {:?}  源总共产出 {} 个", a, produced.get()); produced.set(0);
        let f = src().find(|x| *x == 7);
        println!("find(==7) = {:?}  源总共产出 {} 个", f, produced.get()); produced.set(0);
        let any = src().any(|x| x > 100);
        println!("any(>100) = {}  源总共产出 {} 个", any, produced.get()); produced.set(0);
        let n = src().take(5).count();
        println!("take(5).count() = {}  源总共产出 {} 个", n, produced.get()); produced.set(0);
        let s: i32 = src().take_while(|x| *x < 4).sum();
        println!("take_while(<4).sum() = {}  源总共产出 {} 个(多产出一个用来发现 4 不满足条件)", s, produced.get());
    }
''', quiet_src=True); R['short'] = r['out']
print()
print('== 四:惰性让无穷迭代器成为可能;链本身只是一个嵌套的结构体,类型里记录了每一层')
r = tryit('u62d', '''
    fn tn<T>(_: &T) -> &'static str { std::any::type_name::<T>() }
    fn main() {
        let nat = 1u64..;
        let evens_sq: Vec<u64> = nat.clone().filter(|x| x % 2 == 0).map(|x| x * x).take(5).collect();
        println!("无穷序列取前 5 个偶数的平方: {:?}", evens_sq);
        let k = 3;
        let it = (1..10).filter(|x| x % 2 == 0).map(move |x| x * k);
        println!("类型: {}", tn(&it).replace("core::iter::adapters::", "").replace("core::ops::range::", ""));
        println!("size_of(这条链) = {} 字节(Range<i32> 本身 {} 字节;闭包 filter 无捕获、map 捕获了 k)", std::mem::size_of_val(&it), std::mem::size_of::<std::ops::Range<i32>>());
        let big: Vec<u8> = vec![0; 1_000_000];
        let it2 = big.iter().map(|x| x + 1).filter(|x| *x > 0);
        println!("在 100 万元素 Vec 上建一条 map+filter 链: size_of = {} 字节(只存了迭代器状态,不存元素)", std::mem::size_of_val(&it2));
    }
''', quiet_src=True); R['types'] = r['out']
print()
print('== 五:惰性的代价:迭代器引用的数据必须一直活着;闭包副作用的执行时机取决于消费点')
r = tryit('u62e', '''
    fn main() {
        let it;
        {
            let v = vec![1, 2, 3];
            it = v.iter().map(|x| x * 2);
        }
        println!("{:?}", it.collect::<Vec<_>>());
    }
''', maxlines=25); R['e0597'] = r['diag'].split('\\n')[0]
r = tryit('u62f', '''
    fn main() {
        let mut log = Vec::new();
        let lazy = (1..=3).map(|x| { log.push(x); x });
        println!("建好链之后 log = (此时不能读,因为闭包还借着 log)");
        let _ = lazy.count();
        println!("消费之后 log = {:?}", log);
    }
''', quiet_src=True); R['log'] = r['out']
save('u62', R)
