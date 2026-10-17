from lib import *
R = J('d119')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
r = L('race'); a = L('atomic_req'); rt = L('retry')
steps = [
    step("场景:视图在事务里创建订单,再把订单 id 放进队列,另一个线程(代表任务 worker,有自己的数据库连接)收到 id 后立刻查订单。分别在 atomic() 里入队、事务提交后入队时,看 worker 能不能查到。", n=fl([['视图 / 事务', '创建订单 + 入队'], ['worker(另一个连接)', '收到 id 立刻查订单']], cur=[0, 1]), kv=KV([['worker', '独立线程 + 独立连接']], ['worker'])),
    step("入队后立刻提交:200 次里 worker 每次都查到了(found 200)——在这个环境里 worker 线程被唤醒再发查询的时间,比提交更长(本机 PostgreSQL 临时实例,fsync=off,提交很快)。所以「入队之后立刻提交」这种最短窗口并没有复现出竞态。", t=tl(r[:1]), done=[0], kv=KV([['立刻提交', '200 / 200 查到'], ['结论', '竞态没有复现(窗口太短)']], ['结论'])),
    step("入队后事务还要再做 50 ms 别的事才提交:40 次里 worker 全部查不到(missing 40)。窗口一变长,「任务先于事务提交」就 100% 出现。真实系统里,提交前的其它工作、慢查询、锁等待都会让窗口变长。", t=tl(r[1:2]), mark=[0], kv=KV([['提交前还有 50 ms 工作', '40 / 40 查不到']], ['提交前还有 50 ms 工作'])),
    step("on_commit 里入队:200 次全部查到(found 200)。ATOMIC_REQUESTS=True 时(视图返回后才提交),视图里直接入队与 on_commit 入队,各 200 次请求也都查到——同样是窗口很短,没有复现出失败。", t=tl(r[2:] + a), done=[0, 1], kv=KV([['on_commit', '任何窗口下都安全'], ['ATOMIC_REQUESTS 下直接入队', '本次没有复现失败']], ['on_commit'])),
    step("补救:worker 端加重试(每 20 ms 一次、最多 5 次)。40 次里,第 2 次尝试就查到的有 10 次、第 3 次查到的有 30 次,都在 5 次之内;有效,但这是在消费端打补丁,并且增加了延迟。根本做法还是入队放在 on_commit。", t=tl(rt), done=[0], kv=KV([['重试', '能补救,增加延迟']], ['重试'])),
]
A = dict(
    n=119, series='django', tags='Django,事务,异步任务,竞态,PostgreSQL,真实验证,动画演示',
    desc='事务与异步任务的边界:任务在 atomic 里入队后,提交前还有 50 ms 工作时 worker 40/40 查不到订单;立刻提交或 on_commit 入队时 200/200 查到(窗口很短的情形没有复现竞态);worker 加重试可以补救。',
    lead='把任务发给 Celery 之类的 worker 时,worker 可能比你的事务提交得更快。这篇在真实的 PostgreSQL 上用另一个线程当 worker,诚实地看这个竞态在什么条件下出现、什么条件下没有复现。',
    facts=[('40 / 40 查不到', '任务在 atomic 里入队、提交前还有 50 ms 工作时,worker 立刻查订单'), ('200 / 200 查到', '入队后立刻提交、on_commit 入队、ATOMIC_REQUESTS 下——窗口很短,没有复现失败'), ('重试', 'worker 每 20 ms 重试,第 2–3 次查到')],
    body=[
        sec('worker 会不会先于提交', '', term('', blk('d119', 1)), '<p>这个结果需要小心解读:<b>竞态并没有在最短窗口里复现</b>。我用的临时 PostgreSQL 关掉了 fsync 与同步提交,提交本身很快,而 worker 线程被唤醒并发起查询的时间反而更长。一旦提交前多了 50 ms 的其它工作,失败就是必然的。所以「没复现」不代表安全,只代表窗口够短;生产环境里提交更慢(fsync)、事务更长,更容易出现。</p>'),
        sec('ATOMIC_REQUESTS', '', term('', blk('d119', 2)), '<p><code>ATOMIC_REQUESTS = True</code> 时整个视图在一个事务里,视图返回后才提交,视图里的入队天然早于提交。本次 200 次请求都没有失败,同样是因为窗口太短,没有更多结论。</p>'),
        sec('消费端重试', '', term('', blk('d119', 3)), '<p>重试能补救,但它是让消费端去容忍生产端的错误。生产端用 <code>transaction.on_commit</code> 入队(第 120 篇)才是不产生这个窗口的做法。</p>'),
        sec('分步演示', '', demo('事务与任务边界', [('n', 'flow', '角色'), ('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。自己起的临时 PostgreSQL 16(fsync=off、synchronous_commit=off);worker 是同一进程里的线程 + 独立连接,不是真实的 Celery / RQ', '没有验证:真实的消息队列延迟、fsync 打开时的提交耗时、任务里读到旧状态(未提交的更新)的情形、Celery 的 ETA / countdown 是否足以规避、多数据库路由'],
)
