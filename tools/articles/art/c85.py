from lib import *
S = SS('c85')
steps = [
    step("用 -e API_KEY=S3CR3T-demo-value-123(假的秘密值)启动容器,哪里能看到:docker inspect(Config.Env 和整个输出)能看到;docker exec 里 env 能看到;容器里 /proc/1/environ 能看到;从虚拟机里读 /proc/<容器主进程 PID>/environ 能看到;docker exec 起的后续进程也继承;另一个容器里 env 看不到;docker logs、docker ps、docker events 里也看不到。能执行 docker inspect 或 docker exec 的人,就能拿到环境变量里的秘密。", t=tl(S(1)), done=lidx(S(1), '另一个容器', 'docker events / docker logs'), mark=lidx(S(1), 'docker inspect(Config.Env)', 'docker exec 里 env', '/proc/1/environ', '虚拟机里读'), kv=KV([['能看到', 'docker inspect、docker exec env、/proc/PID/environ、虚拟机里读'], ['看不到', '另一个容器、docker logs / ps / events']], ['能看到'])),
    step("命令行参数里的秘密(sh 作为 PID 1,参数里带 --token=…):docker ps --no-trunc 的 COMMAND 列能看到;docker top 能看到;docker inspect 的 Args / Path 能看到;docker events 里看不到。命令行参数比环境变量暴露得更广——任何 ps 或 docker ps 都能显示。", t=tl(S(2)), done=lidx(S(2), 'docker top', 'docker ps --no-trunc'), mark=lidx(S(2), 'docker inspect 的 Args'), kv=KV([['docker ps --no-trunc / docker top / docker inspect', '都能看到命令行里的秘密'], ['docker events', '看不到']], ['docker ps --no-trunc / docker top / docker inspect'])),
    step("读完就删能抹掉吗:Python 读 API_KEY 后 os.environ.pop,os.environ 里确实没了(False),但 /proc/self/environ 里还有(True);docker exec 读 /proc/1/environ 仍能看到;docker inspect 的 Config.Env(创建容器时的配置)当然也还在。进程里 unset 抹不掉这些痕迹。", t=tl(S(3)), done=lidx(S(3), '/proc/self/environ', 'docker exec cat /proc/1/environ'), mark=lidx(S(3), 'os.environ 里还有吗', 'docker inspect Config.Env'), kv=KV([['os.environ.pop', '进程内存里的 environ 被删'], ['/proc/self/environ', '启动时的原始环境块仍可读'], ['docker inspect', '配置里仍有']], ['/proc/self/environ'])),
    step("改用挂载只读文件(-v 文件:/run/secrets/api_key:ro)让应用自己读:docker inspect 整个输出里看不到秘密值,docker exec env 看不到,/proc/1/environ 看不到;应用仍然读得到文件内容;docker inspect 只显示挂载的路径 /run/secrets/api_key。注意:能 docker exec 进容器的人仍然可以 cat 那个文件。", t=tl(S(4)), done=lidx(S(4), '应用仍然读得到文件'), mark=lidx(S(4), 'docker inspect 整个输出'), kv=KV([['inspect / env / environ', '都看不到秘密值'], ['应用', '读得到文件'], ['仍可见', '能 exec 进容器的人 cat 文件']], ['inspect / env / environ'])),
]
A = mkartc('c85', 85, 'Docker,环境变量,密钥泄露,docker inspect,secrets,/proc/environ,真实验证,动画演示',
    '用假的秘密值实测环境变量的可见范围:-e 传入的值在 docker inspect、docker exec env、/proc/PID/environ、虚拟机里都能读到(另一个容器和 docker logs 看不到);命令行参数在 docker ps --no-trunc、docker top、docker inspect 里都可见;进程里 pop 掉环境变量抹不掉 /proc/self/environ;改成只读挂载文件后 inspect、env、environ 都看不到秘密值。',
    '用环境变量传密码到底安全吗?这篇用一个假的秘密值,逐个检查 docker inspect、exec、/proc、日志、命令行和其它容器能不能看到它,以及 unset 之后的痕迹,最后对比挂载文件的做法。',
    [('4 处能看到', '环境变量里的秘密:docker inspect、docker exec env、/proc/1/environ、虚拟机里的 /proc'), ('pop 抹不掉', '进程内 os.environ.pop 后,/proc/self/environ 里仍能读到'), ('文件挂载看不到', '改成只读挂载文件,docker inspect、env、environ 里都没有秘密值')],
    [('环境变量', '<p>能运行 <code>docker inspect</code> 或 <code>docker exec</code> 的人可以直接读到环境变量,在虚拟机里也能从 <code>/proc</code> 读;没有权限的容器和日志里看不到。</p>'),
     ('命令行', '<p>把秘密写在命令行参数里更糟,<code>docker ps --no-trunc</code> 就能列出来。</p>'),
     ('进程内删除', '<p>应用读完把变量 pop 掉只影响进程内的 <code>os.environ</code>;内核保留的启动时环境块(<code>/proc/self/environ</code>)和 docker 的配置都还在。</p>'),
     ('用文件', '<p>只读挂载的秘密文件不出现在 docker inspect 的环境里,也不在 env 里;但仍然是「能进容器的人都能读」,所以它减少的是意外泄露面(日志、inspect 输出、环境转储),不是权限边界。BuildKit 的 secret mount(c8)是构建期的同类做法。运行期的专用方案(Swarm / Kubernetes secrets)我没有测。</p>')],
    steps,
    [ENV_C + '。秘密是假字符串 S3CR3T-demo-value-123;逐处检查是否包含它;虚拟机里的 /proc 用特权容器加 nsenter 读取(方法见 c19);文件挂载用本项目临时目录下的文件;实验后已删除容器和临时文件',
     '没有验证:compose 的 secrets、Swarm secrets、docker run --env-file 的痕迹(shell 历史里没有)、docker history 里 ENV / ARG 的暴露(见 c7)、日志里误打印环境变量的情形、各 Linux 发行版上 /proc 的 hidepid 设置'],
    '环境变量泄露')
