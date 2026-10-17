import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u87'); R = {}
print('== 一:spawn 返回 JoinHandle;join 得到线程的返回值(Result);线程有自己的 id 与名字')
r = tryit('u87a', '''
    use std::thread;
    fn main() {
        let main_id = thread::current().id();
        let h = thread::spawn(|| { let t = thread::current(); (t.id(), t.name().map(String::from), (1..=10).sum::<i32>()) });
        let (id, name, sum) = h.join().unwrap();
        println!("主线程名 {:?}  子线程名 {:?}  两个线程 id 不同: {}  子线程算出 {}", thread::current().name(), name, id != main_id, sum);
        let b = thread::Builder::new().name("worker-7".into()).spawn(|| thread::current().name().unwrap().to_string()).unwrap();
        println!("Builder 命名的线程: {}", b.join().unwrap());
    }
''', quiet_src=True); R['basic'] = r['out']
print()
print('== 二:闭包借用局部变量,必须 move(E0373);Vec 被 move 进线程后主线程不能再用(E0382)')
r = tryit('u87b', '''
    use std::thread;
    fn main() { let v = vec![1, 2, 3]; let h = thread::spawn(|| { println!("{:?}", v); }); h.join().unwrap(); }
''', maxlines=30); R['e0373'] = r['diag']
r = tryit('u87c', '''
    use std::thread;
    fn main() { let v = vec![1, 2, 3]; let h = thread::spawn(move || { println!("{:?}", v); }); println!("{:?}", v); h.join().unwrap(); }
''', maxlines=30); R['e0382'] = r['diag']
print()
print('== 三:不 join:main 返回时进程结束,还没跑完的子线程被直接终止;join 之后才保证跑完')
code = '''
    use std::{thread, time::Duration};
    fn main() {
        let join = std::env::args().nth(1).as_deref() == Some("join");
        let h = thread::spawn(|| { thread::sleep(Duration::from_millis(200)); println!("子线程跑完了"); });
        println!("主线程到达末尾(join = {})", join);
        if join { h.join().unwrap(); }
    }
'''
r = tryit('u87d', code, quiet_src=True, show_run=False)
for a in ((), ('join',)):
    rc, o, e, _ = run(r['bin'], *a); print(f'  参数 {a}: stdout = {o.strip().splitlines()}'); R['join_' + ('yes' if a else 'no')] = o.strip().splitlines()
print()
print('== 四:执行顺序不确定:8 个线程各打印自己的编号,同一程序连跑 8 次的记录顺序')
r = tryit('u87e', '''
    use std::{thread, sync::Mutex};
    fn main() {
        let order = Mutex::new(Vec::new());
        thread::scope(|s| { for i in 0..8 { let order = &order; s.spawn(move || { order.lock().unwrap().push(i); }); } });
        println!("{}", order.lock().unwrap().iter().map(|x| x.to_string()).collect::<Vec<_>>().join(""));
    }
''', quiet_src=True, show_run=False)
orders = [run(r['bin'])[1].strip() for _ in range(8)]; print('  8 次运行的顺序:', orders, f'(共 {len(set(orders))} 种不同顺序)'); R['orders'] = orders
print()
print('== 五:thread::scope:借用局部变量,不需要 move,离开作用域时自动 join;spawn 的创建+join 成本')
r = tryit('u87f', '''
    use std::{thread, time::Instant};
    fn main() {
        let mut data = vec![1, 2, 3, 4, 5, 6];
        let total = thread::scope(|s| {
            let (l, r) = data.split_at_mut(3);
            let h1 = s.spawn(|| { l.iter_mut().for_each(|x| *x *= 10); l.iter().sum::<i32>() });
            let h2 = s.spawn(|| { r.iter_mut().for_each(|x| *x += 1); r.iter().sum::<i32>() });
            h1.join().unwrap() + h2.join().unwrap()
        });
        println!("scope 里两个线程分别改 data 的左右两半:data = {:?} 合计 {}", data, total);
        let n = 2000; let t = Instant::now();
        for _ in 0..n { thread::spawn(|| {}).join().unwrap(); }
        let per = t.elapsed().as_secs_f64() * 1e6 / n as f64;
        println!("spawn + join 一个空线程平均 {:.0} µs(release,{} 次)", per, n);
    }
''', quiet_src=True, release=True); R['scope'] = r['out']
print()
print('== 六:线程栈大小:Builder 指定栈大小,递归 2000 层(每层约 256 字节局部数组)在较小的栈上会栈溢出')
code = '''
    use std::thread;
    fn depth(n: u64) -> u64 { let buf = [0u8; 256]; if n == 0 { buf[0] as u64 } else { depth(n - 1) + std::hint::black_box(buf[(n % 256) as usize]) as u64 + 1 } }
    fn main() {
        let kb: usize = std::env::args().nth(1).unwrap().parse().unwrap();
        let h = thread::Builder::new().stack_size(kb * 1024).spawn(|| depth(2000)).unwrap();
        match h.join() { Ok(v) => println!("栈 {} KiB:递归 2000 层成功 → {}", std::env::args().nth(1).unwrap(), v), Err(_) => println!("panic") }
    }
'''
r = tryit('u87g', code, quiet_src=True, show_run=False)
for kb in (2048, 512, 256, 64):
    rc, o, e, _ = run(r['bin'], str(kb)); sig = f'被信号 {-rc} 终止' if rc < 0 else f'退出码 {rc}'
    print(f'  栈 {kb} KiB:{sig};stdout={o.strip()!r};stderr 末行={[l for l in e.splitlines() if l.strip()][-1:]}'); R[f'stack_{kb}'] = [rc, o.strip(), [l for l in e.splitlines() if l.strip()][-1:]]
save('u87', R)
