from lib import *
S = SS('c34')
steps = [
    step("Docker Desktop 虚拟机有 10 个 CPU。用 12 个满负荷进程跑 6 秒,从容器的 cgroup 里读 cpu.stat 算平均占用:不限制 → 9.72 个 CPU(cpu.max = max 100000);--cpus 0.5 → 0.50(cpu.max = 50000 100000);--cpus 1 → 1.00;--cpus 2 → 2.02;--cpu-quota 25000(周期默认 100000)→ 0.25。--cpus 就是 cpu.max 里的 配额/周期。", t=tl(S(1)), done=lidx(S(1), '--cpus 0.5', '--cpus 1:', '--cpus 2', '--cpu-quota 25000'), mark=lidx(S(1), '不限制'), b=bars([['不限制', 9.72, '9.72'], ['--cpus 2', 2.02, '2.02'], ['--cpus 1', 1.0, '1.00'], ['--cpus 0.5', 0.5, '0.50'], ['--cpu-quota 25000', 0.25, '0.25']], 9.72, done=[1, 2, 3, 4], mark=[0]), kv=KV([['--cpus N', 'cpu.max = N×100000 / 100000'], ['--cpu-quota 25000', '0.25 个 CPU'], ['不限制', 'cpu.max = max,用了 9.72 个']], ['--cpus N'])),
    step("--cpu-shares 只在争抢时起作用:只有一个容器、--cpu-shares 2(最低权重)、2 个满负荷进程,平均占用 2.00 个 CPU,一点没被限制。两个容器钉在同一个 CPU 上(--cpuset-cpus 0)同时满负荷:shares 1024 对 1024 → 0.50 对 0.51;1024 对 512 → 0.63 对 0.40(实际比例 1.57);1024 对 256 → 0.74 对 0.30(2.47);2048 对 256 → 0.83 对 0.26(3.19)。cgroup v2 里 shares 被换算成 cpu.weight:256 → 35,512 → 59,1024 → 100,2048 → 174,不是线性的;按 weight 算的比例 1.69、2.86、4.97,实际比例落在同一方向但偏小(原因我没有查)。", t=tl(S(2)), done=lidx(S(2), '只有这一个容器', 'shares 1024 对 1024'), mark=lidx(S(2), 'shares 1024 对 512', 'shares 1024 对 256', 'shares 2048 对 256', 'cpu.weight'), b=bars([['1024 对 1024 实际比例', 0.98, '0.98'], ['1024 对 512', 1.57, '1.57'], ['1024 对 256', 2.47, '2.47'], ['2048 对 256', 3.19, '3.19']], 3.19, done=[0], mark=[1, 2, 3]), kv=KV([['没有竞争', 'shares 2 也用满 2.00 个 CPU'], ['争抢同一个 CPU', '按权重分,1024:512 实际约 1.57:1'], ['换算', '--cpu-shares 1024 → cpu.weight 100']], ['没有竞争'])),
]
A = mkartc('c34', 34, 'Docker,cgroup,cpus,cpu-quota,cpu-shares,cpu.weight,真实验证,动画演示',
    '在 Docker Engine 29.8.2(cgroup v2)里实测 CPU 限制:--cpus 0.5/1/2 让满负荷的容器平均只占 0.50/1.00/2.02 个 CPU(cpu.max 的配额/周期),--cpu-quota 25000 是 0.25;--cpu-shares 没有竞争时不限制(shares 2 仍用满 2.00 个 CPU),同一 CPU 上争抢时按权重分,1024 对 512 约 1.57:1,shares 被换算成非线性的 cpu.weight(512 → 59、1024 → 100、2048 → 174)。',
    '--cpus 和 --cpu-shares 都是限制 CPU,有什么区别?一个是硬上限,另一个只在争抢时起作用。这篇用满负荷的 Python 进程,从 cgroup 的 cpu.stat 里读出实际占用的 CPU,逐项验证。',
    [('0.50 / 1.00 / 2.02', '--cpus 0.5、1、2 的容器满负荷时的平均 CPU 占用(不限制时 9.72)'), ('2.00', '--cpu-shares 2(最低权重)的容器在没有竞争时的 CPU 占用'), ('1.57', '同一 CPU 上 shares 1024 对 512 的容器,实际占用比例(按 shares 本应 2.00)')],
    [('硬上限:--cpus 和 --cpu-quota', '<p><code>--cpus 0.5</code> 在容器的 cgroup 里是 <code>cpu.max = 50000 100000</code>(每 100 ms 周期最多用 50 ms),满负荷的容器稳定在 0.50 个 CPU;<code>--cpu-quota 25000</code> 是 0.25。不限制时 12 个进程占用了 9.72 个 CPU(虚拟机共 10 个)。这是 CPU 时间的上限,容器可以在多个核上同时跑,只是总和不超过。</p>'),
     ('软权重:--cpu-shares', '<p>shares 只决定争抢时的比例。没有竞争时,shares 为 2 的容器也用满 2.00 个 CPU;把两个容器钉在同一个 CPU 上,1024 对 1024 各约一半,1024 对 512 是 0.63 对 0.40。cgroup v2 把 shares 换算成 <code>cpu.weight</code>(1024 → 100,512 → 59,256 → 35,2048 → 174),这个换算不是线性的。实际比例比 shares 的比例小,也比 weight 的比例小一些,我没有深究原因;每组只跑了一次 6 秒。</p>')],
    steps,
    [ENV_C + '。Docker Desktop 虚拟机 10 个 CPU;满负荷程序是 python 的多进程忙等循环,占用 = 容器 cgroup 的 cpu.stat usage_usec 增量 ÷ 实际耗时;竞争实验用 --cpuset-cpus 0 把两个容器钉在同一个 CPU;每组运行一次;实验后已删除容器和镜像',
     '没有验证:CPU 节流次数(见后面的 throttling 一篇)、cgroup v1 的行为、--cpuset-cpus 之外的 NUMA、不同内核调度器版本、超线程对占用的影响、docker update 动态调整'],
    'CPU 限制')
