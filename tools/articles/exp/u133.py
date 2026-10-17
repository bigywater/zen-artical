import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u133'); R = {}
HEAD = '''
    #![allow(unused)]
    use std::{fs::{self, File}, io::{self, BufWriter, LineWriter, Write}, cell::Cell, path::PathBuf, time::Instant};
    fn tmp(name: &str) -> PathBuf { let d = std::env::temp_dir().join("u133"); fs::create_dir_all(&d).unwrap(); d.join(name) }
    struct Counting<W> { inner: W, calls: Cell<u64>, bytes: Cell<u64> }
    impl<W: Write> Write for Counting<W> { fn write(&mut self, b: &[u8]) -> io::Result<usize> { self.calls.set(self.calls.get() + 1); self.bytes.set(self.bytes.get() + b.len() as u64); self.inner.write(b) } fn flush(&mut self) -> io::Result<()> { self.inner.flush() } }
'''
print('== 一:数底层 write 调用:写 10 万个小片段(每个 12 字节),无缓冲 vs BufWriter vs LineWriter')
r = tryit('u133a', HEAD + '''
    fn main() {
        let n = 100_000;
        let mut c = Counting { inner: File::create(tmp("a.txt")).unwrap(), calls: Cell::new(0), bytes: Cell::new(0) };
        for i in 0..n { writeln!(c, "row {:07}", i).unwrap(); }
        println!("无缓冲 File:writeln! 10 万次 → 底层 write 调用 {} 次,共 {} 字节", c.calls.get(), c.bytes.get());
        let c = Counting { inner: File::create(tmp("b.txt")).unwrap(), calls: Cell::new(0), bytes: Cell::new(0) };
        let mut w = BufWriter::new(c); let cap = w.capacity(); for i in 0..n { writeln!(w, "row {:07}", i).unwrap(); } w.flush().unwrap();
        println!("BufWriter(默认容量 {}):底层 write 调用 {} 次,共 {} 字节", cap, w.get_ref().calls.get(), w.get_ref().bytes.get());
        let c = Counting { inner: File::create(tmp("c.txt")).unwrap(), calls: Cell::new(0), bytes: Cell::new(0) };
        let mut w = LineWriter::new(c); for i in 0..n { writeln!(w, "row {:07}", i).unwrap(); } w.flush().unwrap();
        println!("LineWriter(每遇到换行就刷新):底层 write 调用 {} 次", w.get_ref().calls.get());
        for cap in [64usize, 1024, 1 << 20] { let c = Counting { inner: File::create(tmp("d.txt")).unwrap(), calls: Cell::new(0), bytes: Cell::new(0) }; let mut w = BufWriter::with_capacity(cap, c); for i in 0..n { writeln!(w, "row {:07}", i).unwrap(); } w.flush().unwrap(); println!("  BufWriter::with_capacity({:>7}):底层 write 调用 {:>6} 次", cap, w.get_ref().calls.get()); }
    }
''', quiet_src=True); R['calls'] = r['out']
print()
print('== 二:耗时:写 100 万行(release,各 3 次取最小):无缓冲 File / BufWriter / 先拼成一个 String 再 fs::write / stdout')
r = tryit('u133b', HEAD + '''
    fn best<F: FnMut()>(mut f: F) -> f64 { let mut b = f64::MAX; for _ in 0..3 { let t = Instant::now(); f(); b = b.min(t.elapsed().as_secs_f64() * 1e3); } b }
    fn main() {
        let n = 1_000_000;
        let t_un = { let m = 100_000; let t = best(|| { let mut f = File::create(tmp("e.txt")).unwrap(); for i in 0..m { writeln!(f, "row {:07}", i).unwrap(); } }); t * (n as f64 / m as f64) };
        let t_bw = best(|| { let mut w = BufWriter::new(File::create(tmp("f.txt")).unwrap()); for i in 0..n { writeln!(w, "row {:07}", i).unwrap(); } });
        let t_bw1m = best(|| { let mut w = BufWriter::with_capacity(1 << 20, File::create(tmp("f.txt")).unwrap()); for i in 0..n { writeln!(w, "row {:07}", i).unwrap(); } });
        let t_str = best(|| { let mut s = String::with_capacity(13_000_000); for i in 0..n { use std::fmt::Write as _; writeln!(s, "row {:07}", i).unwrap(); } fs::write(tmp("g.txt"), s).unwrap(); });
        println!("无缓冲 File(10 万行实测折算到 100 万行): {:>9.1} ms", t_un);
        println!("BufWriter 默认容量:                      {:>9.1} ms", t_bw);
        println!("BufWriter 1 MiB 容量:                    {:>9.1} ms", t_bw1m);
        println!("先拼成 String 再一次 fs::write:           {:>9.1} ms", t_str);
    }
''', quiet_src=True, release=True); R['bench'] = r['out']
print()
print('== 三:stdout 的耗时:println!、手动锁住 stdout、再套 BufWriter,写 20 万行到 /dev/null(release,各 3 次取最小)')
r = tryit('u133c', HEAD + '''
    fn main() {
        let mode = std::env::args().nth(1).unwrap(); let n = 200_000;
        match mode.as_str() {
            "println" => { for i in 0..n { println!("row {:07}", i); } }
            "locked" => { let out = io::stdout(); let mut l = out.lock(); for i in 0..n { writeln!(l, "row {:07}", i).unwrap(); } }
            _ => { let mut w = BufWriter::new(io::stdout().lock()); for i in 0..n { writeln!(w, "row {:07}", i).unwrap(); } }
        }
    }
''', quiet_src=True, release=True, show_run=False)
R['stdout'] = {}
for mode in ('println', 'locked', 'bufwriter'):
    best = 9e9
    for _ in range(3):
        t = time.perf_counter(); p = subprocess.run(f'{r["bin"]} {mode} > /dev/null', shell=True); best = min(best, (time.perf_counter() - t) * 1e3)
    R['stdout'][mode] = round(best, 1); print(f'  {mode:<10} 写 20 万行到 /dev/null:{best:>7.1f} ms')
print()
print('== 四:丢数据:BufWriter 在 drop 时会刷新;但 process::exit / panic=abort / mem::forget 不会运行 drop,缓冲区里的数据就丢了')
r = tryit('u133d', HEAD + '''
    fn main() {
        let mode = std::env::args().nth(1).unwrap(); let p = tmp(&format!("lost_{}.txt", mode));
        let mut w = BufWriter::new(File::create(&p).unwrap());
        for i in 0..1000 { writeln!(w, "row {:07}", i).unwrap(); }
        match mode.as_str() { "drop" => { drop(w); } "flush_then_exit" => { w.flush().unwrap(); std::process::exit(0); } "exit" => { std::process::exit(0); } _ => { std::mem::forget(w); } }
    }
''', quiet_src=True, show_run=False)
R['lost'] = {}
for mode in ('drop', 'flush_then_exit', 'exit', 'forget'):
    subprocess.run([str(r['bin']), mode]); sz = os.path.getsize(os.path.join(os.environ.get('TMPDIR', '/tmp'), 'u133', f'lost_{mode}.txt')) if os.path.exists(os.path.join(os.environ.get('TMPDIR', '/tmp'), 'u133', f'lost_{mode}.txt')) else -1
    R['lost'][mode] = sz; print(f'  {mode:<16} 写入 1000 行(共 12000 字节)后,文件大小 {sz} 字节')
save('u133', R)
