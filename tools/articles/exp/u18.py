import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u18'); R = {}
print('== 一:返回指向局部变量的引用')
r = tryit('u18a', '''
    fn dangle() -> &String {
        let s = String::from("hello");
        &s
    }
    fn main() { println!("{}", dangle()); }
''', maxlines=26); R['e1'] = r['diag'].split('\n')[0]
r = tryit('u18b', '''
    fn dangle<'a>() -> &'a String {
        let s = String::from("hello");
        &s
    }
    fn main() { println!("{}", dangle()); }
''', maxlines=26); R['e2'] = r['diag'].split('\n')[0]
print()
print('== 二:引用比它指向的值活得久')
r = tryit('u18c', '''
    fn main() {
        let r;
        {
            let x = 5;
            r = &x;
        }
        println!("r = {}", r);
    }
''', maxlines=26); R['e3'] = r['diag'].split('\n')[0]
print()
print('== 三:最经典的悬垂:持有指向 Vec 元素的引用时 push(可能重新分配)')
r = tryit('u18d', '''
    fn main() {
        let mut v = vec![1, 2, 3];
        let first = &v[0];
        v.push(4);
        println!("first = {}", first);
    }
''', maxlines=26); R['e4'] = r['diag'].split('\n')[0]
print('  为什么要禁止?用 unsafe 的裸指针亲眼看看 push 之后元素搬家了(只是为了观察,真实代码不要这么写):')
r = tryit('u18e', '''
    fn main() {
        let mut v = vec![1, 2, 3];          // len 3, cap 3
        let before = &v[0] as *const i32 as usize;
        println!("push 之前 cap = {},v[0] 的地址 = {:#x}", v.capacity(), before);
        v.push(4);                          // 容量不够,重新分配并搬家
        let after = &v[0] as *const i32 as usize;
        println!("push 之后 cap = {},v[0] 的地址 = {:#x}", v.capacity(), after);
        println!("地址变了:{}(旧地址上的内存已经被释放)", before != after);
    }
''', quiet_src=True); R['moved'] = r['out']
print()
print('== 四:改成合法的写法')
r = tryit('u18f', '''
    fn longest_owned() -> String { let s = String::from("hello"); s }       // 返回所有权
    fn main() {
        println!("{}", longest_owned());
        let r; let x = 5; r = &x;                                           // x 活得比 r 久
        println!("r = {r}");
        let mut v = vec![1, 2, 3];
        let first = v[0];                                                   // 拷贝出值,不再持有引用
        v.push(4);
        println!("first = {first},v = {:?}", v);
    }
''', quiet_src=False)
save('u18', R)
