import re
from lib import *
S = SS('u29')
m = re.findall(r'每次约 ([\d.]+) ns', '\n'.join(S(4))); rc_ns, deep_ns = float(m[0]), float(m[1])
steps = [
    step("Rc<T> 让多个所有者共享同一份数据,用引用计数记录所有者数量:Rc::new 之后 strong_count = 1;Rc::clone 之后 2;内层再 clone 出 c 为 3(a、b、c 指向同一块内存,Rc::ptr_eq 为 true);c 离开作用域回到 2;drop(b) 之后回到 1。最后一个所有者消失时数据才被释放。", t=tl(S(1)), done=lidx(S(1), 'strong_count'), kv=KV([['Rc::clone', '计数 +1,不复制数据'], ['离开作用域 / drop', '计数 -1']], ['Rc::clone'])),
    step("Rc 里的数据默认只读:a.push(4) 报 error[E0596]: cannot borrow data in an `Rc` as mutable(Rc 没有实现 DerefMut)。想修改有两条路:Rc::get_mut 只在唯一所有者时返回 Some(独占时成功,有第二个所有者时返回 None);Rc::make_mut 是写时复制 —— 发现不是唯一所有者就先克隆一份再修改,之后 a = [1, 2, 3, 4, 5]、b 仍是 [1, 2, 3, 4],两者不再指向同一块内存。", t=tl(S(2)), mark=lidx(S(2), 'error[E0596]'), done=lidx(S(2), 'make_mut 之后'), kv=KV([['直接修改', 'E0596'], ['make_mut', '写时复制']], ['make_mut'])),
    step("Rc 不是 Send:把它 move 进 thread::spawn 的闭包,报 error[E0277]: `Rc<i32>` cannot be sent between threads safely(the trait `Send` is not implemented for `Rc<i32>`)。原因是它的计数不是原子的,多线程同时增减会出错;跨线程要用 Arc。", t=tl(S(3)), mark=lidx(S(3), 'error[E0277]'), kv=KV([['Rc 跨线程', 'E0277(不是 Send)'], ['替代', 'Arc']], ['Rc 跨线程'])),
    step(f"内存布局与成本:Rc<u64> 本身是 8 字节指针,Rc::new(0u64) 在堆上分配了 24 字节(强引用计数 8 + 弱引用计数 8 + 数据 8)。Rc::clone 共享 1 MiB 的数据每次约 {rc_ns:.1f} ns(只加一个计数),而把同样的 Vec<u8> 深克隆每次约 {deep_ns:,.0f} ns —— 相差约 {deep_ns/rc_ns:,.0f} 倍。", t=tl(S(4)), mark=lidx(S(4), 'Rc::clone'), b=bars([['Rc::clone', rc_ns, f'{rc_ns:.1f} ns'], ['Vec 深克隆 1 MiB', deep_ns, f'{deep_ns:,.0f} ns']], deep_ns, mark=[1], done=[0]), kv=KV([['Rc::clone', f'约 {rc_ns:.1f} ns'], ['Vec 克隆 1 MiB', f'约 {deep_ns/1000:.1f} µs']], ['Rc::clone'])),
]
A = mkart('u29', 29, 'Rust,Rc,引用计数,共享所有权,真实验证,动画演示',
    f'用真实编译与计时验证 Rc<T>:strong_count 随 clone 与 drop 变化;数据只读(E0596),get_mut 只在独占时成功、make_mut 写时复制;Rc 不是 Send(E0277);Rc<u64> 堆上 24 字节,Rc::clone 约 {rc_ns:.1f} ns 而深克隆 1 MiB 约 {deep_ns:,.0f} ns。',
    'Rc 解决的是「单线程里一份数据有多个所有者」。这篇用真实输出把它的核心行为逐条验证:计数怎么变、数据为什么只读以及怎么修改、为什么不能跨线程,以及它在内存里的样子和 clone 的成本。',
    [('24 字节', 'Rc::new(0u64) 在堆上分配的大小(两个计数 + 数据)'), ('E0277', 'Rc 不是 Send,不能 move 进 thread::spawn'), (f'≈ {deep_ns/rc_ns:,.0f} 倍', 'Vec<u8>(1 MiB) 深克隆相对 Rc::clone 的耗时')],
    [('引用计数', None), ('只读与修改', None), ('不是 Send', '<p>多线程要用 Arc,见<a href="rust-arc-thread-sharing.html">Arc&lt;T&gt; 与跨线程共享所有权</a>;Send 的含义见<a href="rust-send-sync.html">Send 与 Sync</a>。</p>'), ('布局与成本', '<p>循环引用会让计数永远不归零,见<a href="rust-weak-cycles.html">Weak&lt;T&gt; 解决循环引用</a>;需要修改共享数据时配合<a href="rust-refcell-runtime-borrow.html">RefCell</a>。内存布局见<a href="rust-box-rc-arc-layout.html">Box、Rc、Arc 的内存布局</a>。</p>')],
    steps, [ENV_U + '。计时为 release 构建的单次运行', '没有验证:Rc 的弱引用计数在 Weak 存在时的变化(见 Weak 一篇)、Rc<str> 与 Rc<[T]>、Rc::try_unwrap、Rc 的 clone 在优化后是否被消除(只测了单次 clone 的循环平均)'], 'Rc<T>')
