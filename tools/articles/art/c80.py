from lib import *
S = SS('c80')
steps = [
    step("Dockerfile:RUN 盐 → COPY app.txt → RUN sleep 2(A)→ COPY dep.txt → RUN sleep 2(B)。第 1 次冷构建 5.8 秒,全部执行;第 2 次什么都没改 0.2 秒,全部 CACHED;第 3 次只改 app.txt 的修改时间(touch)0.2 秒,仍然全部 CACHED——缓存看的是内容,不是 mtime;第 4 次改 app.txt 的内容 4.7 秒,从 COPY app.txt 开始后面全部重新执行(最前面的盐 RUN 仍 CACHED);第 5 次只改 dep.txt 的内容 2.5 秒,只有 COPY dep.txt 和后面的 RUN B 重新执行;第 6 次把 app.txt 写回 v2(与第 4 次的内容相同)0.4 秒,全部命中缓存。", t=tl(S(1)), done=lidx(S(1), '第 2 次', '第 3 次', '第 6 次'), mark=lidx(S(1), '第 4 次', '第 5 次'), b=bars([['冷构建 (秒)', 5.8, '5.8'], ['什么都没改 (秒)', 0.2, '0.2'], ['改 app.txt 内容 (秒)', 4.7, '4.7'], ['只改 dep.txt 内容 (秒)', 2.5, '2.5']], 5.8, done=[1], mark=[0, 2, 3]), kv=KV([['mtime 变化', '不影响缓存'], ['内容变化', '从该 COPY 起后面的指令全部失效'], ['写回相同内容', '重新命中缓存']], ['内容变化'])),
    step("指令顺序决定缓存利用率:先 COPY . 再 RUN 安装依赖(sleep 3),改了源码 main.py 后,COPY . 失效,后面的 RUN 也要重新执行,用时 3.4 秒;先只 COPY deps.txt、RUN 安装依赖、再 COPY . 源码,同样改了 main.py,前面的 COPY deps.txt 和 RUN 都是 CACHED,只有最后的 COPY . 重新执行,用时 0.3 秒。", t=tl(S(2)), done=lidx(S(2), '先 COPY 依赖清单'), mark=lidx(S(2), '先 COPY . 再装依赖'), b=bars([['先 COPY . 后 RUN:改源码 (秒)', 3.4, '3.4'], ['先依赖后源码:改源码 (秒)', 0.3, '0.3']], 3.4, done=[1], mark=[0]), kv=KV([['COPY . 在前', '改任何文件都让后面的 RUN 重跑 (3.4 秒)'], ['依赖清单在前', '只重跑最后的 COPY (0.3 秒)']], ['依赖清单在前'])),
    step("什么样的 Dockerfile 修改会让缓存失效:加一行注释 → 仍然全部 CACHED(0.3 秒);RUN 命令末尾多一个空格 → 也 CACHED(0.2 秒);RUN 命令里把 echo X 改成 echo Y → 这一步重新执行(2.4 秒);在前面插入一条 ENV FOO=1 → 后面的 RUN 重新执行(2.4 秒)。", t=tl(S(3)), done=lidx(S(3), '加了一行注释', 'RUN 命令末尾多一个空格'), mark=lidx(S(3), '改了一个字符', '加一个 ENV'), kv=KV([['注释、行尾空格', '不影响缓存'], ['改命令里的字符', '该步失效'], ['前面插入 ENV', '后面的步骤失效']], ['改命令里的字符'])),
    step("--no-cache 与 --no-cache-filter:两个阶段 one、two 各 sleep 2 秒,不加参数 0.2 秒全部 CACHED;--no-cache-filter one 2.4 秒,只有 one 阶段的 RUN 重新执行,two 阶段仍 CACHED;--no-cache 2.6 秒,全部步骤(包括 COPY --from)重新执行。", t=tl(S(4)), done=lidx(S(4), '不加参数'), mark=lidx(S(4), '--no-cache-filter one', '--no-cache(全部'), kv=KV([['不加参数', '全部 CACHED,0.2 秒'], ['--no-cache-filter one', '只重跑 one 阶段 (2.4 秒)'], ['--no-cache', '全部重跑 (2.6 秒)']], ['--no-cache-filter one'])),
]
A = mkartc('c80', 80, 'Docker,构建缓存,缓存失效,Dockerfile指令顺序,no-cache-filter,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测构建缓存何时失效:只改文件修改时间不会失效,改内容才会,而且从那条 COPY 起后面全部重新执行;先 COPY 依赖清单再 COPY 源码,改源码的构建从 3.4 秒降到 0.3 秒;加注释和行尾空格不失效,改命令字符或前面插入 ENV 才失效;--no-cache-filter 只让指定阶段重跑。',
    '为什么改了一行代码,依赖又重新装了一遍?构建缓存到底看什么?这篇用 sleep 做可控的耗时,逐项量出:改 mtime、改内容、调换顺序、加注释、改命令各自让缓存怎样。',
    [('3.4 秒 对 0.3 秒', '改一个源码文件后重建:先 COPY . 后安装依赖,与先依赖后源码的用时'), ('touch 不失效', '只改文件修改时间,构建 0.2 秒全部命中缓存'), ('注释不失效', '在 Dockerfile 里加一行注释,仍然全部 CACHED')],
    [('缓存键', '<p>COPY 指令的缓存键是所拷文件的内容(不是 mtime),RUN 指令的缓存键是命令字符串加上前面所有步骤的结果。一步失效,后面的步骤全部失效。内容改了再改回去,又会命中之前的缓存(第 6 次构建)。</p>'),
     ('顺序', '<p>把变化少的放前面:先只拷依赖清单、安装依赖,再拷源码。这样改源码只会让最后的 COPY 重新执行。</p>'),
     ('Dockerfile 本身的修改', '<p>注释和 RUN 命令末尾的空格没有让缓存失效;改命令里的字符、在前面加 ENV 则会。这里只试了这四种改法,其它改法(如换行、续行符)我没有测。</p>'),
     ('强制重跑', '<p><code>--no-cache</code> 全部重跑;<code>--no-cache-filter 阶段名</code> 只重跑一个阶段,多阶段构建里很有用。</p>')],
    steps,
    [ENV_C + '。每个 RUN 里都有 sleep 2 或 3 秒用来让「执行」和「命中缓存」在耗时上一目了然,开头的 RUN echo 盐用来避开之前构建留下的缓存;是否 CACHED 取自 --progress=plain 的输出;每个场景之间 Dockerfile 与文件的变化见正文;实验后已删除镜像',
     '没有验证:RUN --mount=type=cache(见 c9)、外部缓存导入导出 --cache-from / --cache-to、ADD 远程 URL 的缓存键、ARG 对缓存的影响(见 c7)、.dockerignore 对缓存的影响(见 c2)、多平台构建的缓存'],
    '构建缓存失效')
