from lib import *
S = SS('m44')
steps = [
    step("原子领取:8 个 worker 各自循环 findOneAndUpdate({status: \"pending\"}) 设成 running,直到队列空,2,000 个任务。耗时 0.27 s(7,462 个/秒);领取总数 2,000,不同的任务 2,000,没有重复领取;各 worker 领到 [259, 240, 239, 253, 246, 264, 257, 242] 个;数据库里 tries > 1 的任务数是 0。", t=tl(S(1)), mark=lidx(S(1), '没有重复领取', 'tries>1 的任务数 0'), done=lidx(S(1), '耗时 0.27 s'), kv=KV([['findOneAndUpdate', '查找 + 修改是一个原子操作'], ['2,000 个任务', '2,000 次领取,没有重复'], ['负载均衡', '每个 worker 约 250 个']], ['findOneAndUpdate'])),
    step("有缺陷的做法:先 find 一个 pending 再 update 它为 running,两步中间没有保护。8 个 worker 共领取 8,377 次,只有 2,000 个不同的任务,6,377 个任务被多个 worker 同时领到(重复处理);耗时 2.26 s。", t=tl(S(2)), mark=lidx(S(2), '重复处理'), done=lidx(S(2), '耗时 2.26 s'), b=bars([['原子领取', 2000, '2,000 次领取'], ['先 find 再 update', 8377, '8,377 次领取']], 8377, mark=[1], done=[0]), kv=KV([['两步领取', '多个 worker 抢到同一个任务'], ['重复处理', '6,377 个任务']], ['两步领取'])),
    step("折中:update 时带条件 status: \"pending\" 并检查 modified_count,没抢到就重来。领取 2,000 次、不同 2,000,没有重复,但抢占失败(白做的 find + update)6,223 次,耗时 2.27 s——比原子领取慢约 8 倍。", t=tl(S(3)), mark=lidx(S(3), '抢占失败'), done=lidx(S(3), '没有重复'), kv=KV([['带条件的 update', '没有重复,但争抢多'], ['失败次数', '6,223 次'], ['耗时', '2.27 s,慢约 8 倍']], ['带条件的 update'])),
    step("按优先级领取:sort 指定 prio 降序,单个 worker 领 300 个任务,prio 序列单调不增(True);前 10 个都是 4,第 100 个是 3,第 200 个是 1,第 300 个是 0。", t=tl(S(4)), mark=lidx(S(4), '单调不增'), done=lidx(S(4), '前 10 个 prio'), kv=KV([['sort {prio: -1, _id: 1}', '高优先级先领'], ['同优先级', '按 _id 先后']], ['sort {prio: -1, _id: 1}'])),
    step("队列索引:pending 任务 5 万个,每次 findOneAndUpdate 取最高优先级的一个:有 (status, prio, _id) 索引 0.1 ms,没有索引 17 ms——没有索引每次领取都要扫描并排序。", t=tl(S(5)), mark=lidx(S(5), '无索引'), done=lidx(S(5), '有索引'), b=bars([['有索引', 0.1, '0.1 ms'], ['无索引', 17, '17 ms']], 17, mark=[1], done=[0]), kv=KV([['有索引', '0.1 ms'], ['无索引', '17 ms,队列越大越慢']], ['有索引'])),
    step("worker 领到任务后崩溃,任务会永远停在 running。给任务加租约 lease(1 秒),4 个任务被领走(running 4、pending 6)后 worker 崩溃;1.2 秒后清扫 update_many({status: running, lease: {$lt: now}}) 把 4 个过期任务放回 pending,pending 回到 10 个;这 4 个任务的 tries 是 1(领取过 1 次)。", t=tl(S(6)), mark=lidx(S(6), '清扫', '放回 pending'), done=lidx(S(6), '4 个任务被领走'), kv=KV([['租约 lease', '领取时写入过期时间'], ['清扫', 'running 且过期的放回 pending'], ['tries', '记录领取次数,便于限制重试']], ['租约 lease'])),
]
A = mkartm('m44', 44, 'MongoDB,findAndModify,任务队列,原子领取,租约,真实验证,动画演示',
    '实测用 findOneAndUpdate 做任务队列:8 个 worker 原子领取 2,000 个任务零重复(7,462 个/秒);先 find 再 update 的做法有 6,377 个任务被重复领取;带条件 update 没有重复但失败 6,223 次、慢 8 倍;按优先级领取、队列索引(0.1 对 17 ms)、租约清扫崩溃的 worker。',
    '想用 MongoDB 做一个任务队列,怎么保证每个任务只被一个 worker 领走?这篇对比原子领取、两步领取、带条件更新三种写法,再验证优先级、索引和租约。',
    [('0 对 6,377', '原子领取与先 find 再 update 两步领取下被重复领取的任务数'), ('7,462 个/秒', '8 个 worker 原子领取的吞吐'), ('0.1 对 17 ms', '队列有 (status, prio, _id) 索引与没有索引时,5 万个 pending 里领一个的耗时')],
    [('原子领取', '<p><code>findOneAndUpdate</code> 把“找一个 pending 的”和“改成 running”合成一个原子操作,2,000 个任务 8 个 worker 零重复。</p>'),
     ('两步做法', '<p>先 find 再 update 中间没有保护,多个 worker 找到同一个任务:8,377 次领取对应只有 2,000 个不同任务,6,377 个任务被重复处理。</p>'),
     ('带条件 update', '<p>update 加上 <code>status: "pending"</code> 条件并检查 <code>modified_count</code> 可以避免重复,但抢占失败 6,223 次,白做了很多工作,慢约 8 倍。</p>'),
     ('优先级', '<p>用 <code>sort</code> 指定 <code>{prio: -1, _id: 1}</code> 领取,验证了领取顺序是 prio 从高到低。</p>'),
     ('索引', '<p>队列必须有 <code>(status, prio, _id)</code> 索引,否则每次领取要扫描(17 ms 对 0.1 ms)。</p>'),
     ('崩溃的 worker', '<p>领取时写入租约时间,清扫线程把过期的 running 放回 pending,配合 <code>tries</code> 限制重试次数。</p>')],
    steps,
    [ENV_M + '。8 个 worker 是 8 个线程,每个线程自己的连接;吞吐与失败次数每次运行都不同',
     '没有验证:副本集上带 w:majority 的领取延迟;worker 在处理完成时没有及时确认导致的重复处理(至少一次语义);任务极多(百万级)时的队列分片;change stream 驱动的推送式消费;死信队列'],
    '用 findAndModify 做任务队列')
