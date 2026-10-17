from lib import *
R = J('d128')
def S(k): return [l for l in out('d128').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("signing:用密钥 A 签名 {'order': 7};同一个密钥 A 校验得到原数据;换成密钥 B 校验 → BadSignature;密钥 B + SECRET_KEY_FALLBACKS=[A] 又能校验通过。", t=tl(S(1)), mark=[2], done=[1, 3], kv=KV([['换密钥', '旧签名失效'], ['SECRET_KEY_FALLBACKS', '旧签名仍有效']], ['SECRET_KEY_FALLBACKS'])),
    step("已登录用户(数据库会话后端):换成密钥 B 后 /who/ 变成 anonymous——用户被登出了;密钥 B + fallback A 时仍是 ann。数据库里的会话行没有被删,只是 Django 不再认它(会话里保存的认证哈希与密钥有关)。", t=tl(S(2)), mark=[1], done=[2], kv=KV([['数据库会话', '换密钥 → 被登出'], ['fallback', '保持登录']], ['数据库会话'])),
    step("密码重置令牌:用密钥 A 生成;密钥 A 下 check_token 是 True,换成密钥 B 是 False(已发出的重置链接全部失效),密钥 B + fallback A 又是 True。", t=tl(S(3)), mark=[1], done=[0, 2], kv=KV([['重置链接', '换密钥即失效']], ['重置链接'])),
    step("不受影响的:换密钥后用密码登录仍然成功(密码哈希不依赖 SECRET_KEY);密钥 A 下拿到的 CSRF 令牌,在密钥 B 下 POST 仍是 200。", t=tl(S(4)), done=[0, 1], kv=KV([['密码哈希', '不受影响'], ['CSRF 令牌', '不受影响']], ['密码哈希'])),
    step("signed_cookies 会话后端:整个会话在 cookie 里(本例 227 字符),靠密钥签名;换成密钥 B 后 /who/ 是 anonymous。另外,SECRET_KEY 为空时读取它直接抛 ImproperlyConfigured: The SECRET_KEY setting must not be empty.", t=tl(S(5) + S(6)), mark=[2], kv=KV([['signed_cookies', '换密钥 → 登出'], ['空密钥', 'ImproperlyConfigured']], ['signed_cookies'])),
]
A = dict(
    n=128, series='django', tags='Django,安全,SECRET_KEY,签名,会话,真实验证,动画演示',
    desc='SECRET_KEY 的用途,靠换密钥来验证:signing 签名、会话的认证哈希、密码重置令牌换密钥后全部失效;SECRET_KEY_FALLBACKS 让旧值继续有效;密码哈希、CSRF 令牌不受影响;空密钥抛 ImproperlyConfigured。',
    lead='SECRET_KEY 到底用来做什么?与其背文档,不如换一次密钥看什么会坏、什么不会。这篇用 override_settings 在同一个项目里切换密钥,逐项验证,并试 SECRET_KEY_FALLBACKS 做平滑轮换。',
    facts=[('会失效的', 'signing 签名、已登录会话、密码重置令牌、signed_cookies 会话'), ('不受影响的', '密码哈希、CSRF 令牌(本实验里换密钥后仍通过)'), ('SECRET_KEY_FALLBACKS', '把旧密钥放进去,旧签名、会话、令牌继续有效')],
    body=[
        sec('签名', '', term('', blk('d128', 1)), '<p>Django 的很多功能都建立在 <code>django.core.signing</code> 之上,密钥泄漏就意味着别人能伪造这些签名。</p>'),
        sec('会话与登录状态', '', term('', blk('d128', 2))),
        sec('密码重置令牌', '', term('', blk('d128', 3))),
        sec('不受影响的东西', '', term('', blk('d128', 4)), '<p>CSRF 令牌不依赖 <code>SECRET_KEY</code> 这一点,只是在本实验的设置下观察到的。</p>'),
        sec('signed_cookies 与空密钥', '', term('', blk('d128', 5) + '\n' + blk('d128', 6))),
        sec('分步演示', '', demo('SECRET_KEY 的影响', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite;用 override_settings 在同一进程里切换密钥(A、B 是实验用的字符串);会话用 Client.login 创建', '没有验证:密钥泄漏后的具体攻击(本文只做防御侧验证)、SECRET_KEY_FALLBACKS 的数量上限、Django 内置之外的第三方包对密钥的使用、messages cookie、在多实例之间不同步密钥的后果'],
)
