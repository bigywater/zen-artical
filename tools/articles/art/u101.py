from lib import *
import re
S = SS('u101')
R = J('u101')
fa = re.search(r'分支1 (\d+) 次,分支2 (\d+) 次\(共', R['fair']); f1, f2 = fa.group(1), fa.group(2)
steps = [
    step("tokio::select! 同时等待多个 Future,第一个完成的赢,其余的被 drop。快任务(30 ms)与慢任务(100 ms)一起 select!:先打印「快任务 跑完了」,慢任务的局部变量 Noisy 被 drop(「慢任务 被 drop(取消)」);又等 150 ms,慢任务既没跑完也没再打印 —— 它在 select! 结束时就被取消了。", t=tl(S(1)), mark=lidx(S(1), '慢任务(100ms)', '被 drop(取消)'), done=lidx(S(1), '快任务(30ms) 跑完了', 'select! 的结果'), kv=KV([['赢家', '快任务'], ['输家', '被 drop(取消),不会再运行']], ['输家'])),
    step("取消不安全的 Future 会丢数据:read_then_work 先从通道取走一条消息,再 sleep 100 ms 才返回。放进 select! 与 20 ms 的超时比赛,超时先到,read_then_work 被取消:通道里只剩 [2, 3],消息 1 已经被取走、随着 Future 被 drop 而丢失。", t=tl(S(2)), mark=lidx(S(2), '通道里还剩'), done=lidx(S(2), '20 ms 超时'), kv=KV([['取走消息后 await 被取消', '消息丢失'], ['通道剩余', '[2, 3]']], ['取走消息后 await 被取消'])),
    step("取消安全的写法:select! 的分支里只放 rx.recv()(取消时没取走消息就不会丢),取走后在分支体里处理(分支体不是被 select! 取消的 Future)。三条消息都被处理,handled = [1, 2, 3],100 ms 没有新消息后退出循环,一条都没丢。", t=tl(S(3)), done=lidx(S(3), '处理了', '100 ms'), kv=KV([['分支里的 Future', '只做取消安全的事'], ['处理逻辑', '放进分支体']], ['处理逻辑'])),
    step(f"公平性:两个分支同时就绪时,select! 默认随机选择 —— 10000 次里分支 1 赢 {f1} 次、分支 2 赢 {f2} 次,接近各一半;加 biased; 后总是按书写顺序选第一个就绪的:分支 1 赢 10000 次、分支 2 赢 0 次(可能饿死后面的分支)。", t=tl(S(4)), done=lidx(S(4), '默认(随机)', 'biased;'), b=bars([['默认 分支1', int(f1), f1], ['默认 分支2', int(f2), f2], ['biased 分支1', 10000, '10000'], ['biased 分支2', 0, '0']], 10000, done=[0, 1, 2, 3]), kv=KV([['默认', f'{f1} : {f2}'], ['biased;', '10000 : 0']], ['biased;'])),
    step("timeout 超时后内部的 Future 被 drop:30 ms 超时包住一个要 200 ms 的 async 块,先打印「内部 Future 的局部变量被 drop(超时取消了它)」,timeout 返回 Err(\"deadline has elapsed\");没超时的 timeout 返回 Ok(\"完成\")。", t=tl(S(5)), done=lidx(S(5), 'Ok("完成")'), mark=lidx(S(5), '被 drop', 'deadline has elapsed'), kv=KV([['超时', '内部 Future 被 drop'], ['返回', 'Err(Elapsed)']], ['超时'])),
]
A = mkart('u101', 101, 'Rust,tokio,select,取消安全,真实验证,动画演示',
    f'下载 tokio 验证 select! 的取消语义:失败的分支被 drop;取消不安全的 Future 会丢消息(通道里剩 [2, 3]);把取走与处理分开才安全;默认随机选择({f1}:{f2})对 biased 的 10000:0;timeout 超时时内部 Future 被 drop。',
    'select! 看起来只是「谁先完成选谁」,但被选掉的那些 Future 会被直接 drop,一半做完的工作就此消失。这篇用一个会丢消息的例子说明「取消安全」是什么,再验证 select! 的公平性与 timeout 的取消行为。',
    [('drop', 'select! 中没赢的分支的结局'), ('[2, 3]', '取消不安全的 Future 被取消后,通道里剩下的消息(1 已丢失)'), (f'{f1} 对 {f2}', '默认 select! 在两个分支都就绪时的选择分布(10000 次)')],
    [('先到先得,其余取消', '<p>Future 取消与 drop 的机制见<a href="rust-future-cancel-drop.html">Future 取消与 Drop</a>。</p>'), ('取消不安全的例子', None), ('取消安全的写法', '<p>通道的另一种用法见<a href="rust-async-channel.html">异步 Channel</a>。</p>'), ('公平性', None), ('timeout', None)],
    steps, [ENV_U + '。tokio 1.x(rt、time、macros、sync)', '没有验证:tokio 文档里各个 API 的「取消安全」标注是否与实测一致(只验证了 mpsc::Receiver::recv)、select! 里 else 分支、多个 select! 嵌套、futures::select!、tokio_util::sync::CancellationToken'], 'select! 与取消')
