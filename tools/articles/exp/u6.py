import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u6'); R = {}
print('== 一:数组 [T; N]:长度是类型的一部分,大小在编译期确定,存在栈上;越界访问的两种检查')
r = tryit('u6a', '''
    use std::mem::size_of_val;
    fn main() {
        let a = [10, 20, 30, 40, 50];
        println!("a 的类型长度 = {},占 {} 字节(5 个 i32)", a.len(), size_of_val(&a));
        let i = std::env::args().count() + 6;   // 运行时才知道:7
        println!("访问 a[{i}] ...");
        println!("{}", a[i]);
    }
''', maxlines=12); R['oob_rt'] = [l for l in (r['out'] + r.get('err', '')).split('\n') if 'index out of bounds' in l]
r = tryit('u6b', '''
    fn main() {
        let a = [10, 20, 30];
        println!("{}", a[5]);
    }
''', maxlines=16); R['oob_ct'] = r['diag'].split('\n')[0]
print()
print('== 二:切片 &[T] 是胖指针(地址 + 长度),不拥有数据')
r = tryit('u6c', '''
    use std::mem::size_of;
    fn sum(xs: &[i32]) -> i32 { xs.iter().sum() }
    fn main() {
        let arr = [1, 2, 3, 4, 5];
        let v = vec![1, 2, 3, 4, 5];
        println!("size_of::<&i32>()   = {} 字节(普通引用:一个地址)", size_of::<&i32>());
        println!("size_of::<&[i32]>() = {} 字节(切片:地址 + 长度)", size_of::<&[i32]>());
        println!("sum(&arr)       = {}", sum(&arr));
        println!("sum(&v)         = {}", sum(&v));
        println!("sum(&arr[1..4]) = {}", sum(&arr[1..4]));
        println!("sum(&v[..2])    = {}", sum(&v[..2]));
        let s = &v[1..3];
        println!("切片 s = {:?},s.len() = {},s 的数据地址比 v 的数据地址大 {} 字节", s, s.len(), s.as_ptr() as usize - v.as_ptr() as usize);
    }
''', quiet_src=False); R['slice'] = r['out']
r = tryit('u6d', '''
    fn main() {
        let v = vec![1, 2, 3];
        let (a, b) = (3, 2);
        println!("{:?}", &v[a..b]);
    }
''', maxlines=10); R['slice_panic'] = [l for l in (r['out'] + r.get('err', '')).split('\n') if 'slice' in l][:1]
print()
print('== 三:Vec<T> = 堆上的缓冲区 + (指针, 长度, 容量) 三个字;扩容规律')
r = tryit('u6e', '''
    use std::mem::size_of;
    fn main() {
        println!("size_of::<Vec<i32>>() = {} 字节(指针、长度、容量各 8 字节)", size_of::<Vec<i32>>());
        let mut v: Vec<i32> = Vec::new();
        println!("Vec::new():len={} cap={}(还没有分配堆内存)", v.len(), v.capacity());
        let mut last = v.capacity();
        for i in 0..40 {
            v.push(i);
            if v.capacity() != last { println!("push 第 {:>2} 个元素后:cap {:>2} → {:>2}", v.len(), last, v.capacity()); last = v.capacity(); }
        }
        let w: Vec<i32> = Vec::with_capacity(100);
        println!("with_capacity(100):len={} cap={}", w.len(), w.capacity());
        let mut z = vec![1, 2, 3];
        z.reserve(10); println!("vec![1,2,3] 后 reserve(10):cap={}", z.capacity());
        z.shrink_to_fit(); println!("shrink_to_fit 后:cap={}", z.capacity());
    }
''', quiet_src=False); R['grow'] = r['out']
print()
print('== 四:栈与堆:数组的元素在栈上(地址紧挨着局部变量),Vec 的元素在堆上')
r = tryit('u6f', '''
    fn main() {
        let local = 0u8;
        let arr = [1u8; 16];
        let v = vec![1u8; 16];
        let stack = &local as *const u8 as usize;
        println!("局部变量地址   = {:#x}", stack);
        println!("数组元素地址   = {:#x}(与局部变量相差 {} 字节)", arr.as_ptr() as usize, (arr.as_ptr() as usize).abs_diff(stack));
        println!("Vec 元素地址   = {:#x}(与局部变量相差 {} 字节)", v.as_ptr() as usize, (v.as_ptr() as usize).abs_diff(stack));
        println!("Vec 本身(三个字)地址 = {:#x}(在栈上)", &v as *const Vec<u8> as usize);
    }
''', quiet_src=True); R['addr'] = r['out']
print()
print('== 五:get 返回 Option,不 panic')
r = tryit('u6g', '''
    fn main() {
        let v = vec![10, 20, 30];
        println!("v.get(1) = {:?}", v.get(1));
        println!("v.get(9) = {:?}", v.get(9));
        println!("v.get(1..3) = {:?}", v.get(1..3));
        println!("v.get(2..9) = {:?}", v.get(2..9));
        println!("v.first() = {:?},v.last() = {:?}", v.first(), v.last());
    }
''', quiet_src=True)
save('u6', R)
