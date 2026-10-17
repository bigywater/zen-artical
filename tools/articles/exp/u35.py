import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u35'); R = {}
print('== 一:Cow<str>:不需要修改时借用,需要修改时才拥有(克隆)')
r = tryit('u35a', '''
    use std::borrow::Cow;
    fn strip_tabs(s: &str) -> Cow<'_, str> {
        if s.contains('\\t') { Cow::Owned(s.replace('\\t', " ")) } else { Cow::Borrowed(s) }
    }
    fn kind<T: ?Sized + ToOwned>(c: &Cow<'_, T>) -> &'static str { match c { Cow::Borrowed(_) => "Borrowed(没有分配)", Cow::Owned(_) => "Owned(分配了新 String)" } }
    fn main() {
        let a = "no tabs here"; let b = "has\\ttab";
        let ra = strip_tabs(a); let rb = strip_tabs(b);
        println!("{:<14} → {:?}  {}  指向原字符串:{}", a, ra, kind(&ra), std::ptr::eq(ra.as_ptr(), a.as_ptr()));
        println!("{:<14} → {:?}  {}", b, rb, kind(&rb));
    }
''', quiet_src=False)
print()
print('== 二:用计数分配器比较:对 10000 个字符串,其中 10% 需要修改')
r = tryit('u35b', '''
    use std::alloc::{GlobalAlloc, Layout, System};
    use std::borrow::Cow;
    use std::sync::atomic::{AtomicUsize, Ordering};
    struct C; static AL: AtomicUsize = AtomicUsize::new(0);
    unsafe impl GlobalAlloc for C {
        unsafe fn alloc(&self, l: Layout) -> *mut u8 { AL.fetch_add(1, Ordering::Relaxed); unsafe { System.alloc(l) } }
        unsafe fn dealloc(&self, p: *mut u8, l: Layout) { unsafe { System.dealloc(p, l) } }
    }
    #[global_allocator] static G: C = C;
    fn always_string(s: &str) -> String { s.replace('\\t', " ") }
    fn cow(s: &str) -> Cow<'_, str> { if s.contains('\\t') { Cow::Owned(s.replace('\\t', " ")) } else { Cow::Borrowed(s) } }
    fn main() {
        let inputs: Vec<String> = (0..10_000).map(|i| if i % 10 == 0 { format!("row{i}\\tx") } else { format!("row{i} x") }).collect();
        let a0 = AL.load(Ordering::Relaxed);
        let mut n1 = 0usize; for s in &inputs { n1 += always_string(s).len(); }
        let a1 = AL.load(Ordering::Relaxed) - a0;
        let a0 = AL.load(Ordering::Relaxed);
        let mut n2 = 0usize; let mut owned = 0usize;
        for s in &inputs { let c = cow(s); if matches!(c, Cow::Owned(_)) { owned += 1; } n2 += c.len(); }
        let a2 = AL.load(Ordering::Relaxed) - a0;
        println!("每次都返回 String:堆分配 {} 次(总长度 {})", a1, n1);
        println!("返回 Cow<str>     :堆分配 {} 次(其中 Owned {} 个,总长度 {})", a2, owned, n2);
    }
''', release=True, quiet_src=False); R['alloc'] = r['out']
print()
print('== 三:to_mut():写时克隆 —— 第一次修改时才分配,之后直接改;into_owned() 取出拥有的值')
r = tryit('u35c', '''
    use std::borrow::Cow;
    fn main() {
        let original = String::from("hello");
        let mut c: Cow<str> = Cow::Borrowed(&original);
        println!("开始:{:?},是借用:{}", c, matches!(c, Cow::Borrowed(_)));
        c.to_mut().push_str(", world");            // 第一次修改:克隆,变成 Owned
        println!("to_mut().push_str 之后:{:?},是借用:{}", c, matches!(c, Cow::Borrowed(_)));
        c.to_mut().push('!');                       // 之后再修改不会再克隆(缓冲区可能因容量不足而移动,但不是 Cow 造成的)
        println!("再 push 一次:{:?};原字符串没有被改变:{:?}", c, original);
        let s: String = c.into_owned();
        println!("into_owned 得到 String:{s}");
    }
''', quiet_src=False)
print()
print('== 四:大小:Cow<str> 与 String 一样大;Cow<[T]> 同理')
r = tryit('u35d', '''
    use std::borrow::Cow;
    use std::mem::size_of;
    fn main() {
        println!("String = {},&str = {},Cow<str> = {}", size_of::<String>(), size_of::<&str>(), size_of::<Cow<str>>());
        println!("Vec<u8> = {},&[u8] = {},Cow<[u8]> = {}", size_of::<Vec<u8>>(), size_of::<&[u8]>(), size_of::<Cow<[u8]>>());
    }
''', quiet_src=True)
save('u35', R)
