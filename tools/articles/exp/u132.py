import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u132'); R = {}
HEAD = '''
    #![allow(unused)]
    use std::{fs::{self, File}, io::{self, BufRead, BufReader, Read}, cell::Cell, path::PathBuf, time::Instant};
    fn tmp(name: &str) -> PathBuf { let d = std::env::temp_dir().join("u132"); fs::create_dir_all(&d).unwrap(); d.join(name) }
    // 数 read 调用次数的包装器:每次对内层 File 的 read 都算一次系统调用级别的读
    struct Counting<R> { inner: R, calls: Cell<u64>, bytes: Cell<u64> }
    impl<R: Read> Read for Counting<R> { fn read(&mut self, buf: &mut [u8]) -> io::Result<usize> { self.calls.set(self.calls.get() + 1); let n = self.inner.read(buf)?; self.bytes.set(self.bytes.get() + n as u64); Ok(n) } }
    fn make(name: &str, lines: usize) -> PathBuf { let p = tmp(name); let mut s = String::new(); for i in 0..lines { s.push_str(&format!("line number {:07}\\n", i)); } fs::write(&p, s).unwrap(); p }
'''
print('== 一:数一数底层 read 调用:读一个 100 KB 的文件,逐字节 bytes() —— 无缓冲 vs BufReader')
r = tryit('u132a', HEAD + '''
    fn main() {
        let p = make("small.txt", 5000); let size = fs::metadata(&p).unwrap().len();
        let c = Counting { inner: File::open(&p).unwrap(), calls: Cell::new(0), bytes: Cell::new(0) };
        let mut n = 0u64; for b in c.by_ref_hack() {} 
    }
''', quiet_src=True, show_run=False) if False else None
r = tryit('u132a', HEAD + '''
    fn main() {
        let p = make("small.txt", 5000); let size = fs::metadata(&p).unwrap().len();
        let mut c = Counting { inner: File::open(&p).unwrap(), calls: Cell::new(0), bytes: Cell::new(0) };
        let mut n = 0u64; { let mut it = (&mut c).bytes(); while let Some(b) = it.next() { b.unwrap(); n += 1; } }
        println!("无缓冲 File + bytes():文件 {} 字节,逐字节读,底层 read 调用 {} 次(每个字节一次)", size, c.calls.get());
        let c = Counting { inner: File::open(&p).unwrap(), calls: Cell::new(0), bytes: Cell::new(0) };
        let mut br = BufReader::new(c); let cap = br.capacity(); let mut n2 = 0u64; { let mut it = (&mut br).bytes(); while let Some(b) = it.next() { b.unwrap(); n2 += 1; } }
        println!("BufReader::new(默认容量 {} 字节) + bytes():读了同样 {} 字节,底层 read 调用 {} 次", cap, n2, br.get_ref().calls.get());
        for cap in [64usize, 1024, 65536] {
            let c = Counting { inner: File::open(&p).unwrap(), calls: Cell::new(0), bytes: Cell::new(0) }; let mut br = BufReader::with_capacity(cap, c); let mut it = (&mut br).bytes(); while let Some(b) = it.next() { b.unwrap(); } drop(it);
            println!("  with_capacity({:>5}):底层 read 调用 {:>5} 次(约 文件大小 / 容量 = {:.0})", cap, br.get_ref().calls.get(), size as f64 / cap as f64);
        }
    }
''', quiet_src=True); R['calls'] = r['out']
print()
print('== 二:耗时:读 20 MB(100 万行)文件,几种读法(release,各 3 次取最小)')
r = tryit('u132b', HEAD + '''
    use std::hint::black_box;
    fn best<F: FnMut() -> u64>(mut f: F) -> (f64, u64) { let mut b = f64::MAX; let mut r = 0; for _ in 0..3 { let t = Instant::now(); r = std::hint::black_box(f()); b = b.min(t.elapsed().as_secs_f64() * 1e3); } (b, r) }
    fn main() {
        let p = make("big.txt", 1_000_000); let size = fs::metadata(&p).unwrap().len();
        let (t1, a) = best(|| { let mut f = File::open(&p).unwrap(); let mut s = String::new(); f.read_to_string(&mut s).unwrap(); s.lines().count() as u64 });
        let (t2, b) = best(|| { let f = BufReader::new(File::open(&p).unwrap()); f.lines().count() as u64 });
        let (t3, c) = best(|| { let mut f = BufReader::new(File::open(&p).unwrap()); let mut line = String::new(); let mut n = 0; while f.read_line(&mut line).unwrap() > 0 { n += 1; line.clear(); } n });
        let (t4, d) = best(|| { let mut f = BufReader::with_capacity(1 << 20, File::open(&p).unwrap()); let mut line = String::new(); let mut n = 0; while f.read_line(&mut line).unwrap() > 0 { n += 1; line.clear(); } n });
        let (t5, e) = best(|| { let mut f = File::open(&p).unwrap(); let mut buf = [0u8; 1]; let mut n = 0u64; let mut cnt = 0; let _ = &mut n; let mut lim = 200_000; while lim > 0 && f.read(&mut buf).unwrap() == 1 { if buf[0] == b'\\n' { cnt += 1; } lim -= 1; } cnt });
        println!("文件 {} 字节、{} 行", size, a);
        println!("read_to_string 一次读完再 lines():    {:>8.1} ms  (行数 {})", t1, a);
        println!("BufReader::lines()(每行分配一个 String):{:>8.1} ms  (行数 {})", t2, b);
        println!("BufReader + read_line 复用同一个 String:  {:>8.1} ms  (行数 {})", t3, c);
        println!("同上,缓冲区 1 MiB:                  {:>8.1} ms  (行数 {})", t4, d);
        println!("无缓冲 File 逐字节读(只读前 20 万字节){:>8.1} ms  (只读了文件的 {:.1}%,按字节数折算整个文件约 {:.0} ms)", t5, 200000.0 * 100.0 / size as f64, t5 * size as f64 / 200000.0);
    }
''', quiet_src=True, release=True); R['bench'] = r['out']
print()
print('== 三:BufRead 的底层接口:fill_buf / consume;lines() 去掉换行符;read_until;缓冲区里的数据')
r = tryit('u132c', HEAD + '''
    fn main() {
        let data = "alpha\\nbeta\\r\\ngamma"; let mut br = BufReader::with_capacity(8, data.as_bytes());
        let buf = br.fill_buf().unwrap(); println!("fill_buf(缓冲区容量 8)看到 {:?}({} 字节),还没有消费", String::from_utf8_lossy(buf), buf.len());
        br.consume(3); println!("consume(3) 之后 buffer() = {:?}", String::from_utf8_lossy(br.buffer()));
        let mut v = vec![]; br.read_until(b'\\n', &mut v).unwrap(); println!("read_until(\\\\n) 得到 {:?}(包含分隔符)", String::from_utf8_lossy(&v));
        let lines: Vec<String> = BufReader::new(data.as_bytes()).lines().map(|l| l.unwrap()).collect(); println!("lines() 的结果:{:?}(\\\\n 与 \\\\r\\\\n 都被去掉,最后一行没有换行也算一行)", lines);
    }
''', quiet_src=True); R['api'] = r['out']
print()
print('== 四:一次读完整个文件时 BufReader 没有收益:File::read_to_string 与 BufReader::read_to_string 对比')
r = tryit('u132d', HEAD + '''
    fn main() {
        let p = make("mid.txt", 200_000); let mut best = [f64::MAX; 2];
        for _ in 0..5 {
            let t = Instant::now(); let mut s = String::new(); File::open(&p).unwrap().read_to_string(&mut s).unwrap(); best[0] = best[0].min(t.elapsed().as_secs_f64() * 1e3); std::hint::black_box(&s);
            let t = Instant::now(); let mut s = String::new(); BufReader::new(File::open(&p).unwrap()).read_to_string(&mut s).unwrap(); best[1] = best[1].min(t.elapsed().as_secs_f64() * 1e3); std::hint::black_box(&s);
        }
        println!("File::read_to_string {:.2} ms   BufReader::read_to_string {:.2} ms(文件 {} 字节)", best[0], best[1], fs::metadata(&p).unwrap().len());
    }
''', quiet_src=True, release=True); R['whole'] = r['out']
save('u132', R)
