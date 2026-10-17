import json
from lib import *
R = J('r133'); sc = R['scan']; cp = R['compress']; rp = R['rdbpull']; en = R['enc']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def fl(nodes, cur=(), done=(), mark=()): return {'nodes': nodes, 'cur': list(cur), 'done': list(done), 'mark': list(mark)}
def tl(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
yn = lambda x: '找到' if x else '没有'
steps = [
    step("在 dump.rdb 和 AOF 的原始字节里直接查找:key 名 session:1001、value 里的 token、脚本产生的 value 都能找到——两种文件都是明文(RDB 里的 value 只可能被压缩,不是加密)。", t=tl([f"{k:<44} RDB:{yn(v[0])}  AOF:{yn(v[1])}" for k, v in sc.items()], cur=[0, 1, 2, 6], mark=[3, 4, 5]), kv=KV([['结论', 'RDB / AOF 都是明文']], ['结论'])),
    step(f"没有出现的:ACL 用户的密码明文、它的 SHA-256 哈希,以及 Lua 脚本正文(EVAL 复制的是脚本产生的写命令,不是脚本源码)。ACL 用户在单独的 users.acl 里,不在 RDB / AOF 里。", t=tl([f"{k:<44} RDB:{yn(v[0])}  AOF:{yn(v[1])}" for k, v in sc.items() if not (v[0] or v[1])], mark=[0, 1, 2]), kv=KV([['不在里面', 'ACL 密码 / 哈希 / 脚本正文']], ['不在里面'])),
    step(f"压缩不是保护:user:1 的 value 是 \"CARDNUM-MARKER;\" 重复 400 次({cp['value_len']} 字节)。dump.rdb 在 rdbcompression yes 时是 {cp['yes']} 字节,关闭压缩是 {cp['no']} 字节——但压缩后的文件里标记照样能找到(第一份原文是明文)。", b=bars([['rdbcompression yes(字节)', cp['yes'], str(cp['yes'])], ['rdbcompression no(字节)', cp['no'], str(cp['no'])]], cp['no'], done=[0], mark=[1]), kv=KV([['压缩后标记', '仍能找到']], ['压缩后标记'])),
    step(f"谁能远程拉走整份数据?redis-cli --rdb 走复制协议。用户 app(~app:* +get +set):REPLCONF 被 NOPERM,拿不到文件({rp['app']['got']})。用户 repl(~app:* -@all +psync +sync +replconf +ping,key 模式只有 app:*):拿到了 RDB,里面包含 app:* 以外的 session:1001 的 token({rp['repl']['leaked']})。复制权限不受 key 模式约束。", n=fl([['app(~app:* +get +set)', 'REPLCONF NOPERM'], ['repl(~app:* +psync +sync +replconf)', '拿到整份 RDB']], mark=[1], done=[0]), kv=KV([['repl 用户', '~app:* 限制不了它拉全量'], ['结论', '+psync / +sync 等同于读全部数据']], ['结论'])),
    step(f"备份加密:openssl enc -aes-256-cbc -pbkdf2 加密 dump.rdb({en['size_in']} 字节 → {en['size_out']} 字节,{en['ms']:.0f} ms),密文里找不到 session:1001 和 token;用对的密码解密与原文件逐字节相同({R['roundtrip']});错误密码 → bad decrypt(returncode {R['wrongpw'][0]})。", n=fl([['dump.rdb', '明文'], ['openssl enc AES-256-CBC', '密文:找不到 key / value'], ['解密', f"与原文件相同 = {R['roundtrip']}"]], done=[1, 2], mark=[0]), kv=KV([['加密后', '找不到 key 名和 value'], ['耗时', f"{en['ms']:.0f} ms"]], ['加密后'])),
    step(f"完整性:在密文中间翻转 1 个比特,openssl 解密 returncode = {R['tamper_rc']}(没有报错);解出的文件有 {R['tamper_diff']} 字节和原文件不同。redis-check-rdb 检查它:returncode {R['tamper_check'][0]},报 {R['tamper_check'][1][-1]}。CBC 不带认证,发现篡改要靠 RDB 自己的校验或额外的 MAC。", n=fl([['翻转 1 比特', ''], ['openssl 解密', 'returncode 0(不报错)'], ['redis-check-rdb', R['tamper_check'][1][-1]]], mark=[1], done=[2]), kv=KV([['CBC', '不认证'], ['篡改后解出', f"{R['tamper_diff']} 字节不同"]], ['CBC'])),
]
A = dict(
    n=133, series='redis', tags='Redis,安全,备份,RDB,AOF,加密,真实验证,动画演示',
    desc=f'备份文件泄露的实测:RDB 和 AOF 里 key 名、value 都是明文,压缩不是保护(压缩后标记仍能找到);ACL 密码与脚本正文不在其中;redis-cli --rdb 用一个 ~app:* 的复制账号就拉走了全量数据;用 openssl AES-256-CBC 加密后找不到明文,但 CBC 不带认证。',
    lead='备份文件丢了、复制账号被盗了,会泄露什么?这篇把 RDB 和 AOF 当作攻击者手里的文件直接查找内容,再验证两件防御:限制拉全量数据的权限,以及备份加密和篡改检测。',
    facts=[('明文', 'RDB 和 AOF 里 key 名与 value 都是明文;压缩只让文件变小,不是保护'), ('~app:* 不管用', '有 +psync +sync +replconf 的账号,即使 key 模式只有 app:*,也能用 redis-cli --rdb 拉走整份数据'), ('CBC 不认证', '密文翻转 1 个比特,openssl 解密仍成功(returncode 0),要靠 redis-check-rdb 或额外 MAC 发现')],
    body=[
        sec('文件里有什么', '', term('', blk('r133', 1)), '<p>用 Python 直接在文件字节里查找,等价于 <code>strings | grep</code>。key 名和 value 都是明文。不在里面的:ACL 用户的密码与哈希(在 <code>users.acl</code> 里,第 132 篇)、Lua 脚本正文(复制的是脚本产生的写命令)。压缩:见表格最后几行,文件小了很多,但一份原文仍在。</p>'),
        sec('通过复制协议拉走全量', '', term('', blk('r133', 2)), f'<p>普通应用账号(<code>+get +set</code>)因为没有 <code>+replconf</code>,<code>redis-cli --rdb</code> 一开始就被拒。但只要账号被授予了复制相关的命令,key 模式(<code>~app:*</code>)就管不住它:它拿到的是完整的 RDB。所以复制账号要单独建、单独保管,并且不要把 <code>+psync</code> / <code>+sync</code> 给应用账号。</p>'),
        sec('备份加密', '', term('', blk('r133', 3)), '<p>这里用 <code>openssl enc</code> 只是最小演示:AES-256-CBC + PBKDF2 + 盐,加密后找不到明文,正确密码能还原,错误密码得到 <code>bad decrypt</code>。CBC 模式本身不带认证,密文被改一个比特,解密照样成功、只是明文里对应位置变了——RDB 自带的校验(<code>redis-check-rdb</code>)这次抓到了篡改,但这是这次翻转的位置恰好落在有效数据里的结果,不能当作对所有篡改都有效。生产上应该用带认证的方案(比如带 MAC 的加密工具),本文没有测。</p>'),
        sec('要做的事', '', '<ul><li>备份文件当作和数据库同等敏感:文件权限见第 132 篇,传输与存放要加密。</li><li>复制账号(<code>+psync</code> / <code>+sync</code> / <code>+replconf</code>)单独建,不要和应用账号共用。</li><li>加密备份、并定期做「解密 + redis-check-rdb」的恢复演练。</li><li>不要指望压缩、key 命名或脚本来隐藏数据。</li></ul>'),
        sec('分步演示:备份里有什么、怎么保护', '', demo('备份文件泄露', [('t', 'term', '查找结果'), ('b', 'bars', '大小'), ('n', 'flow', '过程'), ('kv', 'kv', '结论')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。所有数据都是我构造的假数据(token、卡号标记都是测试字符串)', '没有验证:带认证的加密(AES-GCM / age / gpg)、AOF 文件的加密与校验(redis-check-aof)、Redis 8 之外版本的 --rdb 行为、rdb-key-save-delay 之外的备份路径(如 BGSAVE 到云存储)、复制账号只给 +psync 而不给 +sync 时 redis-cli --rdb 能否成功、磁盘加密(LUKS / FileVault)'],
)
