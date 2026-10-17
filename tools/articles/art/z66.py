from lib import *
R = J('z66'); df = R['default']; fu = R['full']
def S(k): return [l for l in out('z66').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("默认配置(没有设置 4lw.commands.whitelist)下,17 个四字命令里只有 srvr 能执行,其它都返回「xxx is not executed because it is not in the whitelist.」;服务端日志里也写着「The list of enabled four letter word commands is : [[srvr]]」。这是 3.5 之后的默认,很多旧文章里「echo ruok | nc」直接可用的说法在默认配置下不再成立。", t=tl(S(1)[:6] + S(1)[-1:]), done=[2], mark=[1, 3, 4, 5], kv=KV([['默认白名单', '只有 srvr']], ['默认白名单'])),
    step("设成 *(实验用)后每条命令的输出:ruok → imok;srvr / stat → 版本与延迟统计;conf → 服务端配置(clientPort、dataDir、dataDirSize…);cons → 每个客户端连接的详情(来源地址、会话 id sid=…、最后一个操作 lop=…、超时 to=…);dirs → 数据与日志目录大小;dump → 会话与临时节点;envi → 运行环境;gtmk → 追踪掩码;isro → rw / ro;wchs / wchp / wchc → 三种 watch 统计(数量 / 按路径 / 按会话)。", t=tl(S(2)[:24]), done=list(range(0, 24)), kv=KV([['常用', 'ruok / srvr / mntr / cons / wchs'], ['看会话', 'dump / cons']], ['常用'])),
]
A = dict(
    n=66, series='zookeeper', tags='ZooKeeper,四字命令,运维,真实验证,动画演示',
    desc='ZooKeeper 四字命令实测:3.9.6 默认白名单只有 srvr(其它命令返回「not executed because it is not in the whitelist」);设成 * 后 ruok / srvr / stat / conf / cons / dirs / dump / envi / gtmk / isro / wchs / wchp / wchc 的实际输出。',
    lead='四字命令(ruok、stat、mntr……)是 ZooKeeper 运维最古老的接口。现在它默认几乎全部被禁用了。这篇把每条命令在默认配置和放开白名单之后的真实输出都打印一遍。',
    facts=[('只有 srvr', '默认白名单里唯一能用的命令'), ('4lw.commands.whitelist', '用这个参数放开,* 表示全部'), ('17 个命令', '本文实测的四字命令个数')],
    body=[
        sec('默认只有 srvr', '', term('', blk('z66', 1))),
        sec('放开白名单后的输出', '', term('', blk('z66', 2)), '<p>另外还有 mntr、crst、srst、hash 等命令,mntr 的输出在第 65 篇,srst / crst 会清零统计(第 67 篇)。</p>'),
        sec('分步演示', '', demo('四字命令', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。单机;命令通过 TCP 连到客户端端口直接发送四个字母;输出只截取前几行', '没有验证:AdminServer 上对应的命令(第 68 篇)、集群里 leader 才有的信息(dump 的 Session Sets 等,第 12 篇)、较旧版本的默认值'],
)
