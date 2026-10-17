from lib import *
S = SS('f178')
R = J('f178'); c0, c1 = R['ctx_no_ignore'][1], R['ctx_ignore'][1]; s0, s1 = R['img_size']; ca = R['cache']; ka = list(ca)
cmd = R['cmd']; kc = list(cmd)
PIP = R['pip']; kpp = list(PIP); BD = R['bind']; UB = R['unbuf']; ku = list(UB); PM = R['perm']; kpm = list(PM)
steps = [
    step(f"项目目录里放了 40 MB 的 venv、10 MB 的 .git 和 __pycache__,用 FROM scratch 加 COPY . /app 构建(只量构建本身,没有 Python 基础镜像)。没有 .dockerignore:发给 Docker 的构建上下文是 {c0},构建出的镜像 {s0 / 1e6:.1f} MB——venv 和 .git 被一起 COPY 进了镜像;写上 .dockerignore(venv、.git、__pycache__、*.pyc)之后上下文只有 {c1},镜像 {s1 / 1e6:.3f} MB。docker 默认把整个目录送给构建器,而 COPY . 会拷贝目录里的一切,所以这个文件既影响构建速度也影响镜像里有什么(包括不该带进去的 .env 之类文件)。", t=tl(S(1)), done=lidx(S(1), '有 .dockerignore'), mark=lidx(S(1), '没有 .dockerignore', '镜像大小'), b=bars([['没有 .dockerignore 的镜像', s0 / 1e6, f'{s0 / 1e6:.1f} MB'], ['有 .dockerignore 的镜像', max(s1 / 1e6, 0.4), f'{s1 / 1e6:.3f} MB']], 110, mark=[0], done=[1]), kv=KV([['上下文', f'{c0} → {c1}'], ['镜像', f'{s0 / 1e6:.1f} MB → {s1 / 1e6:.3f} MB']], ['上下文'])),
    step(f"层缓存的顺序:每次构建前先随机改 requirements.txt 的一行注释当起点(避免命中上次缓存),再只改 app.py 重新构建。写法 A(COPY . /app 再 COPY requirements.txt):两个 COPY 都重新执行({ca[ka[0]][0][1]}、{ca[ka[0]][1][1]});写法 B(先 COPY requirements.txt,再 COPY app.py):requirements 那一层 {ca[ka[1]][0][1]},只有 app.py 那一层重新执行。同样的规则放到真实的 Dockerfile 里:依赖安装(pip install)跟在 COPY requirements.txt 后面,源码在后面 COPY,改代码就不会重装依赖。注意这一节的构建里只有 COPY 步骤,pip install 步骤是否命中缓存是按这个规则推出来的;pip install 本身在第 5 节用本机的 Python 验证。", t=tl(S(2)), done=lidx(S(2), 'B:'), mark=lidx(S(2), 'A:'), kv=KV([['A', '先 COPY . → 全部重建'], ['B', 'requirements 层 CACHED'], ['结论', '依赖在前、源码在后']], ['B'])),
    step(f"CMD 的两种写法在镜像配置里是不同的:shell 形式 CMD gunicorn ... 存成 {cmd[kc[0]]}——进程树里 /bin/sh 是第一个进程,gunicorn 是它的子进程;exec 形式 CMD [\"gunicorn\", ...] 存成 {cmd[kc[1]]},gunicorn 自己就是第一个进程。容器停止时 docker 的信号发给第一个进程,所以 shell 形式下信号先到 sh(信号怎么传、谁收到,在第 189 篇用真实进程验证)。Dockerfile 里写 exec 形式,是为了让 gunicorn 直接收到 SIGTERM。", t=tl(S(3)), done=lidx(S(3), 'exec 形式'), mark=lidx(S(3), 'shell 形式'), kv=KV([['shell 形式', '/bin/sh -c 包一层'], ['exec 形式', '直接是 gunicorn']], ['exec 形式'])),
    step("docker build --check 可以在不真正构建的情况下检查 Dockerfile:对 CMD python app.py 报 JSONArgsRecommended(「建议用 JSON 数组形式,避免和系统信号有关的意外行为」),对 MAINTAINER 报 MaintainerDeprecated(改用 LABEL),这里的 Dockerfile 只用 FROM scratch,所以没有触发别的规则。退出码是 1(有警告)。把它放进 CI,可以在合并前就发现 shell 形式 CMD 之类的问题。", t=tl(S(4)), done=lidx(S(4), 'JSONArgs', 'Maintainer'), mark=lidx(S(4), '退出码'), kv=KV([['--check', '静态检查,不构建'], ['CMD python ...', 'JSONArgsRecommended']], ['--check'])),
    step(f"Dockerfile 里的安装步骤用本机的 Python 原样做一遍(新建 venv,再 pip install -r requirements.txt,requirements 里只固定 flask==3.1.3 和 gunicorn==26.2.0):退出码 {PIP[kpp[0]][0]},装了 {PIP[kpp[0]][2]} 个包(blinker、click、Flask、gunicorn、itsdangerous、Jinja2、MarkupSafe、Werkzeug),venv {PIP[kpp[1]][3]} MB。默认 pip 会留下 {PIP[kpp[0]][4]} MB 的缓存目录,加 --no-cache-dir 后是 {PIP[kpp[1]][4]} MB——这份缓存在镜像里没有用处,所以 Dockerfile 里写 --no-cache-dir。依赖不固定到具体版本时,同一个 Dockerfile 在不同日期构建会装到不同版本,所以 requirements 要写 ==。", t=tl(S(5)), done=lidx(S(5), '--no-cache-dir', '装好的包'), mark=lidx(S(5), '默认,有缓存'), kv=KV([['依赖', f"{PIP[kpp[1]][2]} 个包,venv {PIP[kpp[1]][3]} MB"], ['pip 缓存', f"{PIP[kpp[0]][4]} MB → {PIP[kpp[1]][4]} MB(--no-cache-dir)"]], ['pip 缓存'])),
    step(f"CMD [\"gunicorn\", \"-b\", ...] 里的绑定地址:-b 0.0.0.0:PORT → 经 127.0.0.1 访问 {BD['0.0.0.0'][0]},经本机局域网地址(en0)访问 {BD['0.0.0.0'][1]};-b 127.0.0.1:PORT → 经 127.0.0.1 访问 {BD['127.0.0.1'][0]},但经局域网地址访问 {BD['127.0.0.1'][1]}。容器里从外面(端口映射)进来的流量走的是容器自己的网卡地址,不是容器内部的 127.0.0.1,所以 gunicorn 只绑 127.0.0.1 时,容器里面看着正常、映射出来的端口却连不上。这里用本机的局域网地址验证了绑定行为,没有使用 Docker 的网络与端口映射。", t=tl(S(6)), done=lidx(S(6), '-b 0.0.0.0'), mark=lidx(S(6), '-b 127.0.0.1'), kv=KV([['0.0.0.0', '回环和外部地址都能访问'], ['127.0.0.1', '外部地址 ConnectionRefused']], ['127.0.0.1'])),
    step(f"Docker 的日志是接住进程 stdout 的管道。stdout 不是终端时 Python 默认块缓冲:视图里 print 一行之后 1.5 秒,日志文件里{'有' if UB[ku[0]][0] else '还没有'}这一行(进程被 SIGTERM 退出之后才出现:{UB[ku[0]][1]});设 PYTHONUNBUFFERED=1 后 1.5 秒内就能看到({UB[ku[1]][0]})。所以 Dockerfile 里常见 ENV PYTHONUNBUFFERED=1,否则 docker logs 里的 print 会延迟(进程被强杀时能不能丢,没有单独验证,只验证了延迟)。", t=tl(S(7)), done=lidx(S(7), 'PYTHONUNBUFFERED=1'), mark=lidx(S(7), '默认'), kv=KV([['默认', '管道里块缓冲,日志延迟'], ['PYTHONUNBUFFERED=1', '立即可见']], ['PYTHONUNBUFFERED=1'])),
    step(f"为什么要用非 root 用户运行,以及它的代价:用 chmod 把代码目录设成只读来模拟「文件属于 root、进程用普通用户运行」(不是真的换用户):目录可写时视图往应用目录写文件 → {PM[kpm[0]]};目录只读时 → {PM[kpm[1]]}。以非 root 运行后,应用要写的位置(上传、缓存、sqlite 文件、instance 目录)必须是该用户能写的目录或挂载卷;root 不受权限位限制,所以用 root 跑的容器里这个问题看不到,换成非 root 才会暴露。", t=tl(S(8)), done=lidx(S(8), '目录可写'), mark=lidx(S(8), '只读'), kv=KV([['目录可写', '200'], ['目录只读', 'PermissionError(500)']], ['目录只读'])),
]
DF = '''FROM python:3.14-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
RUN useradd --create-home app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
USER app
EXPOSE 8000
CMD ["gunicorn", "-b", "0.0.0.0:8000", "app:app"]'''
A = mkartf('f178', 178, 'Flask,Docker,Dockerfile,.dockerignore,层缓存,真实验证,动画演示',
    f'把 Flask 的 Dockerfile 拆成各个步骤逐项验证:真实的 Docker 构建验证 .dockerignore(上下文 {c0} → {c1}、镜像 {s0 / 1e6:.1f} MB → {s1 / 1e6:.3f} MB)、层缓存顺序、shell 与 exec 形式 CMD、docker build --check;用本机的 Python 与 Flask 验证 pip install --no-cache-dir、0.0.0.0 与 127.0.0.1 的绑定、PYTHONUNBUFFERED、只读目录下的 PermissionError。没有执行过 docker run。',
    '把 Flask 放进容器,Dockerfile 里有几处写法决定了镜像大小、构建速度、能不能被访问和日志什么时候出现。本机拉不到 python 基础镜像,所以这篇分两部分验证:与基础镜像无关的构建机制用 Docker Desktop 实际构建(FROM scratch);依赖安装、绑定地址、日志缓冲、权限这些则直接在本机用 Flask 和 gunicorn 做同样的事。需要说明:完整的镜像没有构建过,docker run 也没有执行过。',
    [(f'{c0} → {c1}', '.dockerignore 前后发给构建器的上下文大小'), (f'{PIP[kpp[0]][4]} → {PIP[kpp[1]][4]} MB', 'pip 缓存目录:默认 vs --no-cache-dir'), ('ConnectionRefused', 'gunicorn 只绑 127.0.0.1 时经外部地址访问的结果')],
    [('构建上下文与层缓存', '<p>上一篇:<a href="flask-media-production.html">媒体文件生产部署</a>;下一篇:<a href="flask-health-check.html">健康检查接口</a>。</p><p>前 4 节的构建以 <code>FROM scratch</code> 为基础,验证的是构建机制;后 4 节在本机直接用 Flask 与 gunicorn 验证。</p>'),
     ('.dockerignore 的作用', None),
     ('shell 形式与 exec 形式的 CMD', '<p>下面是按本篇验证过的规则写的 Flask Dockerfile 的常见形状(<strong>这个完整的 Dockerfile 没有被构建过</strong>,因为拉不到 <code>python:3.14-slim</code>;每一步的效果在本篇里分别验证过):</p><pre>' + DF + '</pre><p>依赖在源码之前(层缓存)、pip 不留缓存、PYTHONUNBUFFERED、非 root、exec 形式 CMD、绑定 0.0.0.0。</p>'),
     ('docker build --check', None),
     ('pip install', None),
     ('绑定地址', None),
     ('日志缓冲', None),
     ('只读目录', None)],
    steps, [ENV_F + '。Docker 29.8.0(Docker Desktop),构建只用 FROM scratch;本机 Python 3.14、Flask 3.1.3、gunicorn 26.2.0', '没有验证:用 python 基础镜像构建完整的 Flask 镜像、docker run 与端口映射、真的换成非 root 用户(只用 chmod 模拟)、useradd 与文件属主、HEALTHCHECK、多阶段构建、镜像大小优化(slim/alpine 对比)、compose 与 K8s 编排、容器里 gunicorn 的信号(信号处理见第 189 篇)'], 'Docker 部署 Flask')
