import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u63'); R = {}
print('== 一:map 改变元素类型,filter 不改变;filter 的闭包拿到的是元素的引用(对 iter() 来说是 &&i32)')
r = tryit('u63a', '''
    fn tn<T>(_: &T) -> &'static str { std::any::type_name::<T>() }
    fn main() {
        let v = vec![1, 2, 3, 4, 5, 6];
        let a: Vec<String> = v.iter().map(|x| format!("#{}", x)).collect();
        println!("map i32 -> String: {:?}", a);
        let b: Vec<&i32> = v.iter().filter(|x| { println!("  filter 闭包的参数类型 {}", tn(&x)); **x % 2 == 0 }).take(1).collect();
        println!("filter 之后元素类型仍是 &i32: {:?}", b);
        let c: Vec<i32> = v.iter().copied().filter(|x| x % 2 == 0).collect();
        println!("copied 之后 filter 参数是 &i32,可以直接 x % 2: {:?}", c);
    }
''', quiet_src=False); R['types'] = r['out']
r = tryit('u63b', '''
    fn main() {
        let v = vec![1, 2, 3];
        let c: Vec<&i32> = v.iter().filter(|x| x % 2 == 0).collect();
        println!("{:?}", c);
    }
''', maxlines=30); R['e_filter'] = r['diag']
print()
print('== 二:filter_map 一步完成「解析 + 过滤」;flatten 在 Option 上自动丢弃 None')
r = tryit('u63c', '''
    fn main() {
        let raw = ["10", "x", "30", "", "50"];
        let a: Vec<i32> = raw.iter().filter_map(|s| s.parse().ok()).collect();
        println!("filter_map(parse.ok): {:?}", a);
        let b: Vec<i32> = raw.iter().map(|s| s.parse::<i32>()).flatten().collect();
        println!("map(parse).flatten():  {:?}", b);
        let c: Result<Vec<i32>, _> = raw.iter().map(|s| s.parse::<i32>()).collect();
        println!("collect 成 Result:     {:?}", c);
    }
''', quiet_src=True); R['fm'] = r['out']
print()
print('== 三:fold:累加器类型可以和元素类型不同;顺序决定结果(a*2+x 不满足交换律);reduce 对空序列返回 None')
r = tryit('u63d', '''
    fn main() {
        let v = [10, 3, 2];
        println!("fold(0, a*2+x) 从左到右: {}   rfold 从右到左: {}", v.iter().fold(0, |a, x| a * 2 + x), v.iter().rfold(0, |a, x| a * 2 + x));
        println!("fold 的累加器是 String(元素是 i32): {:?}", v.iter().fold(String::new(), |mut s, x| { if !s.is_empty() { s.push('-'); } s.push_str(&x.to_string()); s }));
        println!("fold 同时算 (和, 个数): {:?}", v.iter().fold((0, 0), |(s, n), x| (s + x, n + 1)));
        println!("reduce(max): {:?}   空序列 reduce: {:?}   空序列 fold(0,..): {}", v.iter().copied().reduce(i32::max), Vec::<i32>::new().into_iter().reduce(i32::max), Vec::<i32>::new().iter().fold(0, |a, x| a + x));
        println!("scan 保留中间状态: {:?}", v.iter().scan(0, |acc, x| { *acc += x; Some(*acc) }).collect::<Vec<_>>());
    }
''', quiet_src=True); R['fold'] = r['out']
print()
print('== 四:try_fold 与短路:遇到溢出立刻停止,后面的元素不再处理')
r = tryit('u63e', '''
    fn main() {
        let v: [u8; 6] = [100, 100, 50, 10, 1, 1];
        let mut seen = 0;
        let r = v.iter().try_fold(0u8, |a, x| { seen += 1; a.checked_add(*x) });
        println!("u8 的 checked_add:total {:?}(看了 {} 个元素,累加到第 4 个溢出)", r, seen);
        let ok = [1u8, 2, 3].iter().try_fold(0u8, |a, x| a.checked_add(*x));
        println!("不溢出的情形: {:?}", ok);
    }
''', quiet_src=True); R['try'] = r['out']
print()
print('== 五:三种写法的汇编:for 循环 / fold / sum(),-O 下是否生成一样的代码')
code = '''
    #[unsafe(no_mangle)] pub fn sum_for(v: &[u32]) -> u32 { let mut s = 0u32; for x in v { s = s.wrapping_add(*x); } s }
    #[unsafe(no_mangle)] pub fn sum_fold(v: &[u32]) -> u32 { v.iter().fold(0u32, |a, x| a.wrapping_add(*x)) }
    #[unsafe(no_mangle)] pub fn sum_iter(v: &[u32]) -> u32 { v.iter().fold(0u32, |a, &x| a.wrapping_add(x)) }
    #[unsafe(no_mangle)] pub fn sum_map_filter(v: &[u32]) -> u32 { v.iter().map(|x| x * 2).filter(|x| x % 3 == 0).fold(0u32, |a, x| a.wrapping_add(x)) }
    #[unsafe(no_mangle)] pub fn sum_manual(v: &[u32]) -> u32 { let mut s = 0u32; for x in v { let y = x * 2; if y % 3 == 0 { s = s.wrapping_add(y); } } s }
'''
bodies = {}
for fn in ('sum_for', 'sum_fold', 'sum_iter', 'sum_map_filter', 'sum_manual'):
    b, txt = asm_of('u63f', code, fn); bodies[fn] = b
txt = open(str(RS / 'asm' / 'u63f.s')).read()
al = re.findall(r'^(_\w+) = (_\w+)', txt, re.M)
print('  汇编里的符号别名:', al)
def norm(b): return [re.sub(r'\bLBB\d+_\d+\b', 'L', re.sub(r'\s+', ' ', l.strip())) for l in b if l.strip() and not l.strip().startswith(('.', ';'))]
nb = {fn: norm(b) for fn, b in bodies.items()}
for fn, b in nb.items(): print(f'  {fn:<16} 指令 {len([l for l in b if not l.endswith(":")])} 条  向量指令(.4s/.2d)条数 {len([l for l in b if re.search(r"\.(4s|2d|16b|8h)", l)])}')
same_fm = nb['sum_for'] == nb['sum_fold']; same_mm = nb['sum_map_filter'] == nb['sum_manual']
print(f'  sum_for 与 sum_fold(规范化标签后)逐行相同: {same_fm};  map+filter+fold 与手写循环逐行相同: {same_mm}')
R['asm'] = {'fm': same_fm, 'mm': same_mm, 'alias': al, 'n': {fn: len([l for l in b if not l.endswith(':')]) for fn, b in nb.items()}, 'vec': {fn: len([l for l in b if re.search(r'\.(4s|2d|16b|8h)', l)]) for fn, b in nb.items()}}
save('u63', R)
