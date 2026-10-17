from lib import *
S = SS('u106')
steps = [
    step("为什么需要 Pin:自引用结构体 SelfRef { data: [u8; 4], ptr: *const u8 } 的 ptr 指向自己的 data。就地建好后二者相同(true);按值移动一次(consume(s) 把它搬到另一块栈空间)之后,data 在新地址,ptr 仍指向旧地址,二者不再相同(false)—— 指针悬空了。", t=tl(S(1)), done=lidx(S(1), '创建后'), mark=lidx(S(1), '移动后'), kv=KV([['创建后', 'ptr == &data'], ['移动后', 'ptr 仍指向旧地址']], ['移动后'])),
    step("Pin<Box<T>> 保证堆上数据的地址不变:Box::pin(Data { … }) 之后把 Pin<Box<Data>> 移动两次(赋值、放进 Vec 再取出),被移动的只是那个指针,Data 的地址始终不变(true)。这就是 async 运行时把 Future 放进 Pin<Box<…>> 的原因。", t=tl(S(2)), done=lidx(S(2), '地址不变'), kv=KV([['Pin<Box<T>>', '移动指针,不移动堆上的值']], ['Pin<Box<T>>'])),
    step("!Unpin 的类型不能拿到 &mut T:对含 PhantomPinned 的 NoMove,p.as_mut().get_mut() 报 error[E0277]: `PhantomPinned` cannot be unpinned,note 「required by a bound in `Pin::<&'a mut T>::get_mut`」—— 否则拿到 &mut 就能 mem::swap 把它搬走,pin 就白做了。", t=tl(S(3)), mark=lidx(S(3), 'error[E0277]', 'get_mut'), kv=KV([['get_mut()', '要求 T: Unpin'], ['!Unpin', 'E0277']], ['!Unpin'])),
    step("同样,Pin::new(&x) 要求 T: Unpin,对 !Unpin 的 NoMove 报同样的 E0277,note「required by a bound in `Pin::<Ptr>::new`」。固定 !Unpin 的值只能用 Box::pin、pin! 宏或 unsafe 的 new_unchecked。", t=tl(S(3)), mark=lidx(S(3), 'Pin::<Ptr>::new'), kv=KV([['Pin::new', '要求 T: Unpin'], ['!Unpin 要固定', 'Box::pin / pin!']], ['!Unpin 要固定'])),
    step("Unpin 是自动 trait,逐个编译检查:i32、String、Vec<u8>、Box<i32>、&mut i32 都是 Unpin(Pin 对它们没有限制);PhantomPinned 与含它的结构体不是;async fn 的 Future 不是 Unpin;连没有借用的 async { 1 + 1; } 块也不是 Unpin(编译器生成的状态机一律 !Unpin)。", t=tl(S(4)), done=lidx(S(4), 'i32', 'String', 'Vec<u8>', 'Box<T>', '&mut i32'), mark=lidx(S(4), 'PhantomPinned', '含 PhantomPinned', 'async fn', 'async 块'), kv=KV([['普通类型', 'Unpin ✓'], ['PhantomPinned', 'Unpin ✗'], ['async 状态机', 'Unpin ✗']], ['async 状态机'])),
    step("栈上固定:std::pin::pin! 宏把值固定在当前栈帧里,不需要堆分配:pin!(work()) 得到 Pin<&mut impl Future>,poll 得到 Ready(6)(跨 await 持有引用的 Future 在栈上也能安全 poll)。对 Unpin 的类型,pin! 之后仍然可以取 &mut(String 用 mem::take 取出 \"x\")。", t=tl(S(5)), done=lidx(S(5), 'Ready(6)', 'x'), kv=KV([['pin!', '固定在栈上,零分配'], ['Unpin 类型', '仍可 &mut']], ['pin!'])),
]
A = mkart('u106', 106, 'Rust,Pin,Unpin,自引用,真实验证,动画演示',
    '用真实运行验证 Pin 与 Unpin:自引用结构体被移动后 ptr 指向旧地址;Pin<Box<T>> 移动两次后数据地址不变;!Unpin 类型拿不到 &mut(get_mut / Pin::new 报 E0277);逐个检查 Unpin(普通类型是,PhantomPinned 与所有 async 块不是);pin! 宏固定在栈上并 poll 出 Ready(6)。',
    'Pin 常被说成「难懂」。这篇不讲抽象定义,而是先让一个自引用结构体真的被移动成悬空指针,再验证 Pin<Box> 怎样保住地址、哪些类型需要 Pin、编译器怎么拦住对 !Unpin 类型的 &mut。',
    [('false', '自引用结构体被移动后 ptr == &data 的结果'), ('true', 'Pin<Box<T>> 被移动两次后数据地址不变'), ('E0277', 'Pin::new / get_mut 用于 !Unpin 类型的错误码')],
    [('为什么需要 Pin', '<p>自引用的 Future 来自 async 状态机,见<a href="rust-async-await-state-machine.html">async/await 状态机</a>。</p>'), ('Pin<Box<T>>', None), ('!Unpin 与 &mut', None), ('哪些类型是 Unpin', None), ('栈上固定', '<p>Pin 在 poll 里的使用见<a href="rust-custom-future.html">自定义 Future</a>。</p>')],
    steps, [ENV_U, '没有验证:Pin::new_unchecked 的 unsafe 契约、结构投影(pin-project)、Drop 对 pinned 值的保证、Pin<&mut T> 的 as_mut/set 用法、一个 !Unpin 类型被 Pin 之后 mem::swap 的编译错误细节'], 'Pin 与 Unpin')
