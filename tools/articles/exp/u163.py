import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u163'); R = {}
base = RS / 'proj' / 'u163'; shutil.rmtree(base, ignore_errors=True); (base / 'src').mkdir(parents=True)
(base / 'Cargo.toml').write_text('[package]\nname = "mt"\nversion = "0.1.0"\nedition = "2024"\n')
def miri(code, flags='', timeout=600):
    (base / 'src' / 'main.rs').write_text(show(code) + '\n')
    t0 = time.perf_counter(); rc, out = ncargo(['miri', 'run', '-q'], base, timeout=timeout, extra={'MIRIFLAGS': flags}); dt = time.perf_counter() - t0
    L = [l for l in out.split('\n') if not l.startswith(('Preparing a sysroot', '   Compiling', '    Finished', '     Running'))]
    return rc, '\n'.join(L).strip(), dt
def native(name, code, release=False, timeout=60):
    ok, diag, binp, _ = rustc(name, code, release=release)
    if not ok: return None, diag, 0
    t0 = time.perf_counter(); rc, o, e, t = run(binp, timeout=timeout); return rc, (o + e).strip(), t
def pr(txt, n=30, ind='    '):
    L = txt.split('\n'); print('\n'.join(ind + l[:230] for l in L[:n])); 
    if len(L) > n: print(f'{ind}…(共 {len(L)} 行)')
def case(key, code, flags='', n=22, rel=False):
    print('  源码:'); print('\n'.join('    ' + l for l in numbered(code).split('\n')))
    rc, o, t = native('u163_' + key, code, release=rel); print(f'  普通编译运行(brew rustc 1.98.1 稳定版):退出码 {rc}'); pr(o or '(无输出)', 6)
    mrc, mo, mt = miri(code, flags); print(f'  cargo miri run{(" (MIRIFLAGS=" + flags + ")") if flags else ""}:退出码 {mrc}'); pr(mo, n)
    R[key] = dict(native_rc=rc, native=o, miri_rc=mrc, miri=mo.split('\n')[:n], miri_secs=round(mt, 1)); return R[key]
print('== 一:释放后使用(use-after-free):普通运行「成功」,Miri 精确指出分配、释放、使用三处')
case('uaf', '''
    fn main() {
        let v = vec![1, 2, 3];
        let p = v.as_ptr();
        drop(v);
        println!("{}", unsafe { *p });
    }
''')
print()
print('== 二:越界读取:用裸指针读 Vec 之外的一个元素')
case('oob', '''
    fn main() {
        let v = vec![10u32, 20, 30];
        let x = unsafe { *v.as_ptr().add(3) };
        println!("{}", x);
    }
''')
print()
print('== 三:读未初始化内存,以及非法的值(bool 里装 2)')
case('uninit', '''
    use std::mem::MaybeUninit;
    fn main() {
        let x: u32 = unsafe { MaybeUninit::<u32>::uninit().assume_init() };
        println!("{}", x);
    }
''')
case('badbool', '''
    fn main() {
        let b: bool = unsafe { std::mem::transmute::<u8, bool>(2) };
        println!("{}", b);
    }
''')
print()
print('== 四:未对齐引用:把 u8 缓冲区中偏移 1 的地址当作 &u32')
case('align', '''
    fn main() {
        let buf = [0u8; 8];
        let p = unsafe { buf.as_ptr().add(1) } as *const u32;
        let r: &u32 = unsafe { &*p };
        println!("{}", r);
    }
''')
print()
print('== 五:别名规则(Stacked Borrows):用了已被「重新借用」作废的旧指针;再用 Tree Borrows 模型跑同一段代码')
code = '''
    fn main() {
        let mut x = 10;
        let raw = &mut x as *mut i32;
        let r1 = unsafe { &mut *raw };
        let r2 = unsafe { &mut *raw };
        *r2 = 20;
        *r1 = 30;
        println!("{}", x);
    }
'''
case('alias_sb', code)
print('  —— 同一段代码,换成 Tree Borrows 模型:')
mrc, mo, mt = miri(code, '-Zmiri-tree-borrows'); print(f'  MIRIFLAGS=-Zmiri-tree-borrows:退出码 {mrc}'); pr(mo, 22); R['alias_tb'] = dict(rc=mrc, out=mo.split('\n')[:22])
print()
print('== 六:数据竞争:两个线程用裸指针无同步地写同一个变量;普通运行结果「看起来正常」,Miri 检测出竞争')
code = '''
    use std::thread;
    struct P(*mut u32);
    unsafe impl Send for P {}
    fn main() {
        let mut x = 0u32;
        let p = P(&mut x as *mut u32);
        let h = thread::spawn(move || {
            let p = p;
            unsafe { *p.0 = 1 };
        });
        unsafe { *(&mut x as *mut u32) = 2 };
        h.join().unwrap();
        println!("x = {}", x);
    }
'''
case('race', code, n=26)
print()
print('== 七:内存泄漏:Miri 在程序结束时列出没有释放的分配')
case('leak', '''
    fn main() {
        let b = Box::new([1u8; 16]);
        std::mem::forget(b);
        let v = vec![1, 2, 3];
        std::mem::forget(v);
        println!("done");
    }
''', n=24)
print()
print('== 八:代价:同一个循环,优化编译的原生程序 vs Miri 解释执行(每个结果都 black_box;Miri 加 -Zmiri-disable-isolation 才用真实时钟)')
print(f'  {"迭代次数":>10} {"原生 -O (ms)":>14} {"Miri 真实 (ms)":>16} {"倍数":>8} {"Miri 默认隔离下程序自己看到的 (ms)":>40}')
R['slow'] = []
import statistics
for n_ in (10_000, 100_000, 1_000_000):
    code = f'''
        use std::hint::black_box;
        use std::time::Instant;
        fn main() {{
            let t = Instant::now();
            let mut s = 0u64;
            for i in 0..black_box({n_}u64) {{ s = s.wrapping_add(black_box(i) * 3 + 1); }}
            black_box(s);
            println!("{{}}", t.elapsed().as_secs_f64() * 1000.0);
        }}
    '''
    nat = []
    for _ in range(5):
        rc, o, _t = native('u163_slow', code, release=True); nat.append(float(o))
    nm = statistics.median(nat)
    mrc, mo, mt = miri(code, '-Zmiri-disable-isolation'); mm = float(mo.split('\n')[-1]) if mrc == 0 else None
    mrc2, mo2, _ = miri(code); virt = float(mo2.split('\n')[-1]) if mrc2 == 0 else None
    print(f'  {n_:>10} {nm:>14.4f} {mm:>16.1f} {mm / max(nm, 1e-6):>8.0f} {virt:>40.1f}'); R['slow'].append([n_, nm, mm, virt])
print()
print('== 九:Miri 能跑什么、不能跑什么:调用系统接口(socket)与 FFI')
code = '''
    use std::net::TcpListener;
    fn main() {
        let l = TcpListener::bind("127.0.0.1:0").unwrap();
        println!("{}", l.local_addr().unwrap());
    }
'''
case('sock', code, n=12)
print('  —— 同一段 socket 代码,加 -Zmiri-disable-isolation:')
mrc, mo, mt = miri(code, '-Zmiri-disable-isolation'); print(f'  退出码 {mrc}'); pr(mo, 12); R['sock_noiso'] = dict(rc=mrc, out=mo.split('\n')[:12])
code = '''
    unsafe extern "C" { fn ffs(i: i32) -> i32; }
    fn main() { println!("{}", unsafe { ffs(8) }); }
'''
case('ffi', code, n=12)
save('u163', R)
