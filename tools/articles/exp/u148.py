import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u148'); R = {}
ok, d, b, _ = rustc('u148', '''
    use std::{fs::{self, File, OpenOptions, TryLockError}, io::{Read, Write}, time::{Duration, Instant}, thread};
    fn open(p: &str) -> File { OpenOptions::new().read(true).write(true).create(true).open(p).unwrap() }
    fn state(r: Result<(), TryLockError>) -> &'static str { match r { Ok(()) => "拿到", Err(TryLockError::WouldBlock) => "WouldBlock(被别人持有)", Err(TryLockError::Error(_)) => "出错" } }
    fn main() {
        let a: Vec<String> = std::env::args().collect(); let mode = a[1].as_str(); let path = a[2].as_str();
        match mode {
            "hold_x" => { let f = open(path); f.lock().unwrap(); println!("READY"); use std::io::Write; std::io::stdout().flush().unwrap(); thread::sleep(Duration::from_millis(a[3].parse().unwrap())); println!("释放前退出"); }
            "hold_s" => { let f = open(path); f.lock_shared().unwrap(); println!("READY"); use std::io::Write; std::io::stdout().flush().unwrap(); thread::sleep(Duration::from_millis(a[3].parse().unwrap())); }
            "try_x" => { let f = open(path); println!("try_lock(独占):{}", state(f.try_lock())); }
            "try_s" => { let f = open(path); println!("try_lock_shared(共享):{}", state(f.try_lock_shared())); }
            "block_x" => { let f = open(path); let t = Instant::now(); f.lock().unwrap(); println!("lock(独占)阻塞了约 {} ms 才拿到", (t.elapsed().as_millis() / 50) * 50); }
            "write_ignore" => { let mut f = OpenOptions::new().write(true).open(path).unwrap(); f.write_all(b"written without taking the lock").unwrap(); println!("没有加锁直接写文件:成功(锁是建议性的)"); }
            _ => {}
        }
    }
''', release=True); assert ok, d
p = str(RS / 'u148.lock'); open(p, 'w').write('')
def start(mode, ms): proc = subprocess.Popen([str(b), mode, p, str(ms)], stdout=subprocess.PIPE, text=True); assert proc.stdout.readline().strip() == 'READY'; return proc
def one(mode): r = subprocess.run([str(b), mode, p], capture_output=True, text=True); return r.stdout.strip()
print('== 一:另一个进程持有独占锁时:try_lock / try_lock_shared 都得到 WouldBlock;lock() 会阻塞到对方释放')
h = start('hold_x', 600); R['x'] = {}
for m in ('try_x', 'try_s'): o = one(m); print(f'  {o}'); R['x'][m] = o
t0 = time.perf_counter(); o = one('block_x'); print(f'  {o}(持有者睡 600 ms 后退出,实际等待 {int((time.perf_counter() - t0) * 1000)} ms)'); R['x']['block'] = o
h.wait()
print()
print('== 二:持有共享锁时:再来共享锁成功(多个读者并存),独占锁 WouldBlock')
h = start('hold_s', 600); R['s'] = {}
for m in ('try_s', 'try_x'): o = one(m); print(f'  {o}'); R['s'][m] = o
h.wait()
print()
print('== 三:持有者进程被 kill -9 之后,锁自动释放(随进程终止自动释放)')
h = start('hold_x', 30000); print(f'  持有者运行中:{one("try_x")}')
h.kill(); h.wait(); time.sleep(0.2); o = one('try_x'); print(f'  kill -9 持有者之后:{o}'); R['kill'] = o
print()
print('== 四:锁是建议性的:不加锁的进程仍然可以写文件')
h = start('hold_x', 600); o = one('write_ignore'); print(f'  持有独占锁期间,另一个进程 {o}'); print(f'  文件内容:{open(p).read()!r}'); R['advisory'] = [o, open(p).read()]; h.wait()
print()
print('== 五:同一个进程里,两次 open 得到两个独立的文件句柄,锁互相冲突(锁跟着打开的文件句柄,不是只跟着进程);一个 File 重复加锁是幂等的')
ok, d, b2, _ = rustc('u148b', '''
    use std::{fs::{File, OpenOptions, TryLockError}};
    fn main() {
        let p = std::env::args().nth(1).unwrap();
        let a = OpenOptions::new().read(true).write(true).open(&p).unwrap(); let b = OpenOptions::new().read(true).write(true).open(&p).unwrap();
        a.lock().unwrap(); println!("句柄 a 拿到独占锁");
        println!("同一进程里的句柄 b try_lock:{}", match b.try_lock() { Ok(()) => "拿到".to_string(), Err(TryLockError::WouldBlock) => "WouldBlock".to_string(), Err(e) => format!("{:?}", e) });
        println!("句柄 a 再 try_lock 一次(已经持有):{}", match a.try_lock() { Ok(()) => "成功(幂等)".to_string(), Err(e) => format!("{:?}", e) });
        a.unlock().unwrap(); println!("a.unlock() 之后 b try_lock:{}", match b.try_lock() { Ok(()) => "拿到".to_string(), Err(e) => format!("{:?}", e) });
        drop(b); println!("b 被 drop(关闭文件)时锁也随之释放:再开一个句柄 c 能拿到锁:{}", OpenOptions::new().read(true).write(true).open(&p).unwrap().try_lock().is_ok());
    }
''', release=True); assert ok, d
r = subprocess.run([str(b2), p], capture_output=True, text=True); print('\n'.join('  ' + l for l in r.stdout.strip().splitlines())); R['same'] = r.stdout.strip().splitlines()
os.remove(p)
save('u148', R)
