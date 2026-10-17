import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u93'); R = {}
print('== 一:compare_exchange 的语义:期望值匹配才写入;成功返回 Ok(旧值),失败返回 Err(当前值)')
r = tryit('u93a', '''
    use std::sync::atomic::{AtomicU32, Ordering::*};
    fn main() {
        let a = AtomicU32::new(5);
        println!("expect 5 → 9: {:?}  现在 = {}", a.compare_exchange(5, 9, SeqCst, SeqCst), a.load(SeqCst));
        println!("expect 5 → 7: {:?}  现在 = {}(期望不符,不写入,返回当前值)", a.compare_exchange(5, 7, SeqCst, SeqCst), a.load(SeqCst));
        println!("swap(1) 返回旧值 {}  fetch_max(10) 返回旧值 {}  现在 = {}", a.swap(1, SeqCst), a.fetch_max(10, SeqCst), a.load(SeqCst));
    }
''', quiet_src=True); R['basic'] = r['out']
print()
print('== 二:CAS 循环实现「读-改-写」:用 compare_exchange_weak 手写 fetch_mul3(没有现成指令的原子乘法);fetch_update 是它的封装')
r = tryit('u93b', '''
    use std::{sync::atomic::{AtomicU64, Ordering::*}, thread};
    fn fetch_double(a: &AtomicU64, tries: &AtomicU64) -> u64 {
        let mut cur = a.load(Relaxed);
        loop { tries.fetch_add(1, Relaxed); match a.compare_exchange_weak(cur, cur.wrapping_mul(3), AcqRel, Relaxed) { Ok(old) => return old, Err(actual) => cur = actual } }
    }
    fn main() {
        let a = AtomicU64::new(1); let tries = AtomicU64::new(0); let calls = 4 * 20_000;
        thread::scope(|s| { for _ in 0..4 { s.spawn(|| { for _ in 0..20_000 { fetch_double(&a, &tries); } }); } });
        // 每次调用恰好应用一次 x → 3x(模 2^64),乘法可交换,与线程交错顺序无关;所以最终值是确定的
        let mut x = 1u64; for _ in 0..calls { x = x.wrapping_mul(3); }
        println!("{} 次 CAS 循环调用,最终值 {} 与单线程顺序应用 {} 次的结果相同: {}", calls, a.load(Relaxed), calls, a.load(Relaxed) == x);
        println!("循环体共执行 {} 次(≥ {} 次调用,多出来的就是 CAS 失败后重试的次数)", tries.load(Relaxed), calls);
        let b = AtomicU64::new(10);
        println!("fetch_update(只在 <20 时加 5):{:?} {:?} {:?}", b.fetch_update(SeqCst, SeqCst, |v| (v < 20).then(|| v + 5)), b.fetch_update(SeqCst, SeqCst, |v| (v < 20).then(|| v + 5)), b.fetch_update(SeqCst, SeqCst, |v| (v < 20).then(|| v + 5)));
    }
''', quiet_src=True, release=True); R['loop'] = r['out']
print()
print('== 三:compare_exchange_weak 允许「虚假失败」(值相等也可能返回 Err);在这台机器上单线程下统计')
r = tryit('u93c', '''
    use std::sync::atomic::{AtomicU32, Ordering::*};
    fn main() {
        let a = AtomicU32::new(0); let n = 20_000_000u32; let (mut wf, mut sf) = (0u32, 0u32);
        for _ in 0..n { if a.compare_exchange_weak(0, 0, SeqCst, SeqCst).is_err() { wf += 1; } }
        for _ in 0..n { if a.compare_exchange(0, 0, SeqCst, SeqCst).is_err() { sf += 1; } }
        println!("单线程,期望值永远正确:compare_exchange_weak 虚假失败 {} / {} 次;compare_exchange 失败 {} 次", wf, n, sf);
    }
''', quiet_src=True, release=True); R['weak'] = r['out']
print()
print('== 四:用 CAS 手写自旋锁,保护一个「非原子」的计数(4 线程 × 10 万次),不加锁则丢更新')
r = tryit('u93d', '''
    use std::{cell::UnsafeCell, sync::atomic::{AtomicBool, Ordering::*}, thread};
    struct Spin { locked: AtomicBool, v: UnsafeCell<u64> }
    unsafe impl Sync for Spin {}
    impl Spin {
        fn lock(&self) { while self.locked.compare_exchange_weak(false, true, Acquire, Relaxed).is_err() { std::hint::spin_loop(); } }
        fn unlock(&self) { self.locked.store(false, Release); }
    }
    fn main() {
        let s = Spin { locked: AtomicBool::new(false), v: UnsafeCell::new(0) };
        thread::scope(|t| { for _ in 0..4 { t.spawn(|| { for _ in 0..100_000 { s.lock(); unsafe { *s.v.get() += 1; } s.unlock(); } }); } });
        println!("自旋锁保护下的计数 = {}(期望 400000)", unsafe { *s.v.get() });
    }
''', quiet_src=True, release=True); R['spin'] = r['out']
print()
print('== 五:ABA 问题:CAS 只比较值,看不到「A → B → A」的中间变化;给值加版本号(标签)可以发现')
r = tryit('u93e', '''
    use std::sync::atomic::{AtomicU64, Ordering::*};
    // 低 32 位是值,高 32 位是版本号
    fn pack(v: u32, ver: u32) -> u64 { ((ver as u64) << 32) | v as u64 }
    fn main() {
        // 无版本号:线程 1 读到 A(=1),被打断;线程 2 把 1 → 2 → 1;线程 1 的 CAS 仍然成功
        let a = AtomicU64::new(1);
        let seen = a.load(SeqCst);
        a.store(2, SeqCst); a.store(1, SeqCst);                      // 另一个线程做的 A→B→A
        println!("无版本号:CAS(期望 {}) → {:?}(成功,但值其实被改过两次)", seen, a.compare_exchange(seen, 5, SeqCst, SeqCst));
        // 有版本号:每次写入版本号 +1
        let b = AtomicU64::new(pack(1, 0));
        let seen = b.load(SeqCst);
        b.store(pack(2, 1), SeqCst); b.store(pack(1, 2), SeqCst);
        let r = b.compare_exchange(seen, pack(5, 1), SeqCst, SeqCst);
        println!("有版本号:CAS(期望 值1/版本0) → {:?}(失败,当前 值{}/版本{})", r.is_ok(), b.load(SeqCst) as u32, b.load(SeqCst) >> 32);
    }
''', quiet_src=True); R['aba'] = r['out']
save('u93', R)

print()
print('== 六:这台 aarch64 机器上,两种 CAS 编译成了什么指令(--emit=asm -O)')
code = '''
    use std::sync::atomic::{AtomicU32, Ordering::*};
    #[unsafe(no_mangle)] pub fn strong(a: &AtomicU32) -> bool { a.compare_exchange(0, 1, SeqCst, SeqCst).is_ok() }
    #[unsafe(no_mangle)] pub fn weak(a: &AtomicU32) -> bool { a.compare_exchange_weak(0, 1, SeqCst, SeqCst).is_ok() }
'''
for fn in ('strong', 'weak'):
    b, _ = asm_of('u93f', code, fn)
    ins = [l.split()[0] for l in b if l.strip() and not l.strip().startswith(('.', 'L', ';')) and not l.endswith(':')]
    print(f'  {fn:<7} 指令: {" ".join(ins)}')
    R['asm_' + fn] = ins
save('u93', R)
