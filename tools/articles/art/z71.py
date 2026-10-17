from lib import *
R = J('z71'); pm = R['perm']
def S(k): return [l for l in out('z71').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("默认 ACL 是 world:anyone 加全部权限(perms=31 = CREATE 4 + READ 1 + WRITE 2 + DELETE 8 + ADMIN 16,即 cdrwa)。不指定 ACL 创建的节点,任何匿名连接都能读(成功读到 hello)、写、删。ZooKeeper 默认是「不设防」的。", t=tl(S(1)), mark=[0, 1, 2, 3], kv=KV([['默认 ACL', 'world:anyone:cdrwa(31)']], ['默认 ACL'])),
    step("用 digest 保护:create 时给 ACL = digest:admin(全部权限)。ACL 里保存的是「admin:B05meOa…=」(用户名 + 口令的哈希)。匿名连接对 /secret 的读、写、读 ACL、改 ACL、列子节点、创建子节点、删子节点全部是 NoAuthError;先 add_auth('digest', 'admin:adminpw') 认证过的连接全部成功。", t=tl(S(2)), mark=list(range(1, 8)), done=list(range(8, 15)), kv=KV([['匿名', '全部 NoAuth'], ['已认证', '全部成功']], ['匿名'])),
    step("五种权限分别控制:READ(读数据与列子节点)、WRITE(改数据)、CREATE(创建子节点)、DELETE(删除子节点)、ADMIN(改 ACL)。给四个用户各不同权限:reader 只能 get;writer 能 get + set;maker 能 get + 创建子节点;deleter 能 get + 删子节点;四个人都不能 set_acl(没有 ADMIN)。注意 CREATE 与 DELETE 是对「子节点」操作的权限,看的是父节点的 ACL。", t=tl(S(3)), done=[0, 1, 2, 3], kv=KV([['READ / WRITE', '本节点的数据'], ['CREATE / DELETE', '本节点的子节点'], ['ADMIN', '改 ACL']], ['CREATE / DELETE'])),
]
A = dict(
    n=71, series='zookeeper', tags='ZooKeeper,ACL,权限控制,digest,真实验证,动画演示',
    desc='ACL 权限控制实测:默认 world:anyone:cdrwa(任何人可读写删);digest 保护后匿名所有操作都是 NoAuth;CREATE / READ / WRITE / DELETE / ADMIN 五种权限各自控制什么(reader / writer / maker / deleter 的对照表)。',
    lead='ZooKeeper 的 ACL 默认是完全开放的。这篇从默认值开始,用 digest 保护一个节点,再把五种权限逐一拆开测:谁能读、谁能写、谁能创建 / 删除子节点、谁能改 ACL。',
    facts=[('默认完全开放', '不指定时是 world:anyone:cdrwa(perms=31)'), ('5 种权限', 'CREATE / READ / WRITE / DELETE / ADMIN(cdrwa)'), ('CREATE / DELETE 看父节点', '它们控制的是「在这个节点下」创建 / 删除子节点')],
    body=[
        sec('默认 ACL', '', term('', blk('z71', 1))),
        sec('用 digest 保护一个节点', '', term('', blk('z71', 2))),
        sec('五种权限', '', term('', blk('z71', 3)), '<p>表里每一行都是一个只有那一种(加 READ)权限的用户做的真实尝试。</p>'),
        sec('分步演示', '', demo('ACL', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。单机;客户端 kazoo 的 add_auth / make_digest_acl;ACL 的 digest 口令是实验用的假口令', '没有验证:超级用户(zookeeper.DigestAuthenticationProvider.superDigest)绕过 ACL、skipACL、enforceQuota、ACL 对 multi 的影响'],
)
