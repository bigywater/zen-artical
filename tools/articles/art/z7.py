from lib import *
R = J('z7'); ops = R['ops']
def S(k): return [l for l in out('z7').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("新建 /p(数据 hello)之后的 stat:czxid=0x2、mzxid=0x2、pzxid=0x2(三个 zxid 都是创建它的那个事务)、version=0、cversion=0、aversion=0、numChildren=0、dataLength=5、ephemeralOwner=0x0(持久节点)。还有 ctime / mtime 两个毫秒时间戳。", t=tl(S(1)), kv=KV([['zxid 三兄弟', 'czxid / mzxid / pzxid'], ['版本号三兄弟', 'version / cversion / aversion']], ['zxid 三兄弟'])),
    step("每种操作改变的字段(只看 /p 自己):set 数据 → mzxid、version、dataLength、mtime 变;创建子节点 → pzxid、cversion、numChildren 变,创建第二个子节点再各 +1;修改子节点的数据 → /p 完全没变化;删除子节点 → pzxid、cversion、numChildren 变;setACL → 只有 aversion 变。", t=tl(S(2)[:6]), done=[0, 1, 2, 4, 5], mark=[3], kv=KV([['version', '本节点数据的修改次数'], ['cversion / pzxid', '子节点列表变化'], ['aversion', 'ACL 的修改次数']], ['cversion / pzxid'])),
    step("两个容易混的点:修改子节点 /p/c 的数据,不会改变 /p 的任何字段(只有创建 / 删除子节点才影响父节点);删除子节点会让父节点的 cversion 增加 1,而不是减少。", t=tl(S(2)[3:5] + S(2)[6:]), mark=[0], kv=KV([['改子节点的数据', '父节点不变'], ['删除子节点', 'cversion 仍然 +1']], ['删除子节点'])),
    step("ctime / mtime 是服务端写入事务时的毫秒时间,不是客户端时间(本例同一台机器,差约 20 ms 是读取的间隔)。", t=tl(S(3)), kv=KV([['时间戳', '服务端时间']], ['时间戳'])),
    step("路径规则(用官方 Java 客户端校验):/ok 与 /中文 成功;以 / 结尾「Path must not end with / character」;出现空节点名(//a、/a//b)报「empty node name」;包含 . 或 .. 的节点名报「relative paths not allowed」;不以 / 开头报「Path must start with / character」。/zookeeper/x 可以创建;/a/b 因父节点 /a 不存在而失败。", t=tl(S(4)), done=[0, 1, 9], mark=[2, 3, 4, 5, 6, 7, 8], kv=KV([['路径', '以 / 开头,不能 / 结尾、不能有空名或 . / ..']], ['路径'])),
]
A = dict(
    n=7, series='zookeeper', tags='ZooKeeper,znode,Stat,数据模型,真实验证,动画演示',
    desc='znode 的数据模型实测:stat 的 11 个字段,哪些操作改变哪些字段(set 改 mzxid/version,创建 / 删除子节点改 pzxid/cversion/numChildren,setACL 只改 aversion;改子节点数据不影响父节点);路径的合法与非法写法。',
    lead='znode 是 ZooKeeper 里唯一的数据结构。它的 stat 里 czxid、mzxid、pzxid、version、cversion、aversion 到底各自什么时候变?路径有什么限制?这篇把每种操作前后的 stat 做 diff,逐项验证。',
    facts=[('3 个 zxid', 'czxid 创建 / mzxid 修改数据 / pzxid 子节点列表最后一次变化'), ('3 个版本号', 'version 数据 / cversion 子节点 / aversion ACL'), ('删子节点 cversion +1', '父节点的 cversion 只增不减')],
    body=[
        sec('stat 的字段', '', term('', blk('z7', 1))),
        sec('每种操作改变了什么', '', term('', blk('z7', 2)), '<p>这个表是后面很多实验的基础:Watcher 和版本号的条件更新(<code>set -v</code>)都建立在这些字段上。</p>'),
        sec('时间戳', '', term('', blk('z7', 3))),
        sec('路径规则', '', term('', blk('z7', 4)), '<p>路径校验发生在 Java 客户端里(请求到达服务端之前)。kazoo 这类客户端会先帮你规范化路径(比如去掉末尾的斜杠),所以这一节用官方的 Java 客户端测;不同语言的客户端对不规范路径的处理可能不同。</p>'),
        sec('分步演示', '', demo('znode 的 stat', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。stat 取自 kazoo 的 get();路径用官方 ZooKeeperMain 创建', '没有验证:ephemeralOwner 的含义与临时节点(第 8 篇)、ACL 的具体语义(第 71 篇)、节点数量与路径深度的上限、数据为空与不存在的区别、ctime 的时区与时钟漂移(多机)'],
)
