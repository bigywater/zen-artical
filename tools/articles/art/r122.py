import json
from lib import *
R = J('r122'); al = R['alice']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def fl(nodes, cur=(), done=(), mark=()): return {'nodes': nodes, 'cur': list(cur), 'done': list(done), 'mark': list(mark)}
def tl(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
steps = [
    step("出厂状态:只有一个 default 用户,配置是 on nopass ~* &* +@all——开机、免密、所有 key、所有频道、所有命令。任何能连上端口的人就是它。", t=tl(['> ACL LIST', 'user default on nopass sanitize-payload ~* &* +@all'], mark=[1]), kv=KV([['用户', 'default'], ['密码', 'nopass'], ['权限', '~* &* +@all']], ['权限'])),
    step("建 alice:ACL SETUSER alice on >secret123 ~app:* +get +set。用 alice 登录后:SET app:1 成功;GET other:1 报 NOPERM No permissions to access a key;DEL app:1、PING、KEYS *、ACL LIST 全部报 NOPERM ... has no permissions to run the '…' command。", n=fl([['SET app:1', 'OK'], ['GET other:1', 'NOPERM key'], ['DEL app:1', 'NOPERM 命令'], ['PING', 'NOPERM 命令']], done=[0], mark=[1, 2, 3]), kv=KV([['新用户默认', '-@all,什么命令都不能跑'], ['要什么给什么', '+get +set ~app:*']], ['新用户默认'])),
    step(f"密码不是明文存的:ACL GETUSER / ACL LIST 里是 64 位十六进制,和 sha256(\"secret123\") 逐字符比对{'一致' if R['hash_match'] else '不一致'}。", kv=KV([['ACL LIST', 'user alice … #fcf730b6…f592e4'], ['sha256(secret123)', 'fcf730b6…f592e4'], ['一致', str(R['hash_match'])]], ['一致'])),
    step(f"ACL SETUSER alice off 之后:已经登录的连接继续发 SET → {R['off_existing']};新连接 AUTH → WRONGPASS invalid username-password pair or user is disabled。off 只拦新登录,不踢已登录的连接。", n=fl([['已登录连接', 'SET → OK'], ['新连接 AUTH', 'WRONGPASS']], done=[0], mark=[1]), kv=KV([['off', '拦新登录,不踢老连接']], ['off'])),
    step("ACL DELUSER alice 之后:那条已登录的连接下一次读取直接遇到 EOF——服务端把该用户的连接断开了。要立刻赶走一个用户,用 DELUSER,不是 off。", n=fl([['DELUSER alice', '连接被服务端断开']], mark=[0]), kv=KV([['DELUSER', '断开该用户所有连接']], ['DELUSER'])),
    step(f"改权限即时生效:bob 已登录并 SET 成功,管理员执行 ACL SETUSER bob -set,bob 下一条 SET → {R['revoke'].replace('(error) ','')},GET 仍然可用。", n=fl([['bob SET k 1', 'OK'], ['ACL SETUSER bob -set', ''], ['bob SET k 2', 'NOPERM'], ['bob GET k', '仍可用']], done=[0, 3], mark=[2]), kv=KV([['权限变更', '对已登录连接立即生效']], ['权限变更'])),
    step("持久化:配了 aclfile 时,ACL SAVE 写 users.acl(每行 user … 含密码哈希),重启后 ACL USERS 还有 bob;没配 aclfile 的实例,ACL SAVE 报错,重启后 carol 消失,只剩 default。", n=fl([['aclfile + ACL SAVE', '重启后用户在'], ['没配 aclfile', '重启后用户丢失']], done=[0], mark=[1]), kv=KV([['有 aclfile', ', '.join(R['persist_users'])], ['没配 aclfile', ', '.join(R['noacl_after_restart'])]], ['没配 aclfile'])),
]
A = dict(
    n=122, series='redis', tags='Redis,ACL,安全,真实验证,动画演示',
    desc='在本机实例上把 ACL 用户从头做一遍:default 用户出厂就是免密全权限;新用户默认什么都不能做;密码存 SHA-256;off 不踢老连接、DELUSER 会踢;改权限对已登录连接立即生效;不配 aclfile,重启后用户全没。',
    lead='Redis 6 之后可以有多个用户,每个用户有自己的密码、可访问的 key 和可执行的命令。这篇不讲概念清单,直接在本机起一个实例,建用户、登录、被拒、改权限、删用户、重启,看每一步服务端真实的回答。',
    facts=[('nopass', '出厂的 default 用户免密、~* &* +@all,任何能连上的人拥有全部权限'), ('立即生效', '撤销命令权限后,已登录连接的下一条命令就被拒;DELUSER 会把该用户的连接断开'), ('aclfile', '不配 aclfile,ACL SETUSER 建的用户重启后全部消失(本次实测)')],
    body=[
        sec('出厂状态与新用户', '', term('', blk('r122', 1)), '<p>默认只有一个 <code>default</code> 用户:<code>on nopass ~* &amp;* +@all</code>。所以「没设密码的 Redis」不是没有访问控制,而是访问控制里唯一的用户对所有人开放。</p>', term('', blk('r122', 2)), '<p>新建用户默认 <code>-@all</code>:连 <code>PING</code> 都不行,要什么权限显式给什么。连 <code>ACL WHOAMI</code> 都需要单独授权(上面 alice 就被拒了)。key 越权和命令越权的报错不同:key 报 <code>No permissions to access a key</code>(不说是哪个 key),命令报 <code>User alice has no permissions to run the \'del\' command</code>。</p>'),
        sec('密码存的是什么', '', term('', blk('r122', 3)), '<p>ACL 里只存 SHA-256 哈希(<code>#</code> 开头),上面把明文的 SHA-256 算出来逐字符比对是一致的。注意这是一次不加盐的快速哈希——它防的是「配置文件/ACL 文件被看到时直接读出明文」,不是防离线暴力破解;密码要够长够随机。(加盐与否是从「哈希与 sha256 一致」这个结果推出来的:一致说明没有加盐。)</p>'),
        sec('off、DELUSER 与已登录的连接', '', term('', blk('r122', 4)), '<p><code>off</code> 只阻止新的登录,已登录的连接照常工作;<code>DELUSER</code> 会断开该用户的连接。所以「禁用某个泄露了密码的账号」应当用 <code>DELUSER</code>(或者 off 之后再 <code>CLIENT KILL USER alice</code>——这一条本文没有验证)。</p>'),
        sec('改权限是否即时生效', '', term('', blk('r122', 5)), '<p>即时生效:不需要用户重新登录。撤销的是命令 <code>-set</code>,<code>GET</code> 不受影响。</p>'),
        sec('持久化:aclfile', '', term('', blk('r122', 6)), '<p>要让用户在重启后还在,用 <code>aclfile</code> 指定文件并执行 <code>ACL SAVE</code>(文件里每行一个用户,密码是哈希)。不配 <code>aclfile</code> 时 <code>ACL SAVE</code> 直接报错,重启后用 <code>ACL SETUSER</code> 建的用户消失。报错信息建议改用 <code>CONFIG REWRITE</code> 存进配置文件——那条路本文没有验证。</p>'),
        sec('分步演示:一个 ACL 用户的一生', '', demo('ACL 用户', [('t', 'term', '服务端输出'), ('n', 'flow', '请求与结果'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。密码明文只是测试用', '没有验证:ACL 与 requirepass 同时存在时的交互(第 126 篇)、CONFIG REWRITE 保存用户、CLIENT KILL USER、user 配置项与 aclfile 同时使用时的报错、Redis 8 以前版本的差异'],
)
