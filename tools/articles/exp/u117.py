import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u117'); R = {}
print('== 一:None 就是空指针:Option<&T>、Option<&mut T>、Option<Box<T>>、Option<NonNull<T>>、Option<fn()> 的 None 都是全 0')
r = tryit('u117a', '''
    use std::{mem::{size_of, transmute}, ptr::NonNull};
    fn main() {
        let a: Option<&u32> = None; let b: Option<&mut u32> = None; let c: Option<Box<u32>> = None; let d: Option<NonNull<u32>> = None; let e: Option<fn()> = None; let f: Option<extern "C" fn()> = None;
        unsafe { println!("  None 的位模式:&u32 {:#x}  &mut u32 {:#x}  Box<u32> {:#x}  NonNull<u32> {:#x}  fn() {:#x}  extern \\"C\\" fn() {:#x}", transmute::<_, usize>(a), transmute::<_, usize>(b), transmute::<_, usize>(c), transmute::<_, usize>(d), transmute::<_, usize>(e), transmute::<_, usize>(f)); }
        println!("  大小:{} {} {} {} {} {}(都是一个指针)", size_of::<Option<&u32>>(), size_of::<Option<&mut u32>>(), size_of::<Option<Box<u32>>>(), size_of::<Option<NonNull<u32>>>(), size_of::<Option<fn()>>(), size_of::<Option<extern "C" fn()>>());
        println!("  对照:*const u32 {} 字节,Option<*const u32> {} 字节(裸指针可以为空,没有 niche)", size_of::<*const u32>(), size_of::<Option<*const u32>>());
    }
''', quiet_src=True); R['bits'] = r['out']
print()
print('== 二:FFI 里的可空指针:C 函数返回 NULL 或指针,Rust 里用 Option<&T> 直接接收(不需要转换)—— 调用真实的 libc 函数 getenv / strchr')
r = tryit('u117b', '''
    use std::ffi::{c_char, c_int, CStr};
    unsafe extern "C" {
        fn getenv(name: *const c_char) -> Option<&'static c_char>;
        fn strchr(s: *const c_char, c: c_int) -> Option<&'static c_char>;
    }
    fn main() {
        unsafe {
            let home = getenv(c"HOME".as_ptr()); let none = getenv(c"U117_NOT_SET".as_ptr());
            println!("  getenv(\\"HOME\\") → {}(C 返回了非空指针)", if home.is_some() { "Some" } else { "None" });
            println!("  getenv(\\"U117_NOT_SET\\") → {:?}(C 返回了 NULL)", none.map(|p| CStr::from_ptr(p).to_str().unwrap()));
            let s = c"hello world"; let hit = strchr(s.as_ptr(), 'w' as c_int); let miss = strchr(s.as_ptr(), 'z' as c_int);
            println!("  strchr(\\"hello world\\", 'w') → {:?}  strchr(.., 'z') → {:?}", hit.map(|p| CStr::from_ptr(p).to_str().unwrap()), miss.map(|p| CStr::from_ptr(p).to_str().unwrap()));
        }
    }
''', quiet_src=True); R['ffi'] = r['out']
print()
print('== 三:Rust 把 Option<Box<T>> 传给 C:None 变成 NULL(用 libc 的 free 验证:free(NULL) 是合法的空操作)')
r = tryit('u117c', '''
    use std::ffi::c_void;
    unsafe extern "C" { fn free(p: Option<Box<c_void>>); fn malloc(n: usize) -> Option<Box<c_void>>; }
    fn main() {
        unsafe {
            free(None); println!("  free(None) 没有崩溃(传给 C 的是 NULL)");
            let p = malloc(16); println!("  malloc(16) → {}", if p.is_some() { "Some(非空指针)" } else { "None" });
            std::mem::forget(p);
        }
    }
''', quiet_src=True); R['free'] = r['out']
print()
print('== 四:没有 niche 时 Option 需要额外标签;用 NonNull / NonZero / 引用做「可空」字段可以节省空间(val: u64 的链表节点实测)')
r = tryit('u117d', '''
    use std::{mem::size_of, ptr::NonNull};
    #[allow(dead_code)] struct NodeBox { val: u64, next: Option<Box<NodeBox>> }
    #[allow(dead_code)] struct NodeRaw { val: u64, next: *mut NodeRaw, has_next: bool }
    #[allow(dead_code)] struct NodeNN { val: u64, next: Option<NonNull<NodeNN>> }
    #[allow(dead_code)] struct NodeOptU64 { val: u32, idx: Option<u64> }
    #[allow(dead_code)] struct NodeNZ { val: u32, idx: Option<std::num::NonZeroU64> }
    fn main() {
        println!("  Option<Box<Node>> 的链表节点:{} 字节;Option<NonNull<Node>>:{} 字节;裸指针 + bool 标志:{} 字节", size_of::<NodeBox>(), size_of::<NodeNN>(), size_of::<NodeRaw>());
        println!("  Option<u64> 做可选索引:{} 字节;Option<NonZeroU64>:{} 字节", size_of::<NodeOptU64>(), size_of::<NodeNZ>());
    }
''', quiet_src=True); R['node'] = r['out']
save('u117', R)
