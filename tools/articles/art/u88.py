from lib import *
S = SS('u88')
steps = [
    step("通道的基本用法:mpsc::channel() 得到 (tx, rx)。子线程 sleep 100 ms 后 tx.send(String),主线程的 rx.recv() 一直阻塞到收到,约 100 毫秒后得到 \"来自子线程\"。", t=tl(S(1)), done=lidx(S(1), 'recv 阻塞了'), kv=KV([['recv()', '阻塞到有消息'], ['耗时', '约 100 ms']], ['recv()'])),
    step("send 会移动值的所有权:tx.send(s) 之后再 println!(\"{}\", s) 报 error[E0382]: borrow of moved value: `s`。发送之后值属于通道/接收方,发送方不能再用。", t=tl(S(1)), mark=lidx(S(1), 'error[E0382]'), kv=KV([['send(s)', '移动 s'], ['之后用 s', 'E0382']], ['之后用 s'])),
    step("所有发送端 drop 之后通道关闭:子线程结束时 tx 随之 drop(先打印「子线程结束」),主线程的 rx.iter().collect() 收到 [1, 2, 3] 后自然结束;之后再 recv() 返回 Err(RecvError)。", t=tl(S(2)), done=lidx(S(2), '子线程结束', 'for / iter', '再 recv'), kv=KV([['所有 tx 被 drop', 'recv 返回 Err,迭代结束']], ['所有 tx 被 drop'])),
    step("不阻塞的接收:空通道 try_recv() 得 Err(Empty);recv_timeout(50ms) 得 Err(Timeout);有值时 try_recv() 得 Ok(1)。发送端都 drop 后,try_recv 与 recv_timeout 都返回 Err(Disconnected) —— 区分「暂时没有」与「永远没有」。", t=tl(S(3)), done=lidx(S(3), 'Ok(1)'), mark=lidx(S(3), 'Empty', 'Timeout', 'Disconnected'), kv=KV([['Empty / Timeout', '暂时没有'], ['Disconnected', '发送端都没了']], ['Disconnected'])),
    step("接收端 drop 之后 send 返回 Err,并把没送出去的值还给你:错误信息「sending on a closed channel」,e.0 就是原来的 \"没人收\"。", t=tl(S(4)), done=lidx(S(4), 'send 失败'), kv=KV([['send 失败', 'SendError(原值)']], ['send 失败'])),
    step("通道里的值必须是 Send:发送 Rc<i32> 报 error[E0277]: `Rc<i32>` cannot be sent between threads safely,note 说「required for `Sender<Rc<i32>>` to implement `Send`」。", t=tl(S(5)), mark=lidx(S(5), 'error[E0277]', 'Sender<Rc<i32>>'), kv=KV([['Sender<T>: Send', '当且仅当 T: Send']], ['Sender<T>: Send'])),
    step("send 只转移所有权,不复制数据:一个 100 万个 u64 的 Vec 发送前后,缓冲区地址相同(true)—— 接收方拿到的是同一块堆内存。", t=tl(S(6)), done=lidx(S(6), '地址相同', '没有被复制', '== 接收后'), kv=KV([['100 万个 u64', '没有被复制,地址不变']], ['100 万个 u64'])),
]
A = mkart('u88', 88, 'Rust,channel,消息传递,mpsc,真实验证,动画演示',
    '用真实运行验证通道的基本语义:recv 阻塞约 100 ms 等到消息;send 移动所有权(E0382);所有发送端 drop 后 recv 返回 Err、迭代结束;try_recv 区分 Empty 与 Disconnected;接收端 drop 后 send 退回原值;Rc 不能发送(E0277);发送 100 万元素的 Vec 不复制数据。',
    '“不要通过共享内存来通信,而要通过通信来共享内存。”通道到底怎么工作?send 后原变量还能用吗?什么时候 recv 会结束?值有没有被复制?这篇把通道最基本的行为逐条验证。',
    [('Disconnected', '所有发送端 drop 之后 try_recv / recv_timeout 的错误'), ('0 次复制', '发送 100 万个 u64 的 Vec 时数据的复制次数(地址不变)'), ('E0382', 'send 之后再使用原变量')],
    [('send 与 recv', None), ('通道什么时候关闭', None), ('不阻塞的接收', None), ('接收端关闭', None), ('能传什么类型', '<p>Send 的规则见<a href="rust-send-sync.html">Send 与 Sync</a>。</p>'), ('零复制', '<p>多个生产者的情形见<a href="rust-mpsc.html">mpsc 多生产者单消费者</a>。</p>')],
    steps, [ENV_U, '没有验证:通道内部的数据结构(链表还是数组)、无界通道在生产快于消费时的内存增长、select 式多通道等待(标准库没有,放在 async 部分)、crossbeam-channel 的性能对比'], '通道')
