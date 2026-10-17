from lib import *
S = SS('u148')
steps = [
    step("File::lock 系列(标准库,稳定):另一个进程持有独占锁(lock())时,try_lock 得到 Err(WouldBlock),try_lock_shared 也是 WouldBlock;lock() 会阻塞:持有者睡 600 ms 后退出,第二个进程的 lock() 实际等了约 600 ms 才拿到。", t=tl(S(1)), done=lidx(S(1), 'try_lock(独占)', 'try_lock_shared', 'lock(独占)阻塞'), kv=KV([['独占锁被持有', 'try_lock / try_lock_shared 都 WouldBlock'], ['lock()', '阻塞到持有者释放']], ['lock()'])),
    step("共享锁允许多个读者并存:另一个进程持有共享锁(lock_shared)时,再来 try_lock_shared 立刻拿到,而 try_lock(独占)得到 WouldBlock。读写锁的语义,但作用在文件上,跨进程有效。", t=tl(S(2)), done=lidx(S(2), 'try_lock_shared(共享):拿到'), mark=lidx(S(2), 'try_lock(独占)'), kv=KV([['共享 + 共享', '都能拿到'], ['共享 + 独占', 'WouldBlock']], ['共享 + 独占'])),
    step("持有锁的进程崩溃也不会留下死锁:持有独占锁的子进程运行时,try_lock 得到 WouldBlock;对它 kill -9 之后,再 try_lock 立刻拿到。锁随进程终止自动释放,所以文件锁适合做「单实例」检查或互斥访问,不需要清理。", t=tl(S(3)), done=lidx(S(3), 'kill -9 持有者之后'), mark=lidx(S(3), '持有者运行中'), kv=KV([['持有者运行中', 'WouldBlock'], ['kill -9 之后', '拿到']], ['kill -9 之后'])),
    step("锁是建议性的:持有独占锁期间,另一个进程不加锁直接打开文件写入,成功,文件内容变成 \"written without taking the lock\"。只有大家都遵守先加锁的约定,锁才有用。", t=tl(S(4)), done=lidx(S(4), '没有加锁直接写文件', '文件内容'), kv=KV([['不加锁的写者', '不受阻拦'], ['锁', '建议性,靠约定']], ['锁'])),
    step("同一个进程里两次 open 得到两个独立的句柄:句柄 a 拿到独占锁后,句柄 b 的 try_lock 得到 WouldBlock(锁跟着打开的文件句柄,不只是按进程);a 再 try_lock 一次已经持有的锁,成功(幂等);a.unlock() 之后 b 拿到;b 被 drop(关闭文件)时锁随之释放,新开句柄 c 也能拿到。", t=tl(S(5)), done=lidx(S(5), '句柄 a 拿到', 'a.unlock()', '再开一个句柄 c'), mark=lidx(S(5), '同一进程里的句柄 b'), kv=KV([['同进程两个句柄', '互相冲突'], ['重复加锁', '幂等'], ['drop(File)', '释放锁']], ['同进程两个句柄'])),
]
A = mkart('u148', 148, 'Rust,文件锁,File::lock,并发,真实验证,动画演示',
    '用多个真实进程验证标准库的 File::lock:独占锁被持有时 try_lock/try_lock_shared 得 WouldBlock、lock 阻塞约 600 ms;共享锁可并存;kill -9 持有者后锁自动释放;锁是建议性的(不加锁的写者照样写);同一进程的两个句柄会冲突、重复加锁幂等、drop 释放。',
    '想保证同一时刻只有一个进程在改某个文件,怎么办?这篇用标准库自带的文件锁 API,在真实的多进程场景下验证独占与共享、阻塞与非阻塞、崩溃后的释放,以及「建议性」到底意味着什么。',
    [('WouldBlock', '另一个进程持有独占锁时 try_lock 的结果'), ('0 次清理', 'kill -9 持有者之后需要手动清理锁的次数(自动释放)'), ('建议性', '不加锁的进程仍然可以写被锁定的文件')],
    [('独占锁与阻塞', '<p>文件基础见<a href="rust-std-fs.html">std::fs 文件读写</a>;子进程见<a href="rust-subprocess-command.html">子进程与 Command</a>。</p>'), ('共享锁', None), ('进程崩溃', None), ('建议性锁', None), ('同一个进程里', '<p>文件描述符的释放见<a href="rust-file-descriptor-release.html">文件描述符与资源释放</a>。</p>')],
    steps, [ENV_U + '', '没有验证:NFS 等网络文件系统上的锁行为、Windows 的强制锁语义、fcntl 记录锁(按字节范围)、fork 之后子进程继承锁的情况、死锁检测(标准库不提供)、锁升级与降级'], '文件锁')
