import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u119'); R = {}
PRE = '''
    struct Noisy(&'static str); impl Drop for Noisy { fn drop(&mut self) { println!("  Noisy({}) drop", self.0); } }
'''
print('== 一:ManuallyDrop<T>:包进去的值不会自动 drop;要么手动 drop,要么忘记(泄漏);大小与 T 相同,Deref 让你照常使用')
r = tryit('u119a', PRE + '''
    use std::mem::{ManuallyDrop, size_of};
    fn main() {
        println!("  size_of::<Noisy>() = {}  size_of::<ManuallyDrop<Noisy>>() = {}", size_of::<Noisy>(), size_of::<ManuallyDrop<Noisy>>());
        { let _a = ManuallyDrop::new(Noisy("忘记")); println!("  作用域结束:ManuallyDrop<Noisy(忘记)> 不会 drop(下面不会有它的 drop 行)"); }
        { let mut b = ManuallyDrop::new(Noisy("手动")); println!("  通过 Deref 使用内部值:{}", b.0); unsafe { ManuallyDrop::drop(&mut b); } println!("  ManuallyDrop::drop 之后"); }
        { let c = ManuallyDrop::new(Noisy("取出")); let inner = ManuallyDrop::into_inner(c); println!("  into_inner 取回所有权,恢复正常 drop 规则:"); let _ = inner; }
    }
''', quiet_src=True); R['basic'] = r['out']
print()
print('== 二:控制字段的 drop 顺序:默认按声明顺序;用 ManuallyDrop + 自己的 Drop 改变顺序')
r = tryit('u119b', PRE + '''
    use std::mem::ManuallyDrop;
    #[allow(dead_code)] struct Default_ { first: Noisy, second: Noisy }
    struct Reordered { first: ManuallyDrop<Noisy>, second: ManuallyDrop<Noisy> }
    impl Drop for Reordered { fn drop(&mut self) { unsafe { ManuallyDrop::drop(&mut self.second); ManuallyDrop::drop(&mut self.first); } } }
    fn main() {
        println!("默认:先 first,后 second");
        drop(Default_ { first: Noisy("first"), second: Noisy("second") });
        println!("用 ManuallyDrop 反过来:先 second,后 first");
        drop(Reordered { first: ManuallyDrop::new(Noisy("first")), second: ManuallyDrop::new(Noisy("second")) });
    }
''', quiet_src=True); R['order'] = r['out']
print()
print('== 三:Drop 的类型不能把字段移出去(E0509);用 ManuallyDrop::take 或 Option::take 绕开')
r = tryit('u119c', '''
    struct Guard { data: String }
    impl Drop for Guard { fn drop(&mut self) {} }
    fn main() { let g = Guard { data: "x".into() }; let s = g.data; println!("{}", s); }
''', maxlines=24); R['e0509'] = r['diag']
r = tryit('u119d', '''
    use std::mem::ManuallyDrop;
    struct Guard { data: ManuallyDrop<String> }
    impl Guard { fn into_data(self) -> String { let mut me = ManuallyDrop::new(self); unsafe { ManuallyDrop::take(&mut me.data) } } }
    impl Drop for Guard { fn drop(&mut self) { println!("  Guard::drop 运行了,会 drop 内部的 String"); unsafe { ManuallyDrop::drop(&mut self.data); } } }
    fn main() {
        let g = Guard { data: ManuallyDrop::new("payload".to_string()) };
        let s = g.into_data(); println!("  into_data 取出 {:?};Guard 自己的 Drop 没有运行(没有上一行的输出)", s);
        let _g2 = Guard { data: ManuallyDrop::new("x".to_string()) };
    }
''', quiet_src=True); R['take'] = r['out']
print()
print('== 四:ManuallyDrop 配合 Vec 的原始部件:拆出指针/长度/容量,再重新组装,避免双重释放')
r = tryit('u119e', '''
    use std::mem::ManuallyDrop;
    fn main() {
        let v = vec![1u32, 2, 3, 4]; let mut v = ManuallyDrop::new(v);
        let (p, len, cap) = (v.as_mut_ptr(), v.len(), v.capacity());
        println!("  拆出 ptr / len = {} / cap = {};原 Vec 被 ManuallyDrop 包着,不会自动释放缓冲区", len, cap);
        let rebuilt = unsafe { Vec::from_raw_parts(p, len, cap) };
        println!("  from_raw_parts 重新组装:{:?}(缓冲区只会被释放一次)", rebuilt);
    }
''', quiet_src=True); R['raw'] = r['out']
print()
print('== 五:mem::forget 与 ManuallyDrop 的区别:forget 立刻放弃值;ManuallyDrop 保留值并允许之后使用或 drop')
r = tryit('u119f', PRE + '''
    use std::mem::{forget, ManuallyDrop};
    fn main() {
        let a = Noisy("forget"); forget(a);
        let mut b = ManuallyDrop::new(Noisy("ManuallyDrop")); println!("  ManuallyDrop 之后还能读: {}", b.0);
        unsafe { ManuallyDrop::drop(&mut b); }
        println!("  forget 之后值没法再用、也没法再 drop;ManuallyDrop 可以");
    }
''', quiet_src=True); R['forget'] = r['out']
save('u119', R)
