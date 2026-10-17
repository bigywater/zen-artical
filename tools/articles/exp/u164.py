import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
import statistics
tee('u164'); R = {}
BIN = RS / 'bin'; BIN.mkdir(exist_ok=True)
def nrustc(name, code, san=None, release=False, flags=()):
    f = src_file(name, code); out = BIN / name
    cmd = ['rustc', '--edition=2024', '--color=never', '-C', 'debuginfo=1', '-Zunstable-options', '-C', 'symbol-mangling-version=legacy', str(f), '-o', str(out)] + (['-O'] if release else []) + (['-Zsanitizer=' + san] if san else []) + list(flags)
    rc, o, e = sh(cmd, env=ENVN, timeout=300); return rc == 0, tidy(o + e), out
def trim(txt, frames=3, shadow=False):
    out, k = [], 0
    for l in txt.split('\n'):
        m = re.match(r'\s+#(\d+) ', l)
        if m:
            k += 1
            if k > frames: continue
            l = re.sub(r' \(\S+:arm64\+0x[0-9a-f]+\)$', '', l); l = re.sub(r'0x[0-9a-f]{9,} in ', '', l)
            l = re.sub(r'(?<=\s)\$?(_ZN)?', lambda m_: m_.group(0), l)
        else: k = 0
        if not shadow and (l.startswith(('Shadow bytes', '  0x', '=>0x', 'Shadow byte legend', '  Addressable', '  Partially', '  Heap left', '  Freed heap', '  Stack ', '  Global ', '  Poisoned', '  Container', '  Array cookie', '  Intra object', '  ASan internal', '  Left alloca', '  Right alloca', '  Shadow gap')) or l.startswith('=>')): continue
        out.append(l.rstrip())
    return '\n'.join(x for x in out if x.strip())
def pr(txt, n=26, ind='    '):
    L = txt.split('\n'); print('\n'.join(ind + l[:200] for l in L[:n]))
    if len(L) > n: print(f'{ind}…(共 {len(L)} 行)')
def asan(key, code, env=None, n=26, frames=3, release=False, show_src=True):
    if show_src: print('  源码:'); print('\n'.join('    ' + l for l in numbered(code).split('\n')))
    ok, diag, binp = nrustc('u164_' + key, code, 'address', release)
    if not ok: print('  编译失败:'); pr(diag, 12); R[key] = dict(compile_fail=diag); return
    e = dict(ENVN, **(env or {})); r = subprocess.run([str(binp)], capture_output=True, text=True, env=e, timeout=60)
    txt = trim(clean(r.stdout + r.stderr), frames); print(f'  -Zsanitizer=address 编译运行:退出码 {r.returncode}'); pr(txt, n)
    R[key] = dict(rc=r.returncode, out=txt.split('\n')[:n]); return r
print('== 一:释放后使用:ASan 报 heap-use-after-free,并给出读取、释放、分配三处调用栈')
asan('uaf', '''
    fn main() {
        let v = vec![1, 2, 3];
        let p = v.as_ptr();
        drop(v);
        println!("{}", unsafe { *p });
    }
''', n=30)
print()
print('== 二:堆越界读:用裸指针读 Vec 之后一个元素;对比安全代码的下标越界(直接 panic,与 sanitizer 无关)')
asan('oob', '''
    use std::hint::black_box;
    fn main() {
        let v = vec![10u32, 20, 30];
        let i = black_box(3);
        let x = unsafe { *v.as_ptr().add(i) };
        println!("{}", x);
    }
''', n=16)
asan('safe_oob', '''
    use std::hint::black_box;
    fn main() {
        let v = vec![10u32, 20, 30];
        let i = black_box(3);
        println!("{}", v[i]);
    }
''', n=8, show_src=True)
print()
print('== 三:栈越界与重复释放')
asan('stack', '''
    use std::hint::black_box;
    fn main() {
        let a = [1u8, 2, 3, 4];
        let p = a.as_ptr();
        let i = black_box(4);
        println!("{}", unsafe { *p.add(i) });
    }
''', n=14)
asan('dfree', '''
    fn main() {
        let b = Box::new(5u32);
        let p = Box::into_raw(b);
        unsafe { drop(Box::from_raw(p)); drop(Box::from_raw(p)); }
    }
''', n=16)
print()
print('== 四:内存泄漏:ASan 在 macOS arm64 上能检测吗(设置 ASAN_OPTIONS=detect_leaks=1)')
asan('leak', '''
    fn main() {
        let b = Box::new([1u8; 16]);
        std::mem::forget(b);
        println!("done");
    }
''', env={'ASAN_OPTIONS': 'detect_leaks=1'}, n=10)
ok, diag, binp = nrustc('u164_leakl', 'fn main() { std::mem::forget(Box::new(1)); }', 'leak'); print('  -Zsanitizer=leak 编译:', 'ok' if ok else diag.split('\n')[0]); R['leak_san'] = diag.split('\n')[0] if not ok else 'ok'
ok, diag, binp = nrustc('u164_mem', 'fn main() { }', 'memory'); print('  -Zsanitizer=memory 编译:', 'ok' if ok else diag.split('\n')[0]); R['mem_san'] = diag.split('\n')[0] if not ok else 'ok'
print()
print('== 五:外部 C 函数造成的越界:Rust 里调用 libc 的 memcpy 往 8 字节的 Vec 里写 16 字节(Miri 看不见 FFI,ASan 拦截了 memcpy)')
asan('ffi', '''
    use std::hint::black_box;
    unsafe extern "C" { fn memcpy(dst: *mut u8, src: *const u8, n: usize) -> *mut u8; }
    fn main() {
        let mut dst = vec![0u8; 8];
        let src = [7u8; 16];
        unsafe { memcpy(dst.as_mut_ptr(), src.as_ptr(), black_box(16)) };
        println!("{}", dst[0]);
    }
''', n=18)
print()
print('== 六:ThreadSanitizer:检测数据竞争;它要求连标准库一起用同一个选项重新编译(-Zbuild-std)')
tb = RS / 'proj' / 'u164t'; shutil.rmtree(tb, ignore_errors=True); (tb / 'src').mkdir(parents=True)
(tb / 'Cargo.toml').write_text('[package]\nname = "ts"\nversion = "0.1.0"\nedition = "2024"\n')
tcode = '''
    use std::thread;
    struct P(*mut u32);
    unsafe impl Send for P {}
    fn main() {
        let mut x = 0u32;
        let p = P(&mut x as *mut u32);
        let h = thread::spawn(move || {
            let p = p;
            for _ in 0..1000 { unsafe { *p.0 += 1 }; }
        });
        for _ in 0..1000 { unsafe { *(&mut x as *mut u32) += 1 }; }
        h.join().unwrap();
        println!("x = {}", x);
    }
'''
(tb / 'src' / 'main.rs').write_text(show(tcode) + '\n'); print('  源码:'); print('\n'.join('    ' + l for l in numbered(tcode).split('\n')))
rc, out = ncargo(['+nightly', 'run', '-q', '--target', 'aarch64-apple-darwin'], tb, extra={'RUSTFLAGS': '-Zsanitizer=thread -Zunstable-options -Csymbol-mangling-version=legacy'})
print('  只给自己的 crate 加 -Zsanitizer=thread(不重编标准库):退出码', rc); pr(out, 6); R['tsan_nostd'] = [rc, out.split('\n')[:6]]
t0 = time.perf_counter(); rc, out = ncargo(['+nightly', 'run', '-q', '-Zbuild-std', '--target', 'aarch64-apple-darwin'], tb, extra={'RUSTFLAGS': '-Zsanitizer=thread -Zunstable-options -Csymbol-mangling-version=legacy'}); dt = time.perf_counter() - t0
txt = trim(out, frames=3); print(f'  加 -Zbuild-std(含重编标准库,共 {dt:.0f} 秒):退出码 {rc}'); pr(txt, 40); R['tsan'] = dict(rc=rc, out=txt.split('\n')[:40], secs=round(dt))
print()
print('== 七:代价:同一个程序用 -O 编译,原生 vs ASan(每种运行 7 次取中位数;结果 black_box)')
prog = '''
    use std::hint::black_box;
    use std::time::Instant;
    fn main() {
        let n = 20_000_000usize;
        let v: Vec<u32> = (0..n as u32).collect();
        let t = Instant::now();
        let mut s = 0u64;
        for i in 0..v.len() { s += unsafe { *v.as_ptr().add(black_box(i)) } as u64; }
        black_box(s);
        let a = t.elapsed().as_secs_f64() * 1000.0;
        let t = Instant::now();
        for i in 0..2_000_000u32 { let b = Box::new([i; 4]); black_box(&b); }
        let b = t.elapsed().as_secs_f64() * 1000.0;
        println!("{:.2} {:.2}", a, b);
    }
'''
print('  源码:'); print('\n'.join('    ' + l for l in numbered(prog).split('\n')))
res = {}
for label, san in (('原生 -O', None), ('ASan -O', 'address')):
    ok, diag, binp = nrustc('u164_cost_' + (san or 'nat'), prog, san, release=True); assert ok, diag
    A, B, W = [], [], []
    for _ in range(7):
        rr = subprocess.run(['/usr/bin/time', '-l', str(binp)], capture_output=True, text=True, env=ENVN)
        a, b = map(float, rr.stdout.split()); A.append(a); B.append(b)
        W.append(int(re.search(r'(\d+)\s+maximum resident set size', rr.stderr).group(1)) / (1 << 20))
    res[label] = dict(loop=statistics.median(A), alloc=statistics.median(B), rss=statistics.median(W), size=binp.stat().st_size)
print(f'  {"":10} {"遍历 2000 万元素 (ms)":>22} {"200 万次 Box::new (ms)":>24} {"峰值内存 (MiB)":>16} {"可执行文件 (KiB)":>18}')
for k, v in res.items(): print(f'  {k:10} {v["loop"]:>22.1f} {v["alloc"]:>24.1f} {v["rss"]:>16.0f} {v["size"] / 1024:>18.0f}')
R['cost'] = res
save('u164', R)
