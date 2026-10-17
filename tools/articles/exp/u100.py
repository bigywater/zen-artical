import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u100'); R = {}
DEPS = 'tokio = { version = "1", features = ["rt", "rt-multi-thread", "time", "macros", "sync"] }'
def build(name, code):
    d = proj(name, {'src/main.rs': code}, deps=DEPS); rc, o = cargo(['build', '--quiet'], d, timeout=900)
    return rc, o, d
def runit(name):
    rc, so, se, _ = run(TG / 'debug' / name); return so.rstrip()
def show_err(o, n=22):
    L = [l for l in o.splitlines() if l.strip()][:n]; print('\n'.join('  ' + l for l in L)); return L
print('== 一:tokio::spawn 要求 Future: Send + \'static;借用局部变量的 async 块不行(E0373)')
rc, o, d = build('u100a', '''
    #[tokio::main(flavor = "current_thread")]
    async fn main() {
        let name = String::from("tokio");
        let h = tokio::spawn(async { println!("hello {}", name); });
        h.await.unwrap();
    }
''')
R['e0373'] = show_err(o)
print()
print('== 二:三种修法:move 把所有权给任务;Arc 共享所有权;Clone 一份')
rc, o, d = build('u100b', '''
    use std::sync::Arc;
    #[tokio::main(flavor = "current_thread")]
    async fn main() {
        let name = String::from("tokio");
        let c = name.clone();
        tokio::spawn(async move { println!("① move 进任务,任务拥有它: {}", c); }).await.unwrap();
        let shared = Arc::new(vec![1, 2, 3]);
        let hs: Vec<_> = (0..3).map(|i| { let s = Arc::clone(&shared); tokio::spawn(async move { s[i] * 10 }) }).collect();
        let mut out = vec![]; for h in hs { out.push(h.await.unwrap()); }
        println!("② 3 个任务共享 Arc<Vec>:{:?}(strong_count = {})", out, Arc::strong_count(&shared));
        println!("③ clone 之后原来的 name 仍然可用: {}", name);
    }
''')
print('  编译退出码', rc); print('  ' + runit('u100b').replace('\n', '\n  ')); R['fix'] = runit('u100b')
print()
print('== 三:不 spawn,而是在同一个任务里并发(join!):可以借用局部变量,不需要 \'static')
rc, o, d = build('u100c', '''
    use std::time::Duration;
    #[tokio::main(flavor = "current_thread")]
    async fn main() {
        let name = String::from("tokio"); let data = vec![1, 2, 3];
        let (a, b) = tokio::join!(
            async { tokio::time::sleep(Duration::from_millis(20)).await; format!("{} 长度 {}", name, name.len()) },
            async { tokio::time::sleep(Duration::from_millis(10)).await; data.iter().sum::<i32>() },
        );
        println!("join! 里的两个 async 块借用了 name 和 data:{} / {};name 与 data 之后仍然可用: {} {:?}", a, b, name, data);
    }
''')
print('  编译退出码', rc); print('  ' + runit('u100c').replace('\n', '\n  ')); R['join'] = runit('u100c')
print()
print('== 四:\'static 不等于「活到程序结束的值」,而是「不含非 \'static 的借用」:拥有数据的任务满足 \'static;用 Box::leak 可以得到 &\'static(代价是泄漏)')
rc, o, d = build('u100d', '''
    fn needs_static<T: 'static>(_: T) {}
    fn main() {
        let owned = String::from("x"); needs_static(owned);                  // 拥有所有权的 String 是 'static
        let lit: &'static str = "字面量"; needs_static(lit);                  // 字面量是 &'static
        let leaked: &'static mut Vec<i32> = Box::leak(Box::new(vec![1, 2, 3])); needs_static(leaked);   // 泄漏出来的引用
        println!("三种 'static 都通过了编译:拥有的 String、字面量、Box::leak 出来的 &'static mut");
        let local = 5; let r = &local;
        needs_static(r);
    }
''')
R['static'] = show_err(o, 14)
print()
print('== 五:在 spawn 的任务里再借用任务自己的数据是没问题的(借用发生在任务内部)')
rc, o, d = build('u100e', '''
    #[tokio::main(flavor = "current_thread")]
    async fn main() {
        let total = tokio::spawn(async move { let v = vec![1, 2, 3, 4]; let r = &v; tokio::task::yield_now().await; r.iter().sum::<i32>() }).await.unwrap();
        println!("任务内部借用自己的 v,跨 await 也没问题:{}", total);
    }
''')
print('  编译退出码', rc); print('  ' + runit('u100e')); R['inner'] = runit('u100e')
save('u100', R)
