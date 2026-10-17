import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
import signal as pysig
tee('u144'); R = {}
LIBC = '''
    #![allow(unused)]
    use std::{sync::atomic::{AtomicBool, AtomicUsize, Ordering::SeqCst}, thread, time::Duration};
    #[repr(C)] struct SigAction { sa_sigaction: usize, sa_mask: u32, sa_flags: i32 }
    unsafe extern "C" { fn sigaction(sig: i32, act: *const SigAction, old: *mut SigAction) -> i32; fn kill(pid: i32, sig: i32) -> i32; fn getpid() -> i32; fn write(fd: i32, buf: *const u8, n: usize) -> isize; fn getpid_() -> i32; }
    const SIGINT: i32 = 2; const SIGKILL: i32 = 9; const SIGUSR1: i32 = 30; const SIGTERM: i32 = 15;
    fn install(sig: i32, h: extern "C" fn(i32)) -> i32 { let a = SigAction { sa_sigaction: h as usize, sa_mask: 0, sa_flags: 0 }; unsafe { sigaction(sig, &a, std::ptr::null_mut()) } }
    struct Guard(&'static str); impl Drop for Guard { fn drop(&mut self) { println!("  Guard({}) 被 drop —— 清理代码运行了", self.0); } }
'''
print('== 一:默认行为:SIGTERM 直接终止进程,不运行任何 Drop(栈上的 Guard 没有机会清理)')
r = tryit('u144a', LIBC + '''
    fn main() { let _g = Guard("默认"); println!("  子进程开始等待(pid {}),等 SIGTERM", unsafe { getpid() }); std::io::Write::flush(&mut std::io::stdout()).unwrap(); thread::sleep(Duration::from_secs(5)); }
''', quiet_src=True, show_run=False)
p = subprocess.Popen([str(r['bin'])], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True); first = p.stdout.readline(); p.send_signal(pysig.SIGTERM); out, err = p.communicate(timeout=5); out = first + out
print('  子进程输出:', out.strip().splitlines()); print(f'  收到 SIGTERM 后:退出码 {p.returncode}(负数 = 被信号 {-p.returncode} 终止),没有 "Guard 被 drop" 这一行'); R['default'] = [p.returncode, out.strip().splitlines()]
print()
print('== 二:自己安装 SIGTERM 处理函数:handler 里只设置一个原子标志(async-signal-safe),主循环发现标志后正常返回 —— Drop 运行,退出码 0')
r = tryit('u144b', LIBC + '''
    static STOP: AtomicBool = AtomicBool::new(false); static HITS: AtomicUsize = AtomicUsize::new(0);
    extern "C" fn on_term(_: i32) { STOP.store(true, SeqCst); HITS.fetch_add(1, SeqCst); }
    fn main() {
        let _g = Guard("优雅退出"); let rc = install(SIGTERM, on_term); println!("  installed sigaction,返回 {}", rc);
        println!("  工作中(pid {}),等待 SIGTERM", unsafe { getpid() }); std::io::Write::flush(&mut std::io::stdout()).unwrap();
        let mut ticks = 0; while !STOP.load(SeqCst) { thread::sleep(Duration::from_millis(20)); ticks += 1; if ticks > 400 { break; } }
        println!("  发现停止标志,处理函数被调用 {} 次,退出主循环", HITS.load(SeqCst));
    }
''', quiet_src=True, show_run=False)
p = subprocess.Popen([str(r['bin'])], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True); first = p.stdout.readline() + p.stdout.readline(); p.send_signal(pysig.SIGTERM); out, err = p.communicate(timeout=10); out = first + out
print('  子进程输出:'); print('\n'.join('    ' + l for l in out.strip().splitlines())); print(f'  退出码 {p.returncode}'); R['graceful'] = [p.returncode, out.strip().splitlines()]
print()
print('== 三:标准信号不排队:阻塞期间连续发 100 次 SIGUSR1,解除阻塞后处理函数只会被调用 1 次(合并);不阻塞时每次发送都会被处理')
r = tryit('u144c', LIBC + '''
    static COUNT: AtomicUsize = AtomicUsize::new(0);
    extern "C" fn on_usr1(_: i32) { COUNT.fetch_add(1, SeqCst); }
    unsafe extern "C" { fn pthread_sigmask(how: i32, set: *const u32, old: *mut u32) -> i32; }
    fn main() {
        install(SIGUSR1, on_usr1);
        unsafe { for _ in 0..100 { kill(getpid(), SIGUSR1); } } thread::sleep(Duration::from_millis(50));
        println!("  不阻塞:连续发 100 次,处理函数被调用 {} 次", COUNT.swap(0, SeqCst));
        let block: u32 = 1 << (SIGUSR1 - 1); let mut old = 0u32;
        unsafe { pthread_sigmask(1, &block, &mut old); for _ in 0..100 { kill(getpid(), SIGUSR1); } }
        println!("  阻塞期间发 100 次,解除阻塞前处理函数被调用 {} 次", COUNT.load(SeqCst));
        unsafe { pthread_sigmask(2, &block, std::ptr::null_mut()); } thread::sleep(Duration::from_millis(50));
        println!("  解除阻塞后:处理函数共被调用 {} 次(100 个信号被合并成 1 个待处理信号)", COUNT.load(SeqCst));
    }
''', quiet_src=True); R['coalesce'] = r['out']
print()
print('== 四:SIGKILL 与 SIGSTOP 不能被捕获或忽略:sigaction 返回 -1(EINVAL)')
r = tryit('u144d', LIBC + '''
    extern "C" fn noop(_: i32) {}
    fn main() { println!("  对 SIGKILL 安装处理函数:返回 {};对 SIGTERM:返回 {}", install(SIGKILL, noop), install(SIGTERM, noop)); println!("  errno = {:?}", std::io::Error::last_os_error().raw_os_error()); }
''', quiet_src=True); R['kill'] = r['out']
print()
print('== 五:忽略信号与 SIGPIPE:Rust 的运行时已经把 SIGPIPE 设成了忽略(上一篇「二进制启动」里验证过);查询当前处理方式')
r = tryit('u144e', LIBC + '''
    fn main() {
        let mut old = SigAction { sa_sigaction: 0, sa_mask: 0, sa_flags: 0 };
        for (name, sig) in [("SIGPIPE", 13), ("SIGINT", 2), ("SIGTERM", 15), ("SIGUSR1", 30)] { unsafe { sigaction(sig, std::ptr::null(), &mut old); } println!("  {:<8} 当前处理:{}", name, match old.sa_sigaction { 0 => "SIG_DFL(默认)", 1 => "SIG_IGN(忽略)", _ => "自定义函数" }); }
    }
''', quiet_src=True); R['query'] = r['out']
save('u144', R)
