import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u13'); R = {}
print('== 一:const 与 static 的基本用法;static 有固定的内存地址(在数据段),不同于代码段与栈')
r = tryit('u13a', '''
    const LIMIT: u32 = 100;
    static GREETING: &str = "hello";
    static TABLE: [u32; 4] = [1, 2, 4, 8];
    fn main() {
        println!("const LIMIT = {LIMIT}, static GREETING = {GREETING}, TABLE[3] = {}", TABLE[3]);
        println!("static TABLE 的地址两次相同吗? {}", &TABLE as *const _ as usize == &TABLE as *const _ as usize);
        println!("static TABLE 地址 = {:#x}(在可执行文件的数据段)", &TABLE as *const _ as usize);
        let main_addr = main as *const () as usize;
        println!("main 函数地址     = {:#x}(代码段)", main_addr);
        println!("栈上局部变量地址  = {:#x}", &main_addr as *const usize as usize);
    }
''', quiet_src=False)
print()
print('== 二:const fn 在编译期求值:函数调用被折叠成一个常量(看汇编)')
code = '''
    const fn fib(n: u32) -> u64 { let (mut a, mut b) = (0u64, 1u64); let mut i = 0; while i < n { let t = a + b; a = b; b = t; i += 1; } a }
    const FIB20: u64 = fib(20);
    #[unsafe(no_mangle)] pub fn get() -> u64 { FIB20 }
    #[unsafe(no_mangle)] pub fn runtime(n: u32) -> u64 { let (mut a, mut b) = (0u64, 1u64); let mut i = 0; while i < n { let t = a + b; a = b; b = t; i += 1; } a }
'''
a1, _ = asm_of('u13b', code, 'get'); a2, _ = asm_of('u13b', code, 'runtime')
print('  fib(20) 作为 const 求值,get() 的汇编:', ' ; '.join(a1)); print(f'  同样的循环在运行时算(runtime(n),{len(a2)} 条指令):', ' ; '.join(a2[:8]) + (' ...' if len(a2) > 8 else '')); R['get_asm'] = a1; R['fib20'] = 6765
print()
print('== 三:static mut 需要 unsafe;2024 edition 里对它取引用还会被 lint 拒绝')
r = tryit('u13c', '''
    static mut COUNTER: u32 = 0;
    fn main() {
        COUNTER += 1;
        println!("{}", COUNTER);
    }
''', maxlines=30); R['e_mut'] = [l for l in r['diag'].split('\n') if l.startswith('error')][:2]
r = tryit('u13d', '''
    static mut COUNTER: u32 = 0;
    fn main() {
        unsafe { COUNTER += 1; }
        let v = unsafe { COUNTER };
        println!("{}", v);
        unsafe { println!("{}", COUNTER); }
    }
''', maxlines=24); R['e_mutref'] = [l for l in r['diag'].split('\n') if l.startswith(('error', 'warning'))][:2]
print()
print('== 四:安全的可变全局:原子类型(或 Mutex)放在 static 里')
r = tryit('u13e', '''
    use std::sync::atomic::{AtomicUsize, Ordering};
    use std::thread;
    static COUNTER: AtomicUsize = AtomicUsize::new(0);
    fn main() {
        let hs: Vec<_> = (0..4).map(|_| thread::spawn(|| { for _ in 0..1000 { COUNTER.fetch_add(1, Ordering::Relaxed); } })).collect();
        for h in hs { h.join().unwrap(); }
        println!("4 个线程各加 1000 次,COUNTER = {}", COUNTER.load(Ordering::Relaxed));
    }
''', quiet_src=False)
r = tryit('u13f', '''
    use std::cell::Cell;
    static C: Cell<i32> = Cell::new(0);
    fn main() { C.set(1); }
''', maxlines=18); R['e_sync'] = r['diag'].split('\n')[0]
save('u13', R)
