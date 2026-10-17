from lib import *
S = SS('c83')
steps = [
    step("Dockerfile:RUN 建组和用户 app(uid/gid 10001)→ COPY --chown=0:0 → USER app → WORKDIR /srv/work → COPY …。镜像的 Config.User = app。默认运行:uid=10001(app) gid=10001(app),HOME=/home/app,whoami 是 app。CapEff 是 0000000000000000(没有任何有效 capability),CapBnd 仍是 00000000a80425fb(14 个的边界集合);写 /tmp/x 和 $HOME/x 成功,写 /x 和 /etc/x 失败(Permission denied)。", t=tl(S(1)), done=lidx(S(1), '默认 CMD 的输出', '写 /tmp'), mark=lidx(S(1), 'CapEff'), kv=KV([['uid / gid', '10001 / 10001(app)'], ['CapEff', '0:非 root 没有有效 capability'], ['能写的地方', '/tmp 和 $HOME;不能写 / 和 /etc']], ['CapEff'])),
    step("文件属主:/srv 是 0:0(root);USER 之前 COPY 进来的 /srv/root.txt 是 0:0;USER 之后不带 --chown 的 COPY /srv/plain.txt 也是 0:0(COPY 默认归 root,不管 USER);COPY --chown=app:app 的 /srv/owned.txt 是 10001:10001。USER app 之后创建的 WORKDIR /srv/work 属主是 10001:10001,app 能往里写;但 app 追加写 root 属主的 /srv/plain.txt → Permission denied,写 owned.txt 可以。", t=tl(S(2)), done=lidx(S(2), 'WORKDIR /srv/work', '以 app 身份往'), mark=lidx(S(2), '以 app 身份修改 COPY'), kv=KV([['COPY(无 --chown)', '属主 root,即使前面有 USER'], ['COPY --chown=app:app', '属主 10001:10001'], ['WORKDIR', 'USER 之后创建的目录属于 USER']], ['COPY(无 --chown)'])),
    step("运行时覆盖:--user root → uid=0,groups 里有一串系统组;--user 12345(passwd 里没有这个 uid)→ uid=12345 gid=0(root) groups=0(root),HOME=/,whoami 报 unknown uid 12345;--user 12345:0 的 id 也是 uid=12345 gid=0;--user app → id -u 是 10001,--user 10001 → id -un 是 app,名字和数字等价。", t=tl(S(3)), done=lidx(S(3), '--user root', '--user app'), mark=lidx(S(3), '--user 12345(passwd'), kv=KV([['--user root', '覆盖镜像里的 USER'], ['--user 12345', '没有名字:HOME=/,gid 默认 0'], ['--user app / 10001', '名字与数字等价']], ['--user 12345'])),
    step("USER 在构建中就生效:USER 10002 之后的 RUN 也以这个用户运行。RUN id -u > /who 报 can't create /who: Permission denied;RUN mkdir /out 报 mkdir: can't create directory '/out': Permission denied(用 || echo 吞掉了失败,构建退出码仍为 0);最终镜像里 /who 和 /out 都不存在。要在构建里装软件或建目录,得放在 USER 之前。", t=tl(S(4)), done=lidx(S(4), '这个镜像里 /who、/out'), mark=lidx(S(4), 'USER 10002 之后的 RUN', 'RUN 里的 id -u'), kv=KV([['USER 之后的 RUN', '以该用户运行,没权限写 /'], ['|| echo 吞掉失败', '构建仍然成功,但目录没建出来']], ['USER 之后的 RUN'])),
]
A = mkartc('c83', 83, 'Docker,非root用户,USER,COPY --chown,最小权限,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测非 root 运行:USER app(uid 10001)后进程 CapEff 为 0、只能写 /tmp 和 HOME;COPY 默认仍归 root(要加 --chown),USER 之后创建的 WORKDIR 属于该用户;--user 可以覆盖,passwd 里没有的 uid 没有名字、HOME 是 /;USER 在构建时就生效,之后的 RUN mkdir / 会失败。',
    '给镜像加一行 USER 就算「非 root」了吗?COPY 进来的文件归谁?uid 在 /etc/passwd 里没有会怎样?USER 之后的构建步骤会遇到什么?这篇逐项实测。',
    [('CapEff = 0', '非 root 用户的有效 capability 集合为空(c40 里 root 有 14 个)'), ('COPY 属主 root', 'USER app 之后不带 --chown 的 COPY,文件属主仍是 0:0'), ('unknown uid 12345', '--user 12345 在 passwd 里没有记录时 whoami 的报错')],
    [('运行时', '<p>USER app 后,进程的 uid/gid 是 10001,有效 capability 为空,只能写 /tmp 和 HOME 这类 app 自己的目录。边界集合 CapBnd 仍然是 14 个,但没有有效权限就用不上(c40)。</p>'),
     ('文件属主', '<p>COPY 默认把文件归 root,即使前面有 USER。要让应用能改自己的文件,要写 <code>COPY --chown=用户:组</code>;WORKDIR 在 USER 之后创建的目录则属于该用户。</p>'),
     ('--user', '<p><code>--user</code> 可以用名字或数字;uid 在 /etc/passwd 里没有时,id 仍然能用,但没有用户名、HOME 是 /,gid 默认 0(root 组)——这个组默认 0 值得注意。</p>'),
     ('构建中的 USER', '<p>USER 从它出现的那一行开始对后面的 RUN 生效。需要 root 的步骤(装包、建目录)要放在 USER 之前。</p>')],
    steps,
    [ENV_C + '。用户用 busybox 的 addgroup / adduser 建立(不需要联网);属主取自 ls -ldn 和 stat;capability 取自 /proc/self/status;构建期的 USER 效果通过让 RUN 失败来观察;实验后已删除镜像',
     '没有验证:Debian/Ubuntu 的 useradd 写法、gosu / su-exec 在入口脚本里降权、USER 与卷的权限(见 c23)、rootless 模式、Kubernetes 的 runAsNonRoot、HOME 目录是否存在时的行为差异'],
    '非 root 用户')
