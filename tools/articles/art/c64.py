from lib import *
S = SS('c64')
steps = [
    step("compose.yaml 里 develop.watch 配了三条规则:./app 同步到 /app(sync)、./conf.txt 同步到 /conf.txt 并重启(sync+restart)、./deps.txt 变化就重建(rebuild)。docker compose up -d --build 用了 0.8 秒,容器 aa2394783760;然后在后台启动 docker compose watch --no-up,进程一直在运行。", t=tl(S(1)), done=lidx(S(1), 'docker compose up -d --build', 'docker compose watch --no-up'), kv=KV([['sync', './app → /app'], ['sync+restart', './conf.txt → /conf.txt 并重启'], ['rebuild', './deps.txt 变化则重建镜像']], ['sync'])),
    step("sync:改 ./app/message.txt 三次,从写入到容器里读到新内容的时间是 630、664、657 ms(含每次 docker exec 轮询的开销),容器还是原来的,StartedAt 没变。新增 app/new.txt,容器里出现了(new file);删除 app/new.txt 后容器里的 /app 只剩 message.txt——同步包括新增和删除。", t=tl(S(2)), done=lidx(S(2), '写入后到容器里读到新内容', '新增 app/new.txt'), mark=lidx(S(2), '删除 app/new.txt'), b=bars([['第 1 次 (ms)', 630, '630'], ['第 2 次 (ms)', 664, '664'], ['第 3 次 (ms)', 657, '657']], 664, done=[0, 1, 2]), kv=KV([['改文件', '约 0.6 秒后容器里生效'], ['容器', '没有重启'], ['新增 / 删除', '都会同步']], ['改文件'])),
    step("sync+restart:改 ./conf.txt 后约 662 ms,容器里读到 c2,随后约 3.8 秒后看到容器重启(StartedAt 变了,容器还是原来那个);docker events(去掉 exec_*)的序列是 extract-to-dir → kill → kill → stop → die → start → restart。先把文件复制进去,再重启容器。3.8 秒里大部分是在等 sh 当 PID 1 不处理 SIGTERM(这个 Docker 的默认宽限期是 3 秒,见 c30)——这是我的推断,没有单独验证。", t=tl(S(3)), done=lidx(S(3), '容器里 /conf.txt = c2'), mark=lidx(S(3), '这段时间容器的事件'), kv=KV([['/conf.txt', '先同步(约 0.66 秒)'], ['容器', '同一个,但重启了(约 3.8 秒)'], ['事件', 'extract-to-dir → kill → kill → stop → die → start → restart']], ['容器'])),
    step("rebuild:改 ./deps.txt 后,watch 输出 Rebuilding service(s) [\"web\"] after changes were detected…,重新构建镜像,约 6.2 秒后容器被重新创建(容器 ID 变了);新容器里 /deps.txt = d2,/app/message.txt = v4(重建时把当前文件一起打进了镜像)。", t=tl(S(4)), done=lidx(S(4), '容器被重新创建了吗'), mark=lidx(S(4), 'watch 进程输出里的不同行'), kv=KV([['rebuild', '重新构建镜像并重建容器,约 6.2 秒'], ['新容器内容', '包含此前 sync 过来的最新文件']], ['rebuild'])),
]
A = mkartc('c64', 64, 'Docker,Docker Compose,watch,develop.watch,热更新,真实验证,动画演示',
    '在 Docker Compose v5.5.1 里实测 docker compose watch:sync 改文件约 0.6 秒后容器里生效且容器不重启,新增和删除也同步;sync+restart 先同步再重启同一个容器(约 3.8 秒);rebuild 重新构建镜像并重建容器(约 6.2 秒),新容器里是最新文件。',
    '想在容器里开发却不想反复 build?docker compose watch 可以把本地文件变化同步进容器、重启或重建。这篇用三条规则分别实测延迟和容器的变化。',
    [('约 0.6 秒', 'sync 规则下,本地改文件到容器里读到新内容的时间'), ('同一个容器、重启', 'sync+restart:StartedAt 变了而容器 ID 不变'), ('约 6.2 秒', 'rebuild 规则下,改文件到新容器可用的时间')],
    [('三种动作', '<p><code>sync</code> 只拷文件;<code>sync+restart</code> 拷完重启容器;<code>rebuild</code> 重新构建镜像并重建容器。路径用 <code>develop.watch</code> 配置。</p>'),
     ('sync 的延迟', '<p>改一次文件,约 0.6 秒后容器里就是新内容(这个数字包含我 <code>docker exec</code> 轮询的开销,实际同步更快)。删除文件也会同步到容器里。</p>'),
     ('sync+restart', '<p>容器 ID 不变,但 StartedAt 变了:先 kill、stop、die,再 start。耗时里的大头是等 sh 作为 PID 1 退出(见 c30 的默认宽限期),如果你的程序能处理 SIGTERM,重启会快很多(没有测)。</p>'),
     ('rebuild', '<p>重新构建会触发整个构建流程(这个镜像很小,所以只要几秒)。新容器是用最新的整个目录构建出来的,所以前面 sync 过来的改动也在里面。</p>')],
    steps,
    [ENV_C + '。Docker Compose v5.5.1;镜像是 alpine:3.20 加几个 COPY(构建不需要联网);用 docker compose watch --no-up 在后台运行,从 Python 里写文件并轮询 docker exec cat 计时;容器事件取自 docker events;实验后已停止 watch 并 down -v',
     '没有验证:ignore 规则、initial_sync、大目录的监视开销、Linux 上的文件监视行为、真实框架(如 Node、Flask)的热重载、sync 的权限与属主、docker compose up --watch'],
    'compose watch')
