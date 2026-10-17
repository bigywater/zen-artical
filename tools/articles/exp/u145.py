import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u145'); R = {}
HEAD = '''
    #![allow(unused)]
    use std::{process::{Command, Stdio, ExitStatus}, io::{Read, Write}, thread, time::{Duration, Instant}, os::unix::process::ExitStatusExt};
'''
print('== 一:output() 一次性运行并收集 stdout / stderr / 退出状态;参数不经过 shell,不会被解释')
r = tryit('u145a', HEAD + '''
    fn main() {
        let o = Command::new("echo").arg("hello").arg("a; echo INJECTED").arg("$HOME").output().unwrap();
        println!("echo 输出 {:?}  状态 {:?}  成功 {}", String::from_utf8_lossy(&o.stdout), o.status.code(), o.status.success());
        println!("(参数里的 ; 和 $HOME 原样当作字符,没有被 shell 解释,也就没有 INJECTED 这个独立命令)");
        let o = Command::new("sh").arg("-c").arg("echo out; echo err 1>&2; exit 3").output().unwrap();
        println!("sh -c:stdout {:?} stderr {:?} 退出码 {:?} 成功 {}", String::from_utf8_lossy(&o.stdout), String::from_utf8_lossy(&o.stderr), o.status.code(), o.status.success());
    }
''', quiet_src=True); R['output'] = r['out']
print()
print('== 二:错误:命令不存在(NotFound)、没有执行权限(PermissionDenied);被信号终止时 code() 是 None')
r = tryit('u145b', HEAD + '''
    fn main() {
        let e = Command::new("definitely-not-a-command-u145").output().unwrap_err(); println!("不存在的命令:kind = {:?},os_error = {:?}", e.kind(), e.raw_os_error());
        let f = std::env::temp_dir().join("u145_noexec.sh"); std::fs::write(&f, "#!/bin/sh\\necho hi\\n").unwrap();
        let e = Command::new(&f).output().unwrap_err(); println!("没有执行权限的文件:kind = {:?},os_error = {:?}", e.kind(), e.raw_os_error()); std::fs::remove_file(&f).unwrap();
        let st = Command::new("sh").arg("-c").arg("kill -TERM $$").status().unwrap(); println!("子进程被 SIGTERM 终止:code() = {:?},signal() = {:?},success() = {}", st.code(), st.signal(), st.success());
        println!("Display:{}", st);
    }
''', quiet_src=True); R['err'] = r['out']
print()
print('== 三:管道:给子进程的 stdin 写数据、读它的 stdout;spawn 返回 Child,用 wait_with_output 收尾')
r = tryit('u145c', HEAD + '''
    fn main() {
        let mut child = Command::new("sort").arg("-r").stdin(Stdio::piped()).stdout(Stdio::piped()).spawn().unwrap();
        child.stdin.take().unwrap().write_all(b"banana\\napple\\ncherry\\n").unwrap();   // 写完 drop 掉 stdin,子进程才会读到 EOF
        let out = child.wait_with_output().unwrap(); println!("sort -r 的输出:{:?}", String::from_utf8_lossy(&out.stdout));
        let p1 = Command::new("printf").arg("a\\nb\\nc\\n").stdout(Stdio::piped()).spawn().unwrap();
        let p2 = Command::new("wc").arg("-l").stdin(Stdio::from(p1.stdout.unwrap())).output().unwrap(); println!("管道 printf | wc -l:{:?}", String::from_utf8_lossy(&p2.stdout).trim());
    }
''', quiet_src=True); R['pipe'] = r['out']
print()
print('== 四:经典死锁:子进程先往 stderr 写 200 KB,再往 stdout 写;父进程先读完 stdout 才读 stderr —— 管道缓冲区写满后子进程阻塞,双方互相等待;用超时证明,再给出 wait_with_output 的正确写法')
r = tryit('u145d', HEAD + '''
    fn main() {
        let script = "head -c 200000 /dev/zero 1>&2; echo done";
        let mut child = Command::new("sh").arg("-c").arg(script).stdout(Stdio::piped()).stderr(Stdio::piped()).spawn().unwrap();
        let mut out = child.stdout.take().unwrap(); let mut err = child.stderr.take().unwrap();
        let h = thread::spawn(move || { let mut s = String::new(); out.read_to_string(&mut s).unwrap(); s });   // 先读 stdout
        thread::sleep(Duration::from_millis(500));
        println!("500 ms 后:读 stdout 的线程完成了吗? {}(子进程卡在写 stderr,没有机会写 stdout 或退出)", h.is_finished());
        let t = Instant::now(); let mut e = Vec::new(); err.read_to_end(&mut e).unwrap(); println!("现在读 stderr,读到 {} 字节(用时 {} ms),死锁解除", e.len(), t.elapsed().as_millis());
        println!("stdout 线程结果:{:?}", h.join().unwrap().trim());
        let o = Command::new("sh").arg("-c").arg(script).output().unwrap(); println!("对照:output() 内部同时读两个管道,不会死锁:stdout {:?},stderr {} 字节", String::from_utf8_lossy(&o.stdout).trim(), o.stderr.len());
    }
''', quiet_src=True); R['deadlock'] = r['out']
print()
print('== 五:环境变量、工作目录;env_clear;子进程默认继承父进程环境')
r = tryit('u145e', HEAD + '''
    fn main() {
        let o = Command::new("sh").arg("-c").arg("echo \\"MY=$MY HOME_SET=${HOME:+yes} PWD=$(basename $PWD)\\"").env("MY", "from-rust").current_dir("/tmp").output().unwrap(); println!("继承环境 + env + current_dir:{}", String::from_utf8_lossy(&o.stdout).trim());
        let o = Command::new("/bin/sh").arg("-c").arg("echo \\"MY=$MY HOME_SET=${HOME:+yes}\\"").env_clear().env("MY", "only").output().unwrap(); println!("env_clear 之后只剩手动设置的:{}", String::from_utf8_lossy(&o.stdout).trim());
        let o = Command::new("sh").arg("-c").arg("echo \\"HOME_SET=${HOME:+yes}\\"").env_remove("HOME").output().unwrap(); println!("env_remove(\\"HOME\\"):{}", String::from_utf8_lossy(&o.stdout).trim());
    }
''', quiet_src=True); R['env'] = r['out']
print()
print('== 六:不 wait 的子进程会变成僵尸进程(Child 被 drop 不会回收);用 ps 看状态')
r = tryit('u145f', HEAD + '''
    fn state(pid: u32) -> String { let o = Command::new("ps").args(["-o", "stat=", "-p", &pid.to_string()]).output().unwrap(); String::from_utf8_lossy(&o.stdout).trim().to_string() }
    fn main() {
        let c = Command::new("true").spawn().unwrap(); let pid = c.id(); thread::sleep(Duration::from_millis(300));
        println!("子进程 true 已经退出,父进程没有 wait,ps 状态:{:?}(Z = 僵尸)", state(pid)); drop(c);
        println!("drop(Child) 之后状态:{:?}(drop 不会 wait)", state(pid));
        let mut c = Command::new("true").spawn().unwrap(); let pid = c.id(); thread::sleep(Duration::from_millis(300)); let st = c.wait().unwrap(); println!("调用 wait() 之后:退出状态 {:?},ps 状态 {:?}(已被回收,不再存在)", st.code(), state(pid));
    }
''', quiet_src=True); R['zombie'] = r['out']
save('u145', R)
