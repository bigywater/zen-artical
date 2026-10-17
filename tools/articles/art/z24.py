from lib import *
R = J('z24'); d = R['default']
def S(k): return [l for l in out('z24').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("默认服务端(jute.maxbuffer 默认值 1048575 字节):创建数据 1048000、1048500 字节成功;1048560 字节开始 ConnectionLoss,1048576、2 MiB 同样。服务端日志:「java.io.IOException: Len error. A message from /127.0.0.1:… with advertised length of 1048616 is either a malformed message or too large to process (length is greater than jute.maxbuffer=1048575)」。限制的是整个请求包(数据 + 路径 + 请求头),所以数据本身的上限比 1048575 略小。", t=tl(S(1)[:5] + S(1)[5:6]), mark=[2, 3, 4], done=[0, 1], kv=KV([['上限', '整个请求包 ≤ 1048575 字节'], ['超过时', '服务端断开连接 + 日志 Len error']], ['上限'])),
    step("服务端设 -Djute.maxbuffer=4194304:kazoo 写 3 MiB 成功、读回长度 3145728(kazoo 不检查响应大小)。官方 Java 客户端用默认值:stat /b3 成功(不传数据,dataLength = 3145728),但 get /b3 得到「WatchedEvent state:Disconnected」「KeeperErrorCode = ConnectionLoss for /b3」——响应超过客户端自己的上限,客户端主动断开。", t=tl(S(2)), mark=[3], done=[0, 1, 2], kv=KV([['服务端调大', '写 3 MiB 成功'], ['客户端没调大', '读 3 MiB → ConnectionLoss']], ['客户端没调大'])),
    step("客户端也加 -Djute.maxbuffer=4194304:get /b3 完整返回 3145728 字节。要让大数据完整读写,服务端与客户端的 jute.maxbuffer 都要调大(集群里是所有节点)。服务端 4 MiB 上限时写 5 MiB 仍然 ConnectionLoss。", t=tl(S(2)[-1:] + S(3)), done=[0], mark=[1], kv=KV([['两端都要设', '服务端管请求,客户端管响应']], ['两端都要设'])),
]
A = dict(
    n=24, series='zookeeper', tags='ZooKeeper,jute.maxbuffer,消息大小,真实验证,动画演示',
    desc='Jute 最大消息大小实测:默认 jute.maxbuffer=1048575 字节,数据 1048500 字节成功、1048560 字节 ConnectionLoss,服务端日志记录「Len error」;服务端调到 4 MiB 后 kazoo 能读写 3 MiB,官方 Java 客户端没调大时读取会 ConnectionLoss,两端都调才完整。',
    lead='jute.maxbuffer 是 ZooKeeper 里最容易被忽略、又最容易让人困惑的参数:超过它,你看到的只是 ConnectionLoss。这篇找出它的准确临界点、服务端日志里的证据,以及服务端与客户端各自管什么。',
    facts=[('1048575', 'jute.maxbuffer 默认值(字节),限制整个请求包'), ('Len error', '请求超限时服务端日志里的错误,客户端只看到 ConnectionLoss'), ('两端都要设', '服务端限制请求大小,Java 客户端限制响应大小')],
    body=[
        sec('默认值的临界点', '', term('', blk('z24', 1)), '<p>数据 1048500 字节还能成功,1048560 就失败,差的几十字节是请求头与路径。</p>'),
        sec('调大服务端', '', term('', blk('z24', 2))),
        sec('两端一起调', '', term('', blk('z24', 3)), '<p>官方文档的建议是调大这个值前先想想是不是该换设计:大数据放进 ZooKeeper 本身就不合适(第 1、22 篇)。</p>'),
        sec('分步演示', '', demo('jute.maxbuffer', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。服务端 JVM 参数 -Djute.maxbuffer=4194304 通过 Node 的 jvm 参数传入;Java 客户端用官方 ZooKeeperMain;kazoo 2.11.0', '没有验证:集群里只有部分节点调大的后果、Netty 与 NIO 的差异、其它相关参数(如 zookeeper.large_request_max_bytes)、数据压缩'],
)
