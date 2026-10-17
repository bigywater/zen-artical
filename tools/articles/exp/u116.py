import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u116'); R = {}
print('== 一:切片 = (指针, 长度):从数组、Vec、范围切出来的切片,指针与长度的变化;切片不复制数据')
r = tryit('u116a', '''
    fn main() {
        let v: Vec<u32> = (0..10).collect(); let base = v.as_ptr() as usize;
        let show = |name: &str, s: &[u32]| println!("  {:<18} 指针 = base + {:>2} 字节  长度 {}", name, s.as_ptr() as usize - base, s.len());
        show("&v[..]", &v[..]); show("&v[2..7]", &v[2..7]); show("&v[5..]", &v[5..]); show("&v[2..7][1..3]", &v[2..7][1..3]); show("&v[3..3] (空)", &v[3..3]);
        let arr = [1u8, 2, 3, 4]; let s: &[u8] = &arr; println!("  数组 [u8; 4] 转 &[u8]:长度 {},数据地址相同 {}", s.len(), s.as_ptr() == arr.as_ptr());
        println!("  size_of::<&[u32]>() = {}(指针 8 + 长度 8)", std::mem::size_of::<&[u32]>());
    }
''', quiet_src=True); R['basic'] = r['out']
print()
print('== 二:切片只是视图:改切片就改原数据;&mut 切片之间不能重叠(split_at_mut 给出不重叠的两半)')
r = tryit('u116b', '''
    fn main() {
        let mut v = vec![1, 2, 3, 4, 5, 6];
        { let s = &mut v[1..4]; s[0] = 20; s[2] = 40; }
        println!("  改 &mut v[1..4] 的第 0、2 个元素后 v = {:?}", v);
        let (l, r) = v.split_at_mut(3); l[0] = 100; r[0] = 400;
        println!("  split_at_mut(3) 得到两个不重叠的 &mut 切片,分别改后 v = {:?}", v);
    }
''', quiet_src=True); R['view'] = r['out']
r = tryit('u116c', '''
    fn main() { let mut v = vec![1, 2, 3, 4]; let a = &mut v[0..3]; let b = &mut v[2..4]; a[0] = 1; b[0] = 2; }
''', maxlines=24); R['e0499'] = r['diag']
print()
print('== 三:越界:切片范围越界与索引越界都是 panic,消息里带有范围与长度;get 返回 None 不 panic')
for name, body in [('范围越界', 'let v = vec![1, 2, 3]; let n = v.len() + std::env::args().count() * 2; let _ = &v[1..n];'), ('起点大于终点', 'let v = vec![1, 2, 3]; let a = 2 + std::env::args().count(); let _ = &v[a..1];'), ('str 切在字符中间', 'let s = "héllo"; let i = 1 + std::env::args().count(); let _ = &s[..i];')]:
    r = tryit('u116d', 'fn main() { ' + body + ' }', quiet_src=True, show_run=False); rc, o, e, _ = run(r['bin']); m = [l for l in e.splitlines() if l.strip() and 'panicked' not in l and 'note: run' not in l][:2]
    print(f'  【{name}】退出码 {rc}:{m}'); R['panic_' + name] = [rc, m]
r = tryit('u116e', '''
    fn main() { let v = vec![1, 2, 3]; println!("  v.get(1..5) = {:?}  v.get(1..3) = {:?}", v.get(1..5), v.get(1..3)); }
''', quiet_src=True); R['get'] = r['out']
print()
print('== 四:零大小元素的切片:长度是真实的,指针不指向任何内存;空切片的指针是对齐的悬空指针(非空)')
r = tryit('u116f', '''
    fn main() {
        let v: Vec<()> = vec![(); 1_000_000]; let s: &[()] = &v;
        println!("  &[()] 长度 {},size_of_val = {} 字节(100 万个零大小元素不占内存)", s.len(), std::mem::size_of_val(s));
        let e: &[u64] = &[]; println!("  空切片 &[u64] 的指针 {:p}:非空 {},对齐到 8: {}(指向「一个对齐的悬空地址」,没有内存可读)", e.as_ptr(), e.as_ptr() as usize != 0, e.as_ptr() as usize % 8 == 0);
    }
''', quiet_src=True); R['zst'] = r['out']
print()
print('== 五:从原始部件构造切片(from_raw_parts)与拆开:chunks、windows、split_first 都只是改指针和长度')
r = tryit('u116g', '''
    fn main() {
        let v: Vec<u16> = (1..=8).collect(); let base = v.as_ptr() as usize;
        let s = unsafe { std::slice::from_raw_parts(v.as_ptr().add(2), 4) }; println!("  from_raw_parts(ptr+2, 4) = {:?}", s);
        let off = |x: &[u16]| (x.as_ptr() as usize - base) / 2;
        println!("  chunks(3):{:?}", v.chunks(3).map(|c| (off(c), c.len())).collect::<Vec<_>>());
        println!("  windows(3) 的前 3 个窗口:{:?}", v.windows(3).take(3).map(|c| (off(c), c.len())).collect::<Vec<_>>());
        let (first, rest) = v.split_first().unwrap(); println!("  split_first:first = {},rest 指针偏移 {} 长度 {}", first, off(rest), rest.len());
        println!("  上面的 (偏移, 长度) 都是以元素为单位,偏移相对于 v 的起点;没有任何元素被复制");
    }
''', quiet_src=True); R['parts'] = r['out']
save('u116', R)
