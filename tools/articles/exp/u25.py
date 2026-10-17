import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u25'); R = {}
print('== 一:结构体里存引用必须声明生命周期参数')
r = tryit('u25a', '''
    struct Excerpt { part: &str }
    fn main() {}
''', maxlines=22); R['e106'] = r['diag'].split('\n')[0]
r = tryit('u25b', '''
    struct Excerpt<'a> { part: &'a str }
    fn main() {
        let novel = String::from("Call me Ishmael. Some years ago...");
        let first = novel.split('.').next().unwrap();
        let e = Excerpt { part: first };
        println!("摘录:{}", e.part);
    }
''', quiet_src=False)
print()
print('== 二:结构体不能比它借用的数据活得久;数据被借用期间不能修改')
r = tryit('u25c', '''
    struct Excerpt<'a> { part: &'a str }
    fn main() {
        let e;
        {
            let novel = String::from("Call me Ishmael.");
            e = Excerpt { part: &novel[..4] };
        }
        println!("{}", e.part);
    }
''', maxlines=24); R['e597'] = r['diag'].split('\n')[0]
r = tryit('u25d', '''
    struct Excerpt<'a> { part: &'a str }
    fn main() {
        let mut novel = String::from("Call me Ishmael.");
        let e = Excerpt { part: &novel[..4] };
        novel.push_str(" Some years ago");
        println!("{}", e.part);
    }
''', maxlines=24); R['e502'] = r['diag'].split('\n')[0]
print()
print('== 三:带引用的结构体 = 零拷贝:用计数分配器比较「借用切片」与「拥有 String」两种分词器的堆分配次数')
r = tryit('u25e', '''
    use std::alloc::{GlobalAlloc, Layout, System};
    use std::sync::atomic::{AtomicUsize, Ordering};
    struct Counting;
    static ALLOCS: AtomicUsize = AtomicUsize::new(0);
    unsafe impl GlobalAlloc for Counting {
        unsafe fn alloc(&self, l: Layout) -> *mut u8 { ALLOCS.fetch_add(1, Ordering::Relaxed); unsafe { System.alloc(l) } }
        unsafe fn dealloc(&self, p: *mut u8, l: Layout) { unsafe { System.dealloc(p, l) } }
    }
    #[global_allocator] static A: Counting = Counting;

    struct Tokens<'a> { words: Vec<&'a str> }                 // 借用:切片指回原文
    struct OwnedTokens { words: Vec<String> }                 // 拥有:每个词一个 String
    fn main() {
        let text: String = (0..10_000).map(|i| format!("word{i} ")).collect();
        let before = ALLOCS.load(Ordering::Relaxed);
        let t = Tokens { words: text.split_whitespace().collect() };
        let a1 = ALLOCS.load(Ordering::Relaxed) - before;
        let before = ALLOCS.load(Ordering::Relaxed);
        let o = OwnedTokens { words: text.split_whitespace().map(String::from).collect() };
        let a2 = ALLOCS.load(Ordering::Relaxed) - before;
        println!("文本里有 {} 个词", t.words.len());
        println!("借用版(Vec<&str>)  堆分配 {} 次", a1);
        println!("拥有版(Vec<String>)堆分配 {} 次", a2);
        println!("第 5000 个词:{} / {};两者内容相同:{}", t.words[5000], o.words[5000], t.words[5000] == o.words[5000]);
    }
''', release=True, quiet_src=False); R['alloc'] = r['out']
print()
print('== 四:一个结构体可以有多个互相独立的生命周期参数')
r = tryit('u25f', '''
    struct Pair<'a, 'b> { left: &'a str, right: &'b str }
    fn main() {
        let a = String::from("长寿的");
        let p;
        {
            let b = String::from("短命的");
            let tmp = Pair { left: &a, right: &b };
            println!("内层:{} {}", tmp.left, tmp.right);
            p = tmp.left;                 // 只取出生命周期 'a 的那部分
        }
        println!("外层:{}", p);
    }
''', quiet_src=False)
save('u25', R)
