import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u21'); R = {}
print('== 一:迭代时修改集合:迭代器持有对 Vec 的 &,push 需要 &mut,二者冲突(这在 C++ 里是「迭代器失效」)')
r = tryit('u21a', '''
    fn main() {
        let mut v = vec![1, 2, 3];
        for x in &v {
            if *x == 2 { v.push(99); }
        }
        println!("{:?}", v);
    }
''', maxlines=30); R['e_iter'] = r['diag'].split('\n')[0]
print()
print('== 二:同一个值的两个 &mut 别名会让「看起来无关」的操作互相覆盖:swap_halves(&mut v, &mut v)')
r = tryit('u21b', '''
    fn swap_halves(a: &mut [i32], b: &mut [i32]) { for (x, y) in a.iter_mut().zip(b.iter_mut()) { std::mem::swap(x, y); } }
    fn main() {
        let mut v = vec![1, 2, 3, 4];
        swap_halves(&mut v, &mut v);       // 两个 &mut 指向同一个 Vec
        println!("{:?}", v);
    }
''', maxlines=24); R['e_alias'] = r['diag'].split('\n')[0]
r = tryit('u21c', '''
    fn swap_halves(a: &mut [i32], b: &mut [i32]) { for (x, y) in a.iter_mut().zip(b.iter_mut()) { std::mem::swap(x, y); } }
    fn main() {
        let mut v = vec![1, 2, 3, 4];
        let (left, right) = v.split_at_mut(2);      // 把一个切片拆成两个不相交的 &mut
        swap_halves(left, right);
        println!("{:?}", v);
    }
''', quiet_src=False)
print()
print('== 三:&mut 的独占性让编译器可以放心优化(noalias):同一个函数,同一个函数,&mut 版本与 & 版本的汇编mut 版本与裸指针版本的汇编')
code = '''
    #[unsafe(no_mangle)] pub fn with_mut(a: &mut i32, b: &mut i32) -> i32 { *a = 1; *b = 2; *a }
    #[unsafe(no_mangle)] pub fn with_ptr(a: *mut i32, b: *mut i32) -> i32 { unsafe { *a = 1; *b = 2; *a } }
'''
a1, txt = asm_of('u21d', code, 'with_mut'); a2, _ = asm_of('u21d', code, 'with_ptr')
print('  with_mut(&mut, &mut)  汇编:', ' ; '.join(a1)); print('  with_ptr(*mut, *mut)  汇编:', ' ; '.join(a2))
R['asm_mut'] = a1; R['asm_ptr'] = a2
print('  (用 &mut 时编译器知道 a 与 b 不会指向同一处,所以敢直接返回常量 1;用裸指针时 a、b 可能相同,必须在写 *b 之后重新读 *a)')
print()
print('== 四:独占也意味着 &mut 不能复制:同时只有一个可变引用,且不是 Copy')
r = tryit('u21e', '''
    fn main() {
        let mut x = 0;
        let a = &mut x;
        let b = a;       // &mut 被移动
        *b += 1;
        *a += 1;
    }
''', maxlines=18); R['e_nocopy'] = r['diag'].split('\n')[0]
save('u21', R)
