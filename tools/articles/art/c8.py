from lib import *
S = SS('c8')
steps = [
    step("三种把密钥交给构建的办法,密钥最后在不在镜像里。A:COPY secret.txt 进去、用完再 rm:在镜像的层内文件 tmp/secret.txt 里找到了密钥;B:--build-arg:在镜像配置 blob 里找到,docker history 有 2 行含密钥;C:RUN --mount=type=secret,id=tok:构建期读到了 18 字节,镜像里(所有层和配置)都找不到密钥,docker history 里 0 行,从镜像启动后 ls /run/secrets 得到 No such file or directory。", t=tl(S(1)), mark=lidx(S(1), '[A:COPY', '[B:--build-arg]'), done=lidx(S(1), '[C:RUN --mount', '没找到', '构建期读到了 18 字节', 'No such file'), b=bars([['A:COPY 再 rm:镜像里找到处数', 1, '1'], ['B:--build-arg', 1, '1'], ['C:secret mount', 0, '0']], 1, mark=[0, 1], done=[2]), kv=KV([['COPY 再 rm', '密钥留在较早的层里'], ['--build-arg', '密钥写进配置和历史'], ['--mount=type=secret', '镜像里找不到,运行时也没有 /run/secrets']], ['--mount=type=secret'])),
    step("把环境变量里的密钥交给构建:--secret id=tok,env=MYTOK,Dockerfile 里 RUN --mount=type=secret,id=tok,env=TOKVAR:构建期 TOKVAR 的长度是 17(等于环境变量值的长度),镜像里同样找不到密钥。", t=tl(S(2)), mark=lidx(S(2), 'TOKVAR 长度 17'), kv=KV([['env=', '把宿主机环境变量作为构建期环境变量'], ['结果', '镜像里没有密钥']], ['结果'])),
    step("密钥的内容不参与缓存键:同一个 Dockerfile 先用 10 字节的密钥构建,再换成 35 字节的完全不同的密钥构建,用到密钥的第 3 步仍然 CACHED(命中缓存)。", t=tl(S(3)), mark=lidx(S(3), 'CACHED'), kv=KV([['换了密钥', '这一步仍命中缓存'], ['含义', '要让密钥变化触发重建,需要自己加一个会变化的 ARG / 文件']], ['含义'])),
    step("Dockerfile 要求了密钥但构建时没给:RUN --mount=type=secret,id=nope,required=true:退出码 1,错误 secret nope: not found。不写 required(默认可选)时构建成功,容器里 /run/secrets/nope 不存在(ls 报 No such file or directory,命令退出码 1)。", t=tl(S(4)), mark=lidx(S(4), 'secret nope: not found'), done=lidx(S(4), '默认可选'), kv=KV([['required=true', '缺密钥时构建失败'], ['默认', '可选:没提供也能构建']], ['required=true'])),
    step("自己犯的错:RUN --mount=type=secret,id=tok cp /run/secrets/tok /app.conf:构建成功,但在镜像的层内文件 app.conf 里找到了密钥。mount 只保证挂载本身不进镜像,命令把内容写到别处就保不住了。", t=tl(S(5)), mark=lidx(S(5), '层内文件 app.conf'), kv=KV([['mount 的保证', '挂载点不留在镜像里'], ['不保证', '命令自己把内容复制出来']], ['不保证'])),
]
A = mkartc('c8', 8, 'Docker,构建密钥,BuildKit,secret mount,镜像泄漏,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测构建期密钥:COPY 再 rm 的密钥仍留在较早的层里,--build-arg 的密钥写进镜像配置和 docker history,而 RUN --mount=type=secret 在所有层和配置里都找不到密钥,运行时也没有 /run/secrets;支持 env= 传入;密钥内容不参与缓存键(换密钥仍 CACHED);required=true 缺密钥时构建失败;命令把密钥 cp 到别处仍会写进镜像。',
    '构建时要用私有仓库的凭据,怎么传才不会留在镜像里?这篇把三种做法(COPY 后删除、--build-arg、--mount=type=secret)的镜像都拆开,在配置、历史和每一层里搜索密钥字符串,并验证 secret mount 的缓存行为和失败方式。',
    [('0', 'RUN --mount=type=secret 构建的镜像里,在所有层和配置中找到密钥的处数'), ('仍 CACHED', '换成完全不同的密钥内容后,用到密钥的那一步仍命中缓存'), ('层内文件 app.conf', '命令把 /run/secrets/tok 复制到 /app.conf 后,密钥出现在镜像的层里')],
    [('三种办法的对比', '<p>COPY 进去再 <code>rm</code>,密钥留在较早的层里(层内文件 <code>tmp/secret.txt</code>,前面讲 whiteout 的那一篇说过,删除救不了);<code>--build-arg</code> 把值写进配置和 <code>docker history</code>;<code>--mount=type=secret</code> 只在构建的那一步里把密钥挂载成临时文件 <code>/run/secrets/tok</code>,镜像的所有层和配置里都搜不到它。</p>'),
     ('也可以用环境变量', '<p><code>--secret id=tok,env=MYTOK</code> 配 <code>RUN --mount=type=secret,id=tok,env=TOKVAR</code>,构建期的 <code>TOKVAR</code> 就是宿主机环境变量里的值(长度 17),同样不进镜像。</p>'),
     ('缓存', '<p>密钥内容不参与缓存键:换成完全不同的密钥,用到它的步骤仍然 CACHED。好处是密钥轮换不会让整条构建链重做;坏处是密钥变了你得自己想办法让它重建。</p>'),
     ('缺失与默认', '<p>默认挂载是可选的:没提供密钥,构建照样成功,只是文件不存在;写了 <code>required=true</code> 才会以 <code>secret nope: not found</code> 失败。命令依赖密钥时记得写 required。</p>'),
     ('mount 管不住你的命令', '<p><code>cp /run/secrets/tok /app.conf</code> 把内容写进了镜像的层里,密钥又泄漏了。secret mount 保证的是挂载本身不进镜像,不是命令的输出。</p>')],
    steps,
    [ENV_C + '。密钥是一个带时间戳的假字符串;在镜像里搜索的方法:docker save 导出 tar,在配置 JSON、每个 blob 以及解压后的每个层文件里查找该字符串;缓存判断来自构建输出里步骤的 CACHED(每次运行前加了带时间戳的 salt 层);每种情形一次;实验后已删除所有镜像',
     '没有验证:ssh 挂载(--mount=type=ssh)、docker compose 的 secrets、多阶段构建中 secret 是否进入中间阶段的缓存导出、--cache-to 导出缓存里是否含密钥、BuildKit 日志(--progress)是否可能打印密钥'],
    '构建期密钥')
