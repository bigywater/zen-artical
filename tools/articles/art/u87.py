from lib import *
S = SS('u87')
R = J('u87'); nord = len(set(R['orders']))
mt = __import__('re').search(r'平均 (\d+) µs', R['scope']).group(1)
steps = [
    step("thread::spawn 返回 JoinHandle,join() 得到线程的返回值(包在 Result 里):子线程算出 1+…+10 = 55。主线程名是 Some(\"main\"),spawn 出来的线程默认没有名字(None),两个线程的 id 不同;用 Builder 可以起名,worker-7 的线程里读到的名字就是 worker-7。", t=tl(S(1)), done=lidx(S(1), '主线程名', 'Builder 命名'), kv=KV([['主线程', 'Some(\"main\")'], ['spawn 的线程', '默认 None'], ['Builder::name', '可命名']], ['spawn 的线程'])),
    step("闭包借用了局部变量 v 就不能传给 spawn:error[E0373]: closure may outlive the current function, but it borrows `v`,note 说「function requires argument type to outlive `'static`」,help 建议加 move。", t=tl(S(2)), mark=lidx(S(2), 'error[E0373]', "'static"), kv=KV([['spawn 要求', "闭包 'static"], ['借用局部变量', 'E0373']], ['借用局部变量'])),
    step("加了 move,v 的所有权进了子线程:主线程再 println!(\"{:?}\", v) 报 error[E0382]: borrow of moved value: `v`,help 建议先 clone 一份再 move。", t=tl(S(2)), mark=lidx(S(2), 'error[E0382]'), kv=KV([['move 之后', '主线程不能再用 v']], ['move 之后'])),
    step("不 join:main 走到末尾进程就结束了,sleep 200 ms 的子线程来不及打印,stdout 只有「主线程到达末尾(join = false)」;带 join 参数运行,先打印主线程那行,等 join 返回前子线程打印「子线程跑完了」。", t=tl(S(3)), mark=lidx(S(3), "('join',)"), done=lidx(S(3), "参数 ()"), kv=KV([['不 join', '子线程被进程退出终止'], ['join', '等线程跑完']], ['不 join'])),
    step(f"线程调度没有固定顺序:8 个线程各把自己的编号追加进 Vec,同一个程序连跑 8 次,得到 {nord} 种不同的顺序(例如 {R['orders'][0]}、{R['orders'][1]}、{R['orders'][6]})。", t=tl(S(4)), done=lidx(S(4), '8 次运行'), kv=KV([['8 次运行', f'{nord} 种顺序']], ['8 次运行'])),
    step(f"thread::scope 不需要 move:两个线程借用 data 的左右两半(split_at_mut),分别乘 10、加 1,data = [10, 20, 30, 5, 6, 7],合计 78;离开 scope 时自动 join。spawn + join 一个空线程平均约 {mt} µs(release,2000 次)。", t=tl(S(5)), done=lidx(S(5), 'scope 里', 'spawn + join'), kv=KV([['scope', '可借用局部变量,自动 join'], ['空线程 spawn+join', f'约 {mt} µs']], ['scope'])),
    step("线程栈大小可以用 Builder 指定:递归 2000 层(每层一个 256 字节数组)在 2048 KiB 的栈上成功(返回 2000);栈缩到 512、256、64 KiB 都栈溢出,stderr 是 fatal runtime error: stack overflow, aborting,进程被信号 6 终止 —— 栈溢出不是 panic,不能被 join 捕获。", t=tl(S(6)), done=lidx(S(6), '栈 2048'), mark=lidx(S(6), '栈 512', '栈 256', '栈 64'), kv=KV([['2048 KiB', '成功'], ['512 / 256 / 64 KiB', '栈溢出 abort']], ['512 / 256 / 64 KiB'])),
]
A = mkart('u87', 87, 'Rust,线程,spawn,join,真实验证,动画演示',
    f'用真实运行验证线程的创建与回收:join 返回结果、线程名与 id;借用局部变量报 E0373,move 后主线程不能再用(E0382);不 join 时子线程被进程退出终止;8 次运行 {nord} 种执行顺序;thread::scope 借用无需 move,spawn+join 约 {mt} µs;小栈上递归 2000 层栈溢出 abort。',
    'thread::spawn 看起来简单,实际上有 move、join、栈大小、不确定顺序等一连串规则。这篇每一条都用真实运行验证:什么时候要 move、不 join 会怎样、顺序真的不确定吗、scope 又好在哪、栈溢出会怎样。',
    [(f'{nord} / 8', '同一程序 8 次运行得到的不同执行顺序数'), (f'约 {mt} µs', 'spawn + join 一个空线程的平均耗时(release)'), ('abort', '线程栈溢出的结局,不是可捕获的 panic')],
    [('JoinHandle 与线程名', None), ('move 与 spawn', '<p>Send 的要求见<a href="rust-send-sync.html">Send 与 Sync</a>。</p>'), ('不 join 会怎样', None), ('执行顺序', None), ('thread::scope', None), ('栈大小', None)],
    steps, [ENV_U + '。耗时 release 构建', '没有验证:默认栈大小的具体数值(只验证了 2048 KiB 够用、512 KiB 不够这个例子)、线程数上限、线程局部存储、park/unpark、线程优先级与亲和性、join 在子线程 panic 时的返回(见 panic 一篇)'], '线程')
