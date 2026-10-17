import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u75'); R = {}
def panic_case(name, body, release=False, args=()):
    r = tryit(name, 'fn main() { ' + body + ' }', quiet_src=True, release=release, show_run=False)
    rc, o, e, _ = run(r['bin'], *args)
    e = '\n'.join(l for l in e.splitlines() if not l.startswith('note: run with'))
    return rc, o, e
print('== 一:常见 panic 的真实消息与退出码')
cases = [
    ('Option::unwrap on None', 'let x: Option<i32> = None; x.unwrap();'),
    ('Result::unwrap on Err', 'let r: Result<i32, String> = Err("磁盘满".into()); r.unwrap();'),
    ('expect 带自定义消息', 'let x: Option<i32> = None; x.expect("配置里必须有端口");'),
    ('Result::expect', 'let r: Result<i32, std::num::ParseIntError> = "a".parse::<i32>(); r.expect("解析端口");'),
    ('数组越界', 'let v = vec![1, 2, 3]; let i = std::env::args().count() + 4; println!("{}", v[i]);'),
    ('除以零', 'let d = std::env::args().count() as i32 - 1; println!("{}", 10 / d);'),
    ('RefCell 重复可变借用', 'let c = std::cell::RefCell::new(1); let _a = c.borrow_mut(); let _b = c.borrow_mut();'),
    ('显式 panic! 带格式', 'let n = 3; panic!("状态非法: n = {}", n);'),
    ('unreachable!', 'let n = std::env::args().count(); if n < 5 { unreachable!("n = {}", n); }'),
]
R['cases'] = []
for title, body in cases:
    rc, o, e = panic_case('u75a', body)
    msg = [l for l in e.splitlines() if l.strip()]
    print(f'  【{title}】退出码 {rc}'); print('\n'.join('      ' + l for l in msg[:3])); R['cases'].append([title, rc, msg[:3]])
print()
print('== 二:整数溢出:debug 构建 panic,release 构建默默回绕')
body = 'let x: u8 = 250u8 + (std::env::args().count() as u8) * 6; println!("x = {}", x);'
for rel in (False, True):
    rc, o, e = panic_case('u75b', body, release=rel); print(f'  {"release" if rel else "debug  "}: 退出码 {rc}  stdout={o.strip()!r}  stderr={[l for l in e.splitlines() if l.strip()][:2]}')
    R['ovf_' + ('rel' if rel else 'dbg')] = [rc, o.strip(), [l for l in e.splitlines() if l.strip()][:2]]
print()
print('== 三:unwrap_or / unwrap_or_else / unwrap_or_default / ? 这些不 panic 的替代;unwrap_or 的参数是急切求值的')
r = tryit('u75c', '''
    fn expensive(tag: &str) -> i32 { println!("  expensive({}) 被调用", tag); 42 }
    fn main() {
        let some = Some(1); let none: Option<i32> = None;
        println!("Some(1).unwrap_or(expensive) = {}", some.unwrap_or(expensive("unwrap_or")));
        println!("Some(1).unwrap_or_else(expensive) = {}", some.unwrap_or_else(|| expensive("unwrap_or_else")));
        println!("None.unwrap_or_else(expensive) = {}", none.unwrap_or_else(|| expensive("none")));
        println!("None.unwrap_or_default() = {}", none.unwrap_or_default());
        println!("Err 的 unwrap_or_else 能看到错误: {}", "x".parse::<i32>().unwrap_or_else(|e| { println!("  拿到错误: {}", e); -1 }));
    }
''', quiet_src=True); R['alts'] = r['out']
print()
print('== 四:线程里的 panic 只杀死那个线程,join 返回 Err;主线程继续;panic 载荷可以取出')
r = tryit('u75d', '''
    use std::thread;
    fn main() {
        let h = thread::spawn(|| { if true { panic!("子线程出错了"); } 5 });
        match h.join() {
            Ok(v) => println!("子线程返回 {}", v),
            Err(p) => println!("join 得到 Err,载荷是 {:?};主线程继续运行", p.downcast_ref::<&str>()),
        }
        println!("主线程仍在运行");
    }
''', quiet_src=True); R['thread'] = {'rc': r['rc'], 'out': r['out'], 'err': [l for l in r['err'].splitlines() if l.strip() and not l.startswith('note: run with')]}
print()
print('== 五:panic hook 自定义输出;panic = "abort" 的差别(cargo profile)')
r = tryit('u75e', '''
    struct G; impl Drop for G { fn drop(&mut self) { println!("  Drop 运行了"); } }
    fn main() {
        std::panic::set_hook(Box::new(|info| { println!("自定义 hook:{}", info.payload().downcast_ref::<&str>().copied().unwrap_or("?")); }));
        let _g = G;
        panic!("出事了");
    }
''', quiet_src=True); R['hook'] = {'rc': r['rc'], 'out': r['out'], 'err': r['err']}
files = {'src/main.rs': '''
    struct G; impl Drop for G { fn drop(&mut self) { println!("  Drop 运行了"); } }
    fn main() { let _g = G; println!("即将 panic"); panic!("boom"); }
'''}
d = proj('u75f', files, toml_extra='[profile.dev]\npanic = "abort"')
rc, o = cargo(['build', '--quiet'], d, timeout=600)
bin_ = TG / 'debug' / 'u75f'; rc2, o2, e2, _ = run(bin_)
print(f'  panic = "abort":被信号 {-rc2}(SIGABRT)终止(Python 报告返回码 {rc2});stdout={o2.strip()!r}(没有 "Drop 运行了");stderr 最后一行: {[l for l in e2.splitlines() if l.strip()][-1:]}')
d = proj('u75g', files); cargo(['build', '--quiet'], d, timeout=600); rc3, o3, e3, _ = run(TG / 'debug' / 'u75g')
print(f'  默认 unwind:    退出码 {rc3};stdout={o3.strip()!r}')
R['abort'] = {'abort': [rc2, o2.strip(), [l for l in e2.splitlines() if l.strip()][-1:]], 'unwind': [rc3, o3.strip()]}
save('u75', R)
