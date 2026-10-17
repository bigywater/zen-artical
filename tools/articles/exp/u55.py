import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u55'); R = {}
print('== 一:drop 的顺序:局部变量按声明的相反顺序;结构体字段按声明顺序;Vec 元素按下标顺序')
r = tryit('u55a', '''
    struct D(&'static str);
    impl Drop for D { fn drop(&mut self) { println!("  drop {}", self.0); } }
    struct Pair { first: D, second: D }
    fn main() {
        println!("-- 局部变量");
        { let _a = D("a"); let _b = D("b"); let _c = D("c"); }
        println!("-- 结构体字段");
        { let _p = Pair { first: D("p.first"), second: D("p.second") }; }
        println!("-- Vec 元素");
        { let _v = vec![D("v0"), D("v1"), D("v2")]; }
        println!("-- 临时值在语句结束时 drop");
        { let _ = D("临时"); println!("  `let _ =` 之后(临时值已经 drop)"); let _keep = D("绑定"); println!("  `let _keep =` 之后(还没 drop)"); }
    }
''', quiet_src=False)
print()
print('== 二:提前释放:std::mem::drop;不能手动调用 .drop();mem::forget 让 Drop 不执行')
r = tryit('u55b', '''
    struct D(&'static str);
    impl Drop for D { fn drop(&mut self) { println!("  drop {}", self.0); } }
    fn main() {
        let a = D("early"); println!("drop(a) 之前"); drop(a); println!("drop(a) 之后");
        let f = D("forgotten"); std::mem::forget(f); println!("forget 之后:不会看到 drop forgotten");
        let _end = D("end");
    }
''', quiet_src=False)
r = tryit('u55c', '''
    struct D;
    impl Drop for D { fn drop(&mut self) { println!("drop"); } }
    fn main() { let d = D; d.drop(); }
''', maxlines=22); R['e040'] = r['diag'].split('\n')[0]
print()
print('== 三:移动之后只 drop 一次(由最后的所有者);条件移动也正确')
r = tryit('u55d', '''
    struct D(&'static str);
    impl Drop for D { fn drop(&mut self) { println!("  drop {}", self.0); } }
    fn consume(d: D) { println!("  consume 里拿到 {}", d.0); }
    fn main() {
        let a = D("a"); consume(a);
        let b = D("b");
        if std::env::args().count() > 5 { consume(b); } else { println!("  没有移动 b"); }
        println!("main 结束");
    }
''', quiet_src=False)
print()
print('== 四:panic 展开(unwinding)时会 drop 已创建的值;process::exit 则不会')
r = tryit('u55e', '''
    struct D(&'static str);
    impl Drop for D { fn drop(&mut self) { println!("  drop {}", self.0); } }
    fn main() { let _g = D("guard"); println!("即将 panic"); panic!("boom"); }
''', quiet_src=True); R['panic_out'] = r['out'].strip()
print('  源码:持有 D("guard") 后 panic!("boom")')
print('  stdout:', r['out'].strip().replace('\n', ' | ')); print('  stderr 第一行:', [l for l in r.get('err', '').split('\n') if 'panicked' in l or 'boom' in l][:2])
r = tryit('u55f', '''
    struct D(&'static str);
    impl Drop for D { fn drop(&mut self) { println!("  drop {}", self.0); } }
    fn main() { let _g = D("guard"); println!("即将 exit"); std::process::exit(0); }
''', quiet_src=True); print('  process::exit 版本的 stdout:', r['out'].strip().replace('\n', ' | '), '(没有 drop guard)')
save('u55', R)
