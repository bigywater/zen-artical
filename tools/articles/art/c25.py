from lib import *
S = SS('c25')
steps = [
    step("拷目录时源路径的写法决定结果:docker cp src 容器:/d1(/d1 已存在)→ /d1/src/a.txt、/d1/src/sub/b.txt,目录本身被放进去;docker cp src/. 容器:/d2(/d2 已存在)→ /d2/a.txt、/d2/sub/b.txt,只拷内容。目标 /d3/newname 的上级 /d3 不存在 → 退出码 1,Could not find the file /d3 in container;目标 /newname 不存在但上级 / 存在 → 目录被改名为 newname,里面是 a.txt 和 sub/b.txt。", t=tl(S(1)), done=lidx(S(1), 'src/. {容器}', 'src {容器}:/newname'), mark=lidx(S(1), '/d3/newname', 'src {容器}:/d1'), kv=KV([['src → /d1(已存在)', '/d1/src/…(目录被放进去)'], ['src/. → /d2(已存在)', '/d2/a.txt…(只拷内容)'], ['目标上级不存在', '退出码 1'], ['目标不存在、上级存在', '目录改名为目标']], ['src/. → /d2(已存在)'])),
    step("拷进去的文件属主:宿主机文件 uid=501,拷进容器后不带 -a 和带 -a 都是 501:20(宿主机的 uid:gid,不是 root)。反过来,容器里属主 1234:5678 的文件拷出来,不带 -a 在宿主机上是 uid=501,带 -a 也是 501(退出码 0,没有报错)——这个宿主机用户没有权限 chown 成别人,结果仍是自己。", t=tl(S(2)), done=lidx(S(2), '宿主机文件属主'), mark=lidx(S(2), '容器里属主 1234:5678'), kv=KV([['拷进容器', '501:20(宿主机 uid:gid)'], ['拷出,带不带 -a', '都是 501,不报错']], ['拷进容器'])),
    step("拷到挂载的位置:命名卷 /vol、bind mount /bnd、普通可写层 /plain 都成功,容器里读到 one,bind mount 的宿主机目录里也有 x.txt;拷到 tmpfs /tmp1,docker cp 退出码是 0,但容器里 cat 报 No such file,tmpfs 目录里是空的——文件悄悄丢了,没有报错。容器已停止时,docker cp 进去、再拷出来也都退出码 0,内容 one。", t=tl(S(3)), done=lidx(S(3), '命名卷', 'bind mount /bnd', '容器已停止'), mark=lidx(S(3), 'tmpfs /tmp1', 'tmpfs 目录里实际有什么'), kv=KV([['命名卷 / bind mount / 可写层', '拷进去能读到'], ['tmpfs', '退出码 0 但文件不见了'], ['已停止的容器', '可以拷进拷出']], ['tmpfs'])),
    step("符号链接和 Docker 管理的文件:拷出容器里的符号链接 /lnk,不带 -L 得到符号链接(指向 /etc/os-release),带 -L 得到普通文件(189 字节)。拷出 /etc/hostname(Docker 为容器生成的文件),退出码 0,内容 3650c7c6d258,正是容器 ID 的前 12 位。", t=tl(S(4)), done=lidx(S(4), '拷出容器里的符号链接', '拷出 /etc/hostname'), kv=KV([['不带 -L', '拷出符号链接本身'], ['带 -L', '拷出链接指向的内容'], ['/etc/hostname', '能拷,内容 = 容器 ID 前 12 位']], ['带 -L'])),
    step("拷 64 MiB 的随机文件:拷进容器 3 次 669 / 1159 / 799 ms(中位数 799),拷出 3 次 612 / 513 / 438 ms(中位数 513);拷回来的文件与原文件逐字节一致。", t=tl(S(5)), done=lidx(S(5), '一致吗'), b=bars([['拷进容器 64 MiB (ms)', 799, '799'], ['拷出容器 64 MiB (ms)', 513, '513']], 799, done=[1], mark=[0]), kv=KV([['拷进', '中位数 799 ms'], ['拷出', '中位数 513 ms'], ['内容', '逐字节一致']], ['内容'])),
]
A = mkartc('c25', 25, 'Docker,docker cp,容器文件拷贝,tmpfs,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测 docker cp:src 与 src/. 的区别、目标目录不存在的几种结果、属主(macOS 上拷进去仍是 501:20)、拷到 tmpfs 时退出码 0 但文件丢失、-L 对符号链接的影响,以及 64 MiB 文件拷进 799 ms、拷出 513 ms(中位数,3 次的波动不小)。',
    '不进入容器怎么读写文件?docker cp 看起来简单,但源路径末尾的 /.、目标路径存不存在、拷到挂载目录里,结果各不相同。这篇逐一实测,包括一个会悄悄丢文件的情形。',
    [('src/.', '加上 /. 只拷目录的内容,不带则目录本身也放进目标'), ('退出码 0 却没文件', 'docker cp 到容器的 tmpfs 挂载点时的结果'), ('799 vs 513 ms', '64 MiB 文件拷进与拷出容器的中位数')],
    [('目录的写法', '<p><code>docker cp src 容器:/d1</code> 在 /d1 已存在时会得到 <code>/d1/src/…</code>;<code>docker cp src/. 容器:/d2</code> 只拷内容。目标不存在但上级存在时,源目录被改名成目标名;上级也不存在则报错退出码 1。</p>'),
     ('属主', '<p>在 macOS 的 Docker Desktop 上,拷进容器的文件属主是宿主机的 uid:gid(501:20),带不带 <code>-a</code> 一样;拷出时属主也是当前用户。这是这台机器上的观察,Linux 宿主机上默认的属主处理我没有测。</p>'),
     ('挂载点', '<p>拷到命名卷、bind mount 都成功;拷到 tmpfs 挂载点,命令退出码为 0 但文件不在。要往 tmpfs 里放文件,只能用 <code>docker exec</code> 之类的方式(本文没有逐一试)。</p>'),
     ('符号链接和 hostname', '<p>默认拷出符号链接本身,<code>-L</code> 才拷内容。Docker 为容器生成的 <code>/etc/hostname</code> 也能拷出来,内容是容器 ID 的前 12 位。</p>'),
     ('速度', '<p>64 MiB 拷进容器 0.7~1.2 秒,拷出 0.4~0.6 秒(3 次);内容一致。docker cp 是把文件打成 tar 流经 API 传输的,大量小文件的开销我没有测。</p>')],
    steps,
    [ENV_C + '。宿主机侧的文件在本项目临时目录下;大文件用 os.urandom 生成,每个方向测 3 次并列出全部;其余场景各运行一次;实验后已删除容器、卷和临时文件',
     '没有验证:Linux 宿主机的属主规则、很多小文件的拷贝开销、docker cp - 与 tar 流的用法、拷贝时容器正在写同一个文件、--follow-link 之外的符号链接边界情况、rootless Docker'],
    'docker cp')
