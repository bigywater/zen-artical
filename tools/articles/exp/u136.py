import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u136'); R = {}
DEPS = 'memmap2 = "0.9"'
def go(name, code, release=True, args=(), timeout=120):
    d = proj(name, {'src/main.rs': code}, deps=DEPS); rc, o = cargo(['build'] + (['--release'] if release else []) + ['--quiet'], d, timeout=900)
    if rc != 0: print('  编译失败:', o[:500]); return None
    rc, so, se, _ = run(TG / ('release' if release else 'debug') / name, *args, timeout=timeout); return rc, so.rstrip(), se.rstrip()
PRE = '''
    #![allow(unused)]
    use std::{fs::{self, File, OpenOptions}, io::{Read, Write, Seek, SeekFrom}, path::PathBuf, time::Instant};
    use memmap2::{Mmap, MmapMut};
    fn tmp(name: &str) -> PathBuf { let d = std::env::temp_dir().join("u136"); fs::create_dir_all(&d).unwrap(); d.join(name) }
    fn rss_mb() -> f64 { let o = std::process::Command::new("ps").args(["-o", "rss=", "-p", &std::process::id().to_string()]).output().unwrap(); String::from_utf8_lossy(&o.stdout).trim().parse::<f64>().unwrap() / 1024.0 }
'''
print('== 一:映射文件后当作 &[u8] 来读;修改 MmapMut 并 flush 后,文件内容真的变了')
rc, o, e = go('u136a', PRE + '''
    fn main() {
        let p = tmp("a.bin"); fs::write(&p, b"hello mmap world").unwrap();
        let f = File::open(&p).unwrap(); let m = unsafe { Mmap::map(&f).unwrap() };
        println!("映射 {} 字节,当作 &[u8] 读:{:?}", m.len(), std::str::from_utf8(&m[6..10]).unwrap());
        let f = OpenOptions::new().read(true).write(true).open(&p).unwrap(); let mut mm = unsafe { MmapMut::map_mut(&f).unwrap() };
        mm[0..5].copy_from_slice(b"HELLO"); mm.flush().unwrap(); drop(mm);
        println!("通过 MmapMut 改前 5 字节并 flush 后,用普通 fs::read 读到:{:?}", String::from_utf8(fs::read(&p).unwrap()).unwrap());
    }
''')
print('\n'.join('  ' + l for l in o.splitlines())); R['basic'] = o
print()
print('== 二:惰性加载:映射一个 1 GiB 的文件(稀疏文件),只触碰其中一个页;进程的常驻内存(RSS)随触碰的页增长')
rc, o, e = go('u136b', PRE + '''
    fn main() {
        let p = tmp("big.bin"); let f = OpenOptions::new().read(true).write(true).create(true).truncate(true).open(&p).unwrap(); f.set_len(1 << 30).unwrap();
        let r0 = rss_mb(); let mut m = unsafe { MmapMut::map_mut(&f).unwrap() };
        println!("映射 1 GiB(set_len 创建的稀疏文件)之后 RSS 从 {:.1} MB 变成 {:.1} MB(映射本身不占物理内存)", r0, rss_mb());
        m[0] = 1; m[500 << 20] = 2; println!("写了 2 个字节(分别在文件头和 500 MiB 处)之后 RSS = {:.1} MB", rss_mb());
        let mut s = 0u64; for i in (0..m.len()).step_by(4096) { s += m[i] as u64; } std::hint::black_box(s);
        println!("每 4 KiB 读一个字节,遍历全部 {} 个页之后 RSS = {:.1} MB", m.len() / 4096, rss_mb());
        drop(m); drop(f); fs::remove_file(&p).unwrap();
    }
''')
print('\n'.join('  ' + l for l in o.splitlines())); R['lazy'] = o
print()
print('== 三:读 256 MiB 文件求和(页缓存已热,release,各 3 次取最小):mmap vs read_to_end vs BufReader 分块读')
rc, o, e = go('u136c', PRE + '''
    fn best<F: FnMut() -> u64>(mut f: F) -> (f64, u64) { let mut b = f64::MAX; let mut r = 0; for _ in 0..3 { let t = Instant::now(); r = std::hint::black_box(f()); b = b.min(t.elapsed().as_secs_f64() * 1e3); } (b, r) }
    fn sum(b: &[u8]) -> u64 { std::hint::black_box(b).chunks(8).map(|c| c.iter().map(|x| *x as u64).sum::<u64>()).sum() }
    fn main() {
        let p = tmp("data.bin"); let n = 256usize << 20;
        { let mut f = File::create(&p).unwrap(); let chunk: Vec<u8> = (0..1 << 20).map(|i| (i % 251) as u8).collect(); for _ in 0..n >> 20 { f.write_all(&chunk).unwrap(); } }
        let (t1, a) = best(|| { let f = File::open(&p).unwrap(); let m = unsafe { Mmap::map(&f).unwrap() }; let r = sum(&m[..]); std::hint::black_box(&m); r });
        let (t2, b) = best(|| { let mut v = Vec::new(); File::open(&p).unwrap().read_to_end(&mut v).unwrap(); sum(&v) });
        let (t3, c) = best(|| { let mut f = File::open(&p).unwrap(); let mut buf = vec![0u8; 1 << 20]; let mut s = 0; loop { let k = f.read(&mut buf).unwrap(); if k == 0 { break; } s += sum(&buf[..k]); } s });
        println!("mmap 映射(含 map 调用)后直接遍历:{:>7.1} ms  (校验 {})", t1, a); println!("read_to_end 读进 Vec 再遍历:    {:>7.1} ms  (校验 {})", t2, b); println!("1 MiB 缓冲循环读边读边算:       {:>7.1} ms  (校验 {})", t3, c);
        fs::remove_file(&p).unwrap();
    }
''')
print('\n'.join('  ' + l for l in o.splitlines())); R['seq'] = o
print()
print('== 四:随机访问:在 256 MiB 文件里随机读 20 万个 8 字节(页缓存已热):mmap 对 seek + read')
rc, o, e = go('u136d', PRE + '''
    fn main() {
        let p = tmp("rand.bin"); let n = 256usize << 20;
        { let mut f = File::create(&p).unwrap(); let chunk: Vec<u8> = (0..1 << 20).map(|i| (i % 251) as u8).collect(); for _ in 0..n >> 20 { f.write_all(&chunk).unwrap(); } }
        let mut x = 88172645463325252u64; let mut rng = move || { x ^= x << 13; x ^= x >> 7; x ^= x << 17; x };
        let offs: Vec<usize> = (0..200_000).map(|_| (rng() as usize % (n - 8)) & !7).collect();
        let f = File::open(&p).unwrap(); let m = unsafe { Mmap::map(&f).unwrap() };
        let mut best = [f64::MAX; 2]; let mut chk = [0u64; 2];
        for _ in 0..3 {
            let t = Instant::now(); let mut s = 0u64; for &o in &offs { s = s.wrapping_add(u64::from_le_bytes(m[o..o + 8].try_into().unwrap())); } chk[0] = s; best[0] = best[0].min(t.elapsed().as_secs_f64() * 1e3);
            let mut f = File::open(&p).unwrap(); let t = Instant::now(); let mut s = 0u64; let mut b = [0u8; 8]; for &o in &offs { f.seek(SeekFrom::Start(o as u64)).unwrap(); f.read_exact(&mut b).unwrap(); s = s.wrapping_add(u64::from_le_bytes(b)); } chk[1] = s; best[1] = best[1].min(t.elapsed().as_secs_f64() * 1e3);
        }
        println!("mmap 随机读 20 万次:        {:>7.2} ms  (校验 {})", best[0], chk[0]); println!("seek + read_exact 20 万次:  {:>7.2} ms  (校验 {})", best[1], chk[1]);
        fs::remove_file(&p).unwrap();
    }
''')
print('\n'.join('  ' + l for l in o.splitlines())); R['rand'] = o
print()
print('== 五:映射的文件被截断:再访问被截掉的页 → SIGBUS(进程被信号杀死),这是 mmap 不能用「安全」包装的原因')
rc, o, e = go('u136e', PRE + '''
    fn main() {
        let p = tmp("trunc.bin"); fs::write(&p, vec![7u8; 1 << 16]).unwrap();
        let f = OpenOptions::new().read(true).write(true).open(&p).unwrap(); let m = unsafe { Mmap::map(&f).unwrap() };
        println!("映射后读 m[60000] = {}", m[60000]);
        f.set_len(4096).unwrap(); println!("把文件截断到 4096 字节(另一个句柄/进程也可能这么做)");
        println!("再读 m[60000] = {}", std::hint::black_box(m[60000]));
    }
''')
print(f'  退出码 {rc}(负数 = 被信号终止:{-rc if rc < 0 else "-"}),stdout:'); print('\n'.join('    ' + l for l in o.splitlines())); R['sigbus'] = [rc, o]
save('u136', R)
