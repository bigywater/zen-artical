import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u134'); R = {}
HEAD = '''
    #![allow(unused)]
    use std::{fs::{self, File}, io::{self, Read}, os::fd::{AsRawFd, FromRawFd, IntoRawFd, OwnedFd, BorrowedFd}, path::PathBuf};
    fn tmp(name: &str) -> PathBuf { let d = std::env::temp_dir().join("u134"); fs::create_dir_all(&d).unwrap(); d.join(name) }
    fn open_fds() -> usize { fs::read_dir("/dev/fd").map(|d| d.count()).unwrap_or(0) }
    unsafe extern "C" { fn close(fd: i32) -> i32; fn getrlimit(resource: i32, rlim: *mut [u64; 2]) -> i32; }
'''
print('== 一:文件描述符(fd)是 File 里的一个整数;File 被 drop 时 fd 才被关闭。用 /dev/fd 数当前打开的 fd')
r = tryit('u134a', HEAD + '''
    fn main() {
        let p = tmp("a.txt"); fs::write(&p, "x").unwrap();
        let base = open_fds();
        let f1 = File::open(&p).unwrap(); println!("打开 1 个文件:fd = {},进程里打开的 fd 数 {} → {}", f1.as_raw_fd(), base, open_fds());
        let f2 = File::open(&p).unwrap(); println!("再打开 1 个:fd = {},数量 {}", f2.as_raw_fd(), open_fds());
        drop(f1); println!("drop(f1) 之后数量 {}", open_fds());
        let f3 = File::open(&p).unwrap(); println!("再开一个,拿到的 fd = {}(复用了刚释放的编号)", f3.as_raw_fd());
        { let _g = File::open(&p).unwrap(); println!("块内再开一个,数量 {}", open_fds()); } println!("块结束(自动 drop)之后数量 {}", open_fds());
    }
''', quiet_src=True); R['basic'] = r['out']
print()
print('== 二:fd 有上限:不 drop 地一直打开文件,到上限后 open 失败(Too many open files,os error 24)')
r = tryit('u134b', HEAD + '''
    fn main() {
        let p = tmp("b.txt"); fs::write(&p, "x").unwrap();
        let mut lim = [0u64; 2]; unsafe { getrlimit(8, &mut lim); }   // RLIMIT_NOFILE = 8 on macOS
        println!("RLIMIT_NOFILE 软限制 = {}(getrlimit 报告的值)", lim[0]);
        let mut keep = Vec::new();
        loop { match File::open(&p) { Ok(f) => keep.push(f), Err(e) => { println!("第 {} 次 open 失败:kind = {:?},os_error = {:?},{}", keep.len() + 1, e.kind(), e.raw_os_error(), e); break; } } }
        println!("一共成功打开 {} 个(加上进程启动时已有的 stdin/out/err 等)", keep.len());
        let n = keep.len(); keep.truncate(n - 10); println!("释放 10 个之后再 open: {}", if File::open(&p).is_ok() { "成功" } else { "失败" });
    }
''', quiet_src=True); R['limit'] = r['out']
print()
print('== 三:循环里打开 1000 个文件:每轮自动 drop 与 mem::forget 泄漏的 fd 数对比')
r = tryit('u134c', HEAD + '''
    fn main() {
        let p = tmp("c.txt"); fs::write(&p, "x").unwrap();
        let mut ok = 0; for _ in 0..1000 { let mut s = String::new(); match File::open(&p).and_then(|mut f| f.read_to_string(&mut s)) { Ok(_) => ok += 1, Err(_) => break } }
        println!("每轮函数结束时 File 被 drop:处理了 {} / 1000 个,结束后 fd 数 {}", ok, open_fds());
        let mut leaked = 0; for _ in 0..1000 { match File::open(&p) { Ok(f) => { std::mem::forget(f); leaked += 1; } Err(_) => break } }
        println!("mem::forget 让 fd 泄漏:打开了 {} 个并忘记关闭,结束后 fd 数 {}(从 4 涨到 {},一个都没有回收)", leaked, open_fds(), open_fds());
    }
''', quiet_src=True); R['leak'] = r['out']
print()
print('== 四:所有权防止重复关闭:try_clone 得到独立的 fd(dup),各自关闭;into_raw_fd 之后 Rust 不再负责关闭')
r = tryit('u134d', HEAD + '''
    fn main() {
        let p = tmp("d.txt"); fs::write(&p, "hello").unwrap(); let base = open_fds();
        let f = File::open(&p).unwrap(); let g = f.try_clone().unwrap(); println!("try_clone:原 fd = {},克隆 fd = {}(不同编号,指向同一个打开的文件),数量 {}", f.as_raw_fd(), g.as_raw_fd(), open_fds() - base);
        drop(f); let mut s = String::new(); let mut g = g; g.read_to_string(&mut s).unwrap(); println!("原 File 已 drop,克隆仍然可读:{:?}", s);
        let raw = File::open(&p).unwrap().into_raw_fd(); println!("into_raw_fd 得到 fd {}:File 已经被消耗,但 fd 仍然打开(数量 {}),要自己关闭", raw, open_fds() - base);
        let r1 = unsafe { close(raw) }; let r2 = unsafe { close(raw) }; println!("手动 close 两次:第一次返回 {},第二次返回 {}(-1 = EBADF:fd 已经关了)", r1, r2);
        let o = unsafe { OwnedFd::from_raw_fd(File::open(&p).unwrap().into_raw_fd()) }; println!("OwnedFd::from_raw_fd 重新交给 Rust 管理:数量 {}", open_fds() - base); drop(o); println!("drop(OwnedFd) 之后数量 {}", open_fds() - base);
    }
''', quiet_src=True); R['own'] = r['out']
print()
print('== 五:fd 被子进程继承吗?子进程里能不能看到父进程打开的 File 的 fd')
r = tryit('u134e', HEAD + '''
    use std::process::Command;
    fn main() {
        let p = tmp("e.txt"); fs::write(&p, "x").unwrap(); let f = File::open(&p).unwrap(); let fd = f.as_raw_fd();
        let out = Command::new("sh").arg("-c").arg(format!("if [ -e /dev/fd/{} ]; then echo 'child sees fd {}'; else echo 'child has no fd {} (not inherited)'; fi", fd, fd, fd)).output().unwrap();
        print!("{}", String::from_utf8_lossy(&out.stdout));
    }
''', quiet_src=True); R['cloexec'] = r['out']
save('u134', R)
