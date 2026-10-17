import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u3'); R = {}
print('== 一:默认不可变:给没有 mut 的变量第二次赋值')
r = tryit('u3a', '''
    fn main() {
        let x = 5;
        println!("x = {x}");
        x = 6;
        println!("x = {x}");
    }
''', maxlines=30); R['e1'] = r['diag'].split('\n')[0]
print()
print('== 二:加上 mut 就可以;mut 是变量绑定的属性,不是类型的一部分')
r = tryit('u3b', '''
    fn main() {
        let mut x = 5;
        println!("x = {x}");
        x = 6;
        println!("x = {x}");
        let y = x;      // 把 mut 变量的值赋给不可变变量:允许
        println!("y = {y}");
    }
''')
print()
print('== 三:不可变是「深」的:结构体字段赋值、调用需要 &mut self 的方法都被挡住')
r = tryit('u3c', '''
    struct P { a: i32 }
    fn main() {
        let p = P { a: 1 };
        p.a = 2;
        let v = Vec::new();
        v.push(1);
        println!("{} {}", p.a, v.len());
    }
''', maxlines=40); R['e3'] = r['diag'].count('error[')
print()
print('== 四:延迟初始化:先声明后赋值,只要每条路径恰好赋值一次就合法;赋值两次则不行')
r = tryit('u3d', '''
    fn main() {
        let x;
        let flag = std::env::args().count() > 1;
        if flag { x = 1; } else { x = 2; }
        println!("x = {x}");
    }
''')
r = tryit('u3e', '''
    fn main() {
        let x;
        x = 1;
        x = 2;
        println!("x = {x}");
    }
''', maxlines=24)
print()
print('== 五:不可变不是运行时开销:同一个函数分别用 let 和 let mut 写,-O 生成的汇编是否相同')
code = '''
    #[unsafe(no_mangle)] pub fn imm(n: u32) -> u32 { let x = n * 3 + 1; x * 2 }
    #[unsafe(no_mangle)] pub fn mutv(n: u32) -> u32 { let mut x = n * 3; x += 1; x *= 2; x }
'''
a1, txt = asm_of('u3f', code, 'imm'); a2, _ = asm_of('u3f', code, 'mutv'); alias = re.search(r'^_mutv = (\S+)', txt, re.M)
print('  imm  的汇编:', ' ; '.join(a1))
print('  mutv 的汇编:', ' ; '.join(a2) if a2 else f'(没有单独的函数体:汇编里是一行 `_mutv = {alias.group(1)}`,LLVM 发现两个函数完全相同,把 mutv 合并成了 imm 的别名)')
R['same_asm'] = a1 == a2 or bool(alias); R['asm'] = a1; R['alias'] = bool(alias); print('  两个函数的机器码相同:', R['same_asm'])
print('  (Rust 的可变性检查全在编译期的借用检查阶段,生成的机器码里没有 mut 的痕迹)')
save('u3', R)
