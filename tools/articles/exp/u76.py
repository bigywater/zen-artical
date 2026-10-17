import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u76'); R = {}
print('== 一:catch_unwind 把 panic 变成 Result;载荷类型取决于 panic! 的写法(&str 或 String)')
r = tryit('u76a', '''
    use std::panic;
    fn main() {
        panic::set_hook(Box::new(|_| {}));   // 关掉默认的 stderr 输出,便于看清返回值
        let r1 = panic::catch_unwind(|| { 1 + 1 });
        println!("没有 panic: {:?}", r1);
        let r2 = panic::catch_unwind(|| { panic!("固定字符串"); });
        let p2 = r2.unwrap_err();
        println!("panic!(\\"字面量\\") 的载荷: &str = {:?}  String = {:?}", p2.downcast_ref::<&str>(), p2.downcast_ref::<String>());
        let n = 7;
        let p3 = panic::catch_unwind(|| { panic!("带参数 {}", n); }).unwrap_err();
        println!("panic!(\\"带 {{}}\\", n) 的载荷: &str = {:?}  String = {:?}", p3.downcast_ref::<&str>(), p3.downcast_ref::<String>());
        let p4 = panic::catch_unwind(|| { std::panic::panic_any(42i32); }).unwrap_err();
        println!("panic_any(42i32) 的载荷: i32 = {:?}", p4.downcast_ref::<i32>());
        println!("程序继续运行");
    }
''', quiet_src=True); R['basic'] = r['out']
print()
print('== 二:闭包捕获 &mut 时需要 AssertUnwindSafe:不加会编译失败')
r = tryit('u76b', '''
    use std::panic;
    fn main() {
        let mut count = 0;
        let r = panic::catch_unwind(|| { count += 1; panic!("x"); });
        println!("{:?} {}", r.is_err(), count);
    }
''', maxlines=30); R['e_unwind'] = r['diag']
r = tryit('u76c', '''
    use std::panic::{self, AssertUnwindSafe};
    fn main() {
        panic::set_hook(Box::new(|_| {}));
        let mut count = 0;
        let r = panic::catch_unwind(AssertUnwindSafe(|| { count += 1; panic!("x"); }));
        println!("is_err = {}  闭包 panic 之前对 count 的修改仍然可见: count = {}", r.is_err(), count);
    }
''', quiet_src=True); R['assert'] = r['out']
print()
print('== 三:panic 时持锁:Mutex 被「毒化」(poisoned);catch_unwind 之后再 lock 得到 Err,可用 into_inner 取出数据')
r = tryit('u76d', '''
    use std::{panic::{self, AssertUnwindSafe}, sync::Mutex};
    fn main() {
        panic::set_hook(Box::new(|_| {}));
        let m = Mutex::new(vec![1, 2, 3]);
        let _ = panic::catch_unwind(AssertUnwindSafe(|| { let mut g = m.lock().unwrap(); g.push(4); panic!("持锁时 panic"); }));
        println!("is_poisoned = {}", m.is_poisoned());
        match m.lock() { Ok(_) => println!("lock 成功"), Err(e) => println!("lock 返回 Err(PoisonError),但数据还在: {:?}", e.into_inner()) }
        m.clear_poison(); println!("clear_poison 之后 is_poisoned = {}", m.is_poisoned());
    }
''', quiet_src=True); R['poison'] = r['out']
print()
print('== 四:resume_unwind 重新抛出,不再触发 hook;panic = "abort" 时 catch_unwind 抓不到(进程被终止)')
r = tryit('u76e', '''
    use std::panic;
    fn main() {
        panic::set_hook(Box::new(|i| println!("hook 被调用: {}", i.payload().downcast_ref::<&str>().copied().unwrap_or("?"))));
        let r = panic::catch_unwind(|| { panic!("原始 panic"); });
        println!("第一次捕获后继续");
        let payload = r.unwrap_err();
        let r2 = panic::catch_unwind(panic::AssertUnwindSafe(|| panic::resume_unwind(payload)));
        println!("resume_unwind 之后又被捕获了:is_err = {};hook 没有再被调用(只打印过一次 hook)", r2.is_err());
    }
''', quiet_src=True); R['resume'] = r['out']
files = {'src/main.rs': '''
    fn main() {
        let r = std::panic::catch_unwind(|| { panic!("boom"); });
        println!("catch_unwind 返回了 {:?}", r.is_err());
    }
'''}
d = proj('u76f', files, toml_extra='[profile.dev]\npanic = "abort"'); cargo(['build', '--quiet'], d, timeout=600)
rc, o, e, _ = run(TG / 'debug' / 'u76f')
print(f'  panic = "abort":被信号 {-rc} 终止(返回码 {rc}),stdout={o.strip()!r}(catch_unwind 没有机会返回)')
R['abort'] = [rc, o.strip()]
print()
print('== 五:Drop 里再 panic(正在展开时又 panic)会直接 abort')
r = tryit('u76g', '''
    struct Bomb; impl Drop for Bomb { fn drop(&mut self) { println!("Bomb::drop 里 panic"); panic!("drop 里的 panic"); } }
    fn main() { let _b = Bomb; println!("主函数先 panic"); panic!("第一个 panic"); }
''', quiet_src=False, show_run=False)
rc, o, e, _ = run(r['bin'])
el = [l for l in e.splitlines() if l.strip() and not re.match(r'\s+\d+: |\s+at |stack backtrace', l)]
print(f'  运行(返回码 {rc},即被信号 {-rc} 终止):'); print('    stdout:', o.strip().replace(chr(10), ' | '))
print('    stderr(去掉回溯栈帧):'); print('\n'.join('      ' + l for l in el))
R['double'] = {'rc': rc, 'out': o.strip(), 'err': el}
save('u76', R)
