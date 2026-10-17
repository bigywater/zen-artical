import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u50'); R = {}
print('== 一:数值的 try_from:越界返回 Err,不像 as 那样悄悄截断')
r = tryit('u50a', '''
    use std::convert::TryFrom;
    fn main() {
        for v in [200i32, 300, -1, 255, 256] {
            println!("{:>4}:as u8 = {:>3},u8::try_from = {:?}", v, v as u8, u8::try_from(v));
        }
        println!("i32::try_from(3_000_000_000u64) = {:?}", i32::try_from(3_000_000_000u64));
        println!("u32::try_from(-5i64)             = {:?}", u32::try_from(-5i64));
        let r: Result<u8, _> = 300i32.try_into();
        println!("300i32.try_into::<u8>()          = {:?}", r);
    }
''', quiet_src=False)
print()
print('== 二:自己的类型实现 TryFrom,带校验与自定义错误')
r = tryit('u50b', '''
    use std::convert::TryFrom;
    #[derive(Debug)] struct Port(u16);
    #[derive(Debug)] enum PortError { Negative, TooBig(i32), Reserved(u16) }
    impl TryFrom<i32> for Port {
        type Error = PortError;
        fn try_from(n: i32) -> Result<Self, PortError> {
            if n < 0 { return Err(PortError::Negative); }
            let p = u16::try_from(n).map_err(|_| PortError::TooBig(n))?;
            if p < 1024 { return Err(PortError::Reserved(p)); }
            Ok(Port(p))
        }
    }
    fn main() {
        for n in [8080, -1, 70000, 80] { println!("{:>6} → {:?}", n, Port::try_from(n)); }
        let p: Result<Port, _> = 443.try_into(); println!("443.try_into() → {:?}", p);
    }
''', quiet_src=False, flags=('-A', 'dead_code'))
print()
print('== 三:无损转换也有 TryFrom(自动得到,错误类型是 Infallible —— 永远不会出现的错误)')
r = tryit('u50c', '''
    use std::convert::{Infallible, TryFrom};
    fn main() {
        let r: Result<u64, Infallible> = u64::try_from(5u32);
        println!("{:?}", r);
        match r { Ok(v) => println!("u32 → u64 的 try_from 一定成功:{v}"), Err(never) => match never {} }
        println!("size_of::<Infallible>() = {}", std::mem::size_of::<Infallible>());
    }
''', quiet_src=False)
print()
print('== 四:切片转数组:长度不对就是 Err')
r = tryit('u50d', '''
    use std::convert::TryInto;
    fn main() {
        let bytes = [0x12u8, 0x34, 0x56, 0x78, 0x9a];
        let a: [u8; 4] = bytes[..4].try_into().unwrap();
        println!("前 4 个字节 → [u8; 4]:{:02x?},大端 u32 = {:#x}", a, u32::from_be_bytes(a));
        let bad: Result<[u8; 4], _> = bytes[..].try_into();
        println!("5 个字节 → [u8; 4]:{:?}", bad);
    }
''', quiet_src=False)
save('u50', R)
