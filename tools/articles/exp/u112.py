import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u112'); R = {}
print('== 一:同样三个字段(u8, u32, u16),repr(Rust) 与 repr(C) 的大小与字段偏移')
r = tryit('u112a', '''
    use std::mem::{size_of, align_of, offset_of};
    struct R { a: u8, b: u32, c: u16 }
    #[repr(C)] struct C { a: u8, b: u32, c: u16 }
    fn main() {
        println!("repr(Rust): size {} align {}  偏移 a={} b={} c={}", size_of::<R>(), align_of::<R>(), offset_of!(R, a), offset_of!(R, b), offset_of!(R, c));
        println!("repr(C):    size {} align {}  偏移 a={} b={} c={}", size_of::<C>(), align_of::<C>(), offset_of!(C, a), offset_of!(C, b), offset_of!(C, c));
        println!("字段本身合计 {} 字节;repr(C) 多出的 {} 字节是填充(padding)", 1 + 4 + 2, size_of::<C>() - 7);
    }
''', quiet_src=True); R['basic'] = r['out']
print()
print('== 二:repr(C) 严格按声明顺序排列;调整声明顺序可以消除填充:对比三种声明顺序的 repr(C) 大小')
r = tryit('u112b', '''
    #![allow(dead_code)]
    use std::mem::size_of;
    #[repr(C)] struct Bad { a: u8, b: u64, c: u8, d: u32 }
    #[repr(C)] struct Good { b: u64, d: u32, a: u8, c: u8 }
    struct RustRepr { a: u8, b: u64, c: u8, d: u32 }
    fn main() {
        println!("repr(C) 声明顺序 u8,u64,u8,u32: {} 字节", size_of::<Bad>());
        println!("repr(C) 声明顺序 u64,u32,u8,u8: {} 字节(按大小降序,填充最少)", size_of::<Good>());
        println!("repr(Rust) 同样四个字段(任意声明顺序): {} 字节(编译器自己重排)", size_of::<RustRepr>());
    }
''', quiet_src=True); R['order'] = r['out']
print()
print('== 三:repr(packed) 去掉填充,但引用未对齐的字段是错误;repr(align(N)) 提高对齐')
r = tryit('u112c', '''
    use std::mem::{size_of, align_of};
    #[repr(C, packed)] struct P { a: u8, b: u32, c: u16 }
    #[repr(C, align(16))] struct A16 { x: u32 }
    fn main() {
        println!("packed: size {} align {}(没有填充,各字段紧挨着)", size_of::<P>(), align_of::<P>());
        println!("align(16) 的 struct,只含一个 u32: size {} align {}(大小被补到对齐的倍数)", size_of::<A16>(), align_of::<A16>());
        let p = P { a: 1, b: 2, c: 3 }; let b = p.b; println!("按值读 packed 字段是安全的: b = {}", b);
    }
''', quiet_src=True); R['packed'] = r['out']
r = tryit('u112d', '''
    #[repr(C, packed)] struct P { a: u8, b: u32 }
    fn main() { let p = P { a: 1, b: 2 }; let r = &p.b; println!("{}", r); }
''', maxlines=24); R['e0793'] = r['diag']
print()
print('== 四:枚举:repr(u8) / repr(C) / 默认的大小;带数据的枚举的大小')
r = tryit('u112e', '''
    #![allow(dead_code)]
    use std::mem::size_of;
    enum E0 { A, B, C }
    #[repr(u8)] enum E1 { A = 1, B = 2, C = 200 }
    #[repr(C)] enum E2 { A, B, C }
    #[repr(u32)] enum E3 { A, B, C }
    #[allow(dead_code)] enum Data { A(u8), B(u32), C }
    #[allow(dead_code)] #[repr(C)] enum DataC { A(u8), B(u32), C }
    fn main() {
        println!("默认 enum E0 {{A,B,C}}: {}  repr(u8): {}  repr(C): {}  repr(u32): {}", size_of::<E0>(), size_of::<E1>(), size_of::<E2>(), size_of::<E3>());
        println!("带数据 enum {{A(u8), B(u32), C}}: 默认 {}  repr(C): {}", size_of::<Data>(), size_of::<DataC>());
        println!("E1::C as u8 = {}(repr(u8) 的判别值可以读出来)", E1::C as u8);
    }
''', quiet_src=True); R['enum'] = r['out']
print()
print('== 五:把 repr(C) 结构体 transmute 成字节数组,直接看内存里的真实排布')
r = tryit('u112f', '''
    #[repr(C)] struct H { tag: u8, len: u32, flags: u16 }
    fn main() {
        let h = H { tag: 0xAA, len: 0x11223344, flags: 0xBEEF };
        let bytes: [u8; 12] = unsafe { std::mem::transmute(h) };
        print!("repr(C) 结构体的 12 个字节(十六进制):"); for b in bytes { print!(" {:02x}", b); } println!();
        println!("tag 在字节 0,len 从字节 4 开始(小端:44 33 22 11),flags 从字节 8 开始(小端:ef be);其余是填充(内容未指定)");
    }
''', quiet_src=True); R['bytes'] = r['out']
save('u112', R)
