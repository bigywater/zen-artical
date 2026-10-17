from lib import *
S = SS('c29')
steps = [
    step("4 种重启策略 × 命令 exit 0 / exit 1,各起一个容器,等 5 秒:no 不重启(exited,RestartCount=0);on-failure:2 在 exit 0 时不重启(RestartCount=0),exit 1 时重启了 2 次后停止(exited,RestartCount=2);always 和 unless-stopped 不管 exit 0 还是 exit 1,都在不停重启(Status=restarting,RestartCount=6)。", t=tl(S(1)), done=lidx(S(1), '--restart no ', '--restart on-failure:2    命令 exit 0'), mark=lidx(S(1), '--restart always', '--restart unless-stopped', 'on-failure:2    命令 exit 1'), b=bars([['no', 0, '0'], ['on-failure:2 exit 0', 0, '0'], ['on-failure:2 exit 1', 2, '2'], ['always(5 秒内)', 6, '6'], ['unless-stopped(5 秒内)', 6, '6']], 6, done=[0, 1], mark=[3, 4]), kv=KV([['no', '不重启'], ['on-failure:2', '只在失败时重启,最多 2 次'], ['always / unless-stopped', '成功退出也重启']], ['always / unless-stopped'])),
    step("退避时间:always 加总是失败的命令,14 秒内启动了 8 次(RestartCount=8)。相邻两次 start 事件的间隔是 175、276、467、886、1679、3310、6537 ms,后面每次大约是前一次的 2 倍(比值 1.58、1.69、1.9、1.9、1.97、1.97)——指数退避,重启越来越慢。", t=tl(S(2)), done=lidx(S(2), '相邻两次 start'), mark=lidx(S(2), '每个间隔与前一个的比值'), b=bars([['间隔 1 (ms)', 175, '175'], ['间隔 3 (ms)', 467, '467'], ['间隔 5 (ms)', 1679, '1679'], ['间隔 7 (ms)', 6537, '6537']], 6537, done=[0], mark=[3]), kv=KV([['14 秒内启动', '8 次'], ['间隔', '175 → 276 → 467 → 886 → 1679 → 3310 → 6537 ms'], ['趋势', '每次约翻倍']], ['趋势'])),
    step("手动停止的容器不会被重启策略拉起:always 的容器 docker stop 3 秒后还是 exited;docker start 后 running;docker kill 之后 3 秒 Status=exited、RestartCount=0,也没有被重新拉起。", t=tl(S(3)), done=lidx(S(3), 'docker stop 3 秒后', 'docker kill 之后'), mark=lidx(S(3), 'docker start 之后'), kv=KV([['docker stop', '不会被拉起'], ['docker kill', '这里也没有被拉起'], ['docker start', '手动启动,running']], ['docker stop'])),
    step("on-failure:3 加总是失败的命令:最终 exited、RestartCount=3,即 1 次原始启动加 3 次重启共执行 4 次。--rm 和 --restart always 一起用,docker run 退出码 125,报 conflicting options: cannot specify both --restart and --rm。", t=tl(S(4)), done=lidx(S(4), 'on-failure:3'), mark=lidx(S(4), '--rm 与 --restart'), kv=KV([['on-failure:3', '最多重启 3 次,共执行 4 次'], ['--rm + --restart', '冲突,退出码 125']], ['--rm + --restart'])),
]
A = mkartc('c29', 29, 'Docker,重启策略,restart,always,on-failure,指数退避,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测重启策略:no 不重启、on-failure:2 只在失败时重启 2 次、always 和 unless-stopped 连成功退出也重启;失败容器的重启间隔 175、276、467、886、1679、3310、6537 ms,每次约翻倍;docker stop 和 docker kill 之后不会被拉起;--rm 与 --restart 冲突。',
    '容器崩了会自动重启吗?always、on-failure、unless-stopped 的区别是什么,重启得多快,什么情况下不会重启?这篇逐项实测,包括容器不停崩溃时间隔如何变长。',
    [('6537 ms', '总是失败的 always 容器,第 7 个重启间隔(前一个 3310 ms,约 2 倍)'), ('RestartCount=3', 'on-failure:3 加总是失败的命令:重启 3 次后停止,共执行 4 次'), ('exit 0 也重启', 'always 和 unless-stopped 对成功退出的容器同样不停重启')],
    [('四种策略', '<p>no 不重启;on-failure 只在退出码非 0 时重启,可以限制次数(:2 重启 2 次后停止),exit 0 不重启;always 和 unless-stopped 对退出码不挑,连成功退出也重启。后两者的区别(daemon 重启后 unless-stopped 不会拉起手动停止过的容器)需要重启 Docker 守护进程来验证,我没有做。</p>'),
     ('指数退避', '<p>重启间隔 175、276、467、886、1679、3310、6537 ms,稳定后每次约为前一次的 2 倍。第一个间隔含容器启动和退出本身的耗时,所以不是整整的 100 ms。我只测了 14 秒,没有看到上限(以及容器稳定运行多久会重置退避),没有验证。</p>'),
     ('手动停止', '<p>docker stop 之后容器保持 exited。docker kill 之后在这个版本里也没有被重新拉起(RestartCount=0)。</p>'),
     ('次数与 --rm', '<p>on-failure:3 总共执行 4 次(1 次原始启动加 3 次重启)。--rm 和 --restart 不能同时使用,docker run 直接以 125 报错。</p>')],
    steps,
    [ENV_C + '。策略对比的每种组合起一个容器,等 5 秒取状态;退避间隔取自 docker events 的 start 事件时间戳(TimeNano);其余场景各运行一次;实验后已删除容器',
     '没有验证:Docker 守护进程重启后 always 与 unless-stopped 的差别、退避的上限和重置条件、--restart 与 Swarm / Compose 的 restart、健康检查失败是否触发重启'],
    '重启策略')
