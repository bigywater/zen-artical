from lib import *
S = SS('c81')
steps = [
    step("镜像 A:alpine 加 ENV、CMD,一个 RUN 生成 30 MB 随机文件,下一个 RUN 把它删掉。结果镜像 Size = 76.5 MB,RootFS 4 层;docker history 各层大小是 4.1kB、31.5MB、4.1kB、0B、0B——那 31.5MB 的层还在。容器里 /big.bin 确实不存在(ls 报 No such file),但文件的内容仍占着镜像的空间(c3 里的 whiteout)。", t=tl(S(1)), done=lidx(S(1), '镜像 Size=76.5 MB', '容器里 /big.bin'), mark=lidx(S(1), 'docker history'), b=bars([['空 alpine (MB)', 13.6, '13.6'], ['生成后删除 (MB)', 76.5, '76.5']], 76.5, done=[0], mark=[1]), kv=KV([['看不见的文件', '容器里不存在'], ['占的空间', '仍在镜像里(31.5MB 的层)']], ['占的空间'])),
    step("镜像 B:同一个 RUN 里生成再删除,Size = 13.6 MB、3 层——和空的 alpine 一样大。要避免产生被删除文件的层,删除要和生成放在同一条指令里。", t=tl(S(2)), done=lidx(S(2), '镜像 Size=13.6 MB'), b=bars([['A:两个 RUN (MB)', 76.5, '76.5'], ['B:同一个 RUN (MB)', 13.6, '13.6']], 76.5, done=[1], mark=[0]), kv=KV([['同一个 RUN 里创建并删除', '13.6 MB'], ['分两个 RUN', '76.5 MB']], ['同一个 RUN 里创建并删除'])),
    step("事后压平:FROM scratch + COPY --from=A / /,得到 Size = 13.6 MB、RootFS 1 层,运行 /bin/echo 输出 squashed-ok;但 Cmd = None、Env 里没有 DEMO——镜像的元数据(ENV、CMD)不会带过来;再补上 ENV DEMO=1 和 CMD [\"echo\",\"from-cmd\"],才恢复 Cmd 和 Env,仍是 1 层。", t=tl(S(3)), done=lidx(S(3), '运行它', '再补上 ENV 和 CMD'), mark=lidx(S(3), 'FROM scratch'), kv=KV([['COPY --from=A / /', '压成 1 层,13.6 MB'], ['元数据', 'ENV、CMD 丢失,要重新写']], ['元数据'])),
    step("docker export | docker import(c17)也能压平:Size = 13.6 MB、1 层,Cmd = None、Env 无 DEMO——元数据同样丢失。", t=tl(S(4)), done=lidx(S(4), '镜像 Size=13.6 MB'), kv=KV([['export | import', '1 层,13.6 MB,元数据丢失']], ['export | import'])),
    step("docker build --squash:退出码 0,但输出警告 WARNING: experimental flag squash is removed with BuildKit. You should squash inside build using a multi-stage Dockerfile for efficiency.;得到的镜像仍是 Size = 76.5 MB、4 层——--squash 在 BuildKit 下被忽略,没有压平。", t=tl(S(5)), done=lidx(S(5), '加了 --squash 之后的镜像'), mark=lidx(S(5), 'docker build --squash'), kv=KV([['--squash', '被忽略,只有一条警告'], ['结果', '仍是 76.5 MB、4 层']], ['--squash'])),
]
A = mkartc('c81', 81, 'Docker,镜像压平,squash,多阶段构建,镜像体积,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测镜像压平:一个 RUN 生成 30 MB 文件、下一个 RUN 删除,镜像仍是 76.5 MB(4 层);同一个 RUN 里生成并删除则是 13.6 MB;FROM scratch + COPY --from 把整个根文件系统压成 1 层(13.6 MB),但 ENV 和 CMD 要重新写;export | import 同样丢元数据;docker build --squash 在 BuildKit 下被忽略。',
    '被删除的文件还占着镜像空间,怎么把它们真正去掉?这篇对比分两层删除、同一层删除、多阶段压平、export | import 和已被移除的 --squash,量出大小和层数,并看压平会丢掉什么。',
    [('76.5 MB 对 13.6 MB', '分两个 RUN 生成再删除,与在同一个 RUN 里生成并删除的镜像体积'), ('ENV、CMD 丢失', '用 COPY --from / 或 export | import 压平后,镜像里的 ENV 和 CMD 不见了'), ('--squash 被忽略', 'BuildKit 下 docker build --squash 只给警告,镜像仍有 4 层')],
    [('为什么删了还占空间', '<p>后一层的删除只是在新层里标记文件被删,前一层里的内容原样保留(c3、c21)。所以镜像里装完东西再清理缓存,必须和安装放在同一条 RUN 里。</p>'),
     ('同一个 RUN', '<p>同一条 RUN 产生一个层,文件在这层里创建后又删除,最终层里没有它,体积和空 alpine 一样。</p>'),
     ('事后压平', '<p>多阶段构建 <code>FROM scratch</code> 再 <code>COPY --from=… / /</code> 得到单层镜像;ENV、CMD 这些元数据不会带过来(我测了这两项),要重新写。压成一层的代价是失去层复用(c18),我没有量化这一点。</p>'),
     ('export | import', '<p><code>docker export | docker import</code> 同样压成 1 层,同样丢掉 Cmd 和 Env。</p>'),
     ('--squash', '<p>在这个 Docker 的 BuildKit 构建器下,<code>--squash</code> 被忽略,只打一条警告;经典构建器下的行为我没有测。</p>')],
    steps,
    [ENV_C + '。随机文件用 /dev/urandom 生成(几乎不可压缩);镜像体积是 docker image inspect 的 Size(压缩内容加解包层,见 c18);层数取自 RootFS.Layers;每种方式构建一次;实验后已删除镜像和容器',
     '没有验证:经典构建器下 --squash、多阶段压平后推送拉取的传输体积、压平对后续构建缓存的影响、用 docker buildx build --output 直接导出平坦的 rootfs、overlay 层数上限(127 层)的实际表现'],
    '镜像压平')
