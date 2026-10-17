import re
from lib import *
R = J('z97'); T = R['stdout']
def S(k): return [x for x in out('z97').split('== ')[k].splitlines()[1:] if x.strip()]
rows1 = re.findall(r'^\s+(\S.*?)\s+→ (\w+),共 ([\d.]+) s', T.split('== 二')[0], re.M)
rows2 = re.findall(r'^\s+(\S.*?)\s+→ (\S+?),发起后 ([\d.]+) s', T.split('== 二')[1], re.M)
tot = {n: float(t) for n, r, t in rows1}
steps = [
    step("服务端不可用(端口上没有服务,连接超时 500 ms),getData() 在放弃前的耗时因策略而异:" + ';'.join(f'{n} {t} s' for n, r, t in rows1) + "。全部最终抛 ConnectionLossException。", t=tl(S(1)), b=bars([[n.split('(')[0] + '(' + n.split('(', 1)[1][:14], float(t), f'{t} s'] for n, r, t in rows1], 9, done=list(range(len(rows1)))), kv=KV([[n.split('(')[0], f'{t} s'] for n, r, t in rows1[:4]], [rows1[0][0].split('(')[0]])),
    step("我在每个策略外包了一层记录。同一个策略对象的 allowRetry 被两条线程各调用一遍 —— main(你的调用线程)和 Curator-Framework(框架后台线程),各自从第 0 次重试开始计数、各自以「放弃」结束。所以一次失败的调用实际花的时间,不只是策略里写的重试次数乘以间隔。指数退避的间隔带随机性:同一个 ExponentialBackoffRetry(100, 5) 的两条序列里,有 100、500、800、900 ms 等不同的睡眠。", t=tl(S(1)), mark=[2], kv=KV([['allowRetry 调用方', 'main + Curator-Framework 两条线程'], ['指数退避', '间隔有随机性']], ['allowRetry 调用方'])),
    step("服务端重启(停止约 1.5 s 后重新启动,实际不可用约 2.5–3 s)期间发起一次 setData:" + ';'.join(f'{n} → {r}({t} s)' for n, r, t in rows2) + "。重试次数太少(RetryNTimes(1, 100))撑不过一次重启;其余几种撑过了。重试策略要按「你愿意容忍多长的服务端不可用」来设。", t=tl(S(2)), mark=[0], kv=KV([[n, f'{r} {t}s'] for n, r, t in rows2], [rows2[0][0]])),
]
A = dict(
    n=97, series='zookeeper', tags='ZooKeeper,Curator,重试策略,真实验证,动画演示',
    desc='Curator 重试策略实测:服务端不可用时 6 种策略放弃前的耗时(2.3–7.9 s)、策略被 main 与 Curator-Framework 两条线程各调用一遍、指数退避的间隔带随机性;服务端重启约 3 s 期间 RetryNTimes(1,100) 失败,其余 3 种成功。',
    lead='Curator 的重试策略只有一行配置,但它决定了服务端抖一下时你的调用是失败还是成功。这篇用真实的不可用服务端和真实的重启,量 6 种策略放弃前花多久、策略对象在内部被怎么调用,以及哪种策略能撑过一次重启。',
    facts=[('2.3–7.9 s', '服务端不可用时 6 种策略放弃前的耗时范围'), ('2 条线程', '同一个策略对象被 main 与 Curator-Framework 两条线程各用一遍'), ('1 次不够', 'RetryNTimes(1, 100) 撑不过 3 秒左右的重启,其余 3 种撑过了')],
    body=[
        sec('不可用时的放弃时间', '', term('', blk('z97', 1)), '<p>连接超时设为 500 ms,所以每次尝试连接本身就要 0.5 s;总耗时是「重试间隔 + 每次尝试连接的等待」的和,不是只看重试间隔。</p>'),
        sec('策略被调用两遍', '', term('', blk('z97', 1)), '<p>我没有去读 Curator 源码查这两条线程具体对应什么;只确认了日志里这两条线程各自从第 0 次开始计数。所以不要只按「策略里写的次数 × 间隔」去估算一次失败调用的总耗时,要在自己的环境里测。</p>'),
        sec('能否撑过一次重启', '', term('', blk('z97', 2)), '<p>服务端重启期间的客户端行为,也可以对照<a href="zookeeper-python-kazoo-client.html">kazoo</a>的「调用一直等到恢复」。Curator 里则是由策略决定等多久。</p>'),
        sec('分步演示', '', demo('重试策略', [('t', 'term', '输出'), ('b', 'bars', '耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。Curator 5.7.1 + OpenJDK 17;连接超时 500 ms、会话超时 6 s;第二项的重启是 SIGTERM 停止后 1.5 s 再启动(含启动时间实际不可用约 2.5–3 s),每个策略只测了 1 次', '没有验证:同一策略重复多次的耗时方差(指数退避有随机性)、ConnectionStateErrorPolicy、两条线程各自对应的框架内部循环、RetryForever / SleepingRetry 的其它实现'],
)
