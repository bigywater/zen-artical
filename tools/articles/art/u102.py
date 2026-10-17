from lib import *
import re
S = SS('u102')
R = J('u102')
ub = re.search(r'用时 (\d+) ms.*积压了 (\d+) 条', R['unbounded']); ut, un = ub.group(1), ub.group(2)
steps = [
    step("有界 mpsc(tokio::sync::mpsc,容量 2):生产者连续 send(1..=6).await,消费者每条处理 50 ms。前两条 send 立即返回(0 ms),send(3) 在消费者取走 1 之后返回(0 ms),send(4) 要等到约 60 ms(消费者取走 2),send(5) 约 110 ms,send(6) 约 170 ms —— 通道满时 send().await 会挂起,生产者被消费者的速度拖住,这就是「背压」。", t=tl(S(1)), done=lidx(S(1), 'send(1)', 'send(2)', 'send(3)'), mark=lidx(S(1), 'send(4)', 'send(5)', 'send(6)'), kv=KV([['容量 2', '满了 send().await 挂起'], ['生产速度', '被消费速度(50 ms/条)拖住']], ['生产速度'])),
    step(f"无界 mpsc:send 是同步方法,永不等待。生产者发完 10 万条只用 {ut} ms,此时队列里积压 {un} 条;消费者之后才一条条取走。生产比消费快时没有任何背压,内存没有上限。", t=tl(S(2)), done=lidx(S(2), '生产者发完', '消费者取走'), kv=KV([['unbounded send', '同步,不 await'], ['积压', f'{un} 条']], ['积压'])),
    step("oneshot:只传一个值。发送端 send(\"结果\") 后,接收端 rx.await 得到 Ok(\"结果\");发送端 drop 而没发值,接收端得到 Err(RecvError);接收端先 drop,send(5) 返回 Err(5),把值退回给发送方。send 消耗发送端,不可能发第二次。", t=tl(S(3)), done=lidx(S(3), '收到', '发送端 drop 后', '接收端 drop 后'), kv=KV([['发送端 drop', 'rx.await → Err'], ['接收端 drop', 'send → Err(原值)']], ['发送端 drop'])),
    step("broadcast:每个订阅者都收到每条消息。两个订阅者各收到 Ok(1) Ok(2) Ok(3)。容量 4 的通道里再发 8 条(10..=17),最旧的 4 条被覆盖,慢订阅者的第一次 recv 得到 Err(Lagged(4))(错过了 4 条),随后继续收到 Ok(14) Ok(15) Ok(16) Ok(17)。", t=tl(S(4)), done=lidx(S(4), '两个接收者', '之后继续'), mark=lidx(S(4), 'Lagged(4)'), kv=KV([['订阅者各收一份', 'r1、r2 都收到 1..=3'], ['慢订阅者', 'Lagged(4),错过 4 条']], ['慢订阅者'])),
    step("watch:只保留最新值。连续 send v1、v2、v3 之后,接收者看到的当前值是 v3,中间的 v1 与 v2 被跳过;changed() 返回新值 v3 后,没有新值时再 changed() 一直等,30 ms 后超时。适合「当前配置/状态」这类只关心最新值的场景。", t=tl(S(5)), done=lidx(S(5), 'v3', 'changed()'), mark=lidx(S(5), '超时'), kv=KV([['watch', '只有最新值'], ['v1 v2', '被跳过']], ['watch'])),
]
A = mkart('u102', 102, 'Rust,tokio,异步通道,mpsc,真实验证,动画演示',
    f'下载 tokio 验证四种异步通道:有界 mpsc 满了 send().await 挂起(背压);无界 mpsc 10 万条 {ut} ms 发完、积压 {un} 条;oneshot 的 drop 语义;broadcast 的 Lagged(4);watch 只保留最新值(v1、v2 被跳过)。',
    'tokio 有 mpsc、oneshot、broadcast、watch 四种常用通道,各自语义很不一样:满了会怎样、慢接收者会怎样、能不能多发。这篇每一种都用一个小程序跑出真实输出。',
    [('背压', '有界 mpsc 满了之后 send().await 挂起,生产者被消费者拖住'), (f'{un} 条', '无界 mpsc 里积压的消息数'), ('Lagged(4)', 'broadcast 慢订阅者错过 4 条的返回')],
    [('有界 mpsc 与背压', '<p>标准库同步通道见<a href="rust-channel-message-passing.html">Channel 消息传递</a>与<a href="rust-mpsc.html">mpsc</a>。</p>'), ('无界 mpsc', None), ('oneshot', None), ('broadcast', '<p>取消安全相关的 recv 见<a href="rust-select-cancellation.html">select! 取消竞争</a>。</p>'), ('watch', None)],
    steps, [ENV_U + '。tokio 1.x(rt、time、macros、sync)', '没有验证:多生产者多消费者的 async-channel / flume、有界 mpsc 的 permit(reserve)用法、broadcast 在大量订阅者下的性能、watch 的 borrow 持锁时间、无界通道积压对内存的实际占用'], '异步通道')
