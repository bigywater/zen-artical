import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u84'); R = {}
print('== 一:const 上下文里的 assert!:条件为假,编译失败(E0080);为真则没有任何运行期代价')
r = tryit('u84a', '''
    #[repr(C)] struct Header { tag: u8, len: u32 }
    const _: () = assert!(std::mem::size_of::<Header>() == 8, "Header 必须是 8 字节");
    fn main() { println!("size = {}", std::mem::size_of::<Header>()); }
''', quiet_src=False); R['ok'] = r['out']
r = tryit('u84b', '''
    #[repr(C)] struct Header { tag: u8, len: u32 }
    const _: () = assert!(std::mem::size_of::<Header>() == 6, "Header 必须是 6 字节");
    fn main() { println!("size = {}", std::mem::size_of::<Header>()); }
''', maxlines=30); R['e0080'] = r['diag']
print()
print('== 二:断言通过时,运行期没有任何痕迹:对比有无 const 断言的汇编')
code1 = '''
    const _: () = assert!(std::mem::size_of::<u64>() == 8);
    #[unsafe(no_mangle)] pub fn f(x: u64) -> u64 { x + 1 }
'''
code2 = '''
    #[unsafe(no_mangle)] pub fn f(x: u64) -> u64 { x + 1 }
'''
b1, t1 = asm_of('u84c1', code1, 'f'); b2, t2 = asm_of('u84c2', code2, 'f')
print(f'  有 const 断言的 f 汇编 {len(b1)} 行,没有断言的 {len(b2)} 行,逐行相同: {b1 == b2}'); R['asm'] = [len(b1), len(b2), b1 == b2]
print()
print('== 三:泛型里的断言:inline const 块 const { assert!(...) },在单态化时才求值,只有被实例化的类型才会失败')
r = tryit('u84d', '''
    struct Buf<const N: usize>;
    impl<const N: usize> Buf<N> {
        const OK: () = assert!(N.is_power_of_two(), "N 必须是 2 的幂");
        fn new() -> Self { let () = Self::OK; Buf }
    }
    fn main() { let _a = Buf::<8>::new(); println!("Buf::<8> 创建成功"); }
''', quiet_src=False); R['generic_ok'] = r['out']
r = tryit('u84e', '''
    struct Buf<const N: usize>;
    impl<const N: usize> Buf<N> {
        const OK: () = assert!(N.is_power_of_two(), "N 必须是 2 的幂");
        fn new() -> Self { let () = Self::OK; Buf }
    }
    fn main() { let _a = Buf::<8>::new(); let _b = Buf::<6>::new(); }
''', maxlines=30); R['generic_err'] = r['diag']
print()
print('== 四:inline const 块 const { ... } 在表达式位置使用')
r = tryit('u84f', '''
    fn first_n<const N: usize>() -> [u8; N] { const { assert!(N > 0 && N <= 4, "N 必须在 1..=4") }; [0; N] }
    fn main() { println!("{:?}", first_n::<3>()); }
''', quiet_src=False); R['inline_ok'] = r['out']
r = tryit('u84g', '''
    fn first_n<const N: usize>() -> [u8; N] { const { assert!(N > 0 && N <= 4, "N 必须在 1..=4") }; [0; N] }
    fn main() { println!("{:?}", first_n::<9>()); }
''', maxlines=30); R['inline_err'] = r['diag']
print()
print('== 五:另一种写法:用数组长度下溢触发常量求值错误(错误消息不如 assert! 可读)')
r = tryit('u84h', '''
    const _: [(); 0 - (std::mem::size_of::<u32>() != 4) as usize] = [];
    const _: [(); 0 - (std::mem::size_of::<u32>() != 5) as usize] = [];
    fn main() {}
''', maxlines=30); R['arr'] = r['diag']
save('u84', R)
