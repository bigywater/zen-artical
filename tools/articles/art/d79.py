from lib import *
R = J('d79'); pf = R['perf']; wh = R['where']
ks = list(pf)
steps = [
    step("五种存储各把数据放在哪里:db → django_session 表 1 行;cache → 只在缓存里,表里 0 行;cached_db → 缓存 + 表(表里 1 行);file → SESSION_FILE_PATH 下 1 个文件;signed_cookies → 全部数据在 cookie 里(cookie 值 89 个字符,是 base64 的 JSON + 签名),服务端什么都不存。前四种的 cookie 只是 32 位 session id。", t=tl([f"{k:<15} {v}" for k, v in wh.items()], cur=[0, 2, 3], mark=[4]), kv=KV([['服务端存储', 'db / cache / cached_db / file'], ['客户端存储', 'signed_cookies']], ['signed_cookies'])),
    step("signed_cookies 的安全边界:cookie 里的数据只是 base64 编码(不需要密钥就能读出 {\"k\":\"…\"}),签名只防篡改、不保密——不要往里放敏感信息;篡改签名后服务端读到空 session;cookie 大小随数据增长:存 1000 字符 → 816、3000 → 2343、5000 → 3900、8000 → 6231(超过浏览器 4096 字节上限,浏览器会丢弃这个 cookie)。", t=tl(R['signed'].splitlines(), cur=[0], mark=[4, 5]), kv=KV([['可读', '签名只防篡改'], ['大小', '超过 4 KB 浏览器丢弃']], ['大小'])),
    step("本机一次「读」「写」请求的耗时(300 次中位数,测试客户端):" + ';'.join(f"{k} 读 {pf[k]['read']:.3f} / 写 {pf[k]['write']:.3f} ms" for k in ks) + "。缓存与 signed_cookies 最快;db 写最慢(UPDATE + 事务);cached_db 读命中缓存与 cache 相当,写要写库。", b=bars([[f'{k} 写(ms)', pf[k]['write'], f"{pf[k]['write']:.3f}"] for k in ks], max(pf[k]['write'] for k in ks) * 1.1, mark=[0], done=[1, 4]), kv=KV([['读', 'cache / cached_db / signed 最快'], ['写', 'db 最慢']], ['写'])),
    step("选择取舍:db 最简单可靠但每次读写都是数据库;cache 快但缓存被清就掉登录(LocMem 还不能跨进程共享——多 worker 时同一用户可能在不同 worker 看到不同 session,本文没有实测);cached_db 读快、写仍落库,丢缓存不丢 session;file 单机可用;signed_cookies 无服务端状态,但不能主动使某个会话失效、数据可读、大小受限。", kv=KV([['常用组合', 'cached_db(读多写少)'], ['无状态', 'signed_cookies(注意上限与可读)']], ['常用组合'])),
]
A = dict(
    n=79, series='django', tags='Django,session,存储后端,缓存,真实验证,动画演示',
    desc=f'实测 Session 的五种存储后端:数据各放在哪里(表 / 缓存 / 文件 / cookie);signed_cookies 的数据不保密、超过 4 KB 浏览器丢弃(8000 字符 → 6231 字节);读写耗时:db 读 {pf["db"]["read"]:.2f} / 写 {pf["db"]["write"]:.2f} ms,cache 读 {pf["cache"]["read"]:.2f} / 写 {pf["cache"]["write"]:.2f} ms。',
    lead='session 可以放数据库、缓存、文件,甚至客户端 cookie。各自的存放位置、性能、安全边界是什么?这篇把五种后端都搭起来,直接看数据在哪、cookie 里是什么、读写要多久。',
    facts=[('可读', 'signed_cookies 里的数据 base64 一解码就能读,签名只防篡改'), ('4096 字节', 'cookie 后端存 8000 字符 → 6231 字节,超过浏览器上限会被丢弃'), (f'{pf["db"]["write"]:.2f} vs {pf["cache"]["write"]:.2f} ms', 'db 后端与 cache 后端一次写请求的耗时(本机)')],
    body=[
        sec('数据在哪里', '', term('', blk('d79', 1)), '<p>用 <code>SESSION_ENGINE</code> 切换后端。前四种把数据放在服务端,浏览器只拿一个随机 id;<code>signed_cookies</code> 相反,把数据放浏览器里。</p>'),
        sec('signed_cookies 的边界', '', term('', blk('d79', 2)), '<p>用 <code>SECRET_KEY</code> 签名,所以无法伪造;但既不加密,也无法在服务端主动作废(比如「登出所有设备」做不到,第 80 篇的机制是靠密码哈希变化)。</p>'),
        sec('速度', '', term('', blk('d79', 3)), '<p>每次 300 次请求中位数,SQLite 与 LocMem 缓存,没有网络;换成 Redis 缓存 + PostgreSQL,数字会不同(第 98 篇用 Redis 缓存 session)。</p>'),
        sec('分步演示:五种后端', '', demo('Session 存储后端', [('t', 'term', '输出'), ('b', 'bars', '写耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite / LocMemCache / 本机文件;耗时来自 django.test.Client', '没有验证:Redis / Memcached 缓存后端、多 worker 下 LocMem 的不一致(文档说法)、session 文件目录的清理、cached_db 缓存被淘汰后的回源、cookie 后端与 SESSION_SERIALIZER 的关系'],
)
