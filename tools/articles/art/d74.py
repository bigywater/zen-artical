from lib import *
import re
R = J('d74')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
cost = {}
for l in L('cost'):
    m = re.match(r'(\S+)\s+make\s+([\d.]+) ms\s+check\s+([\d.]+) ms', l)
    if m: cost[m.group(1)] = (float(m.group(2)), float(m.group(3)))
tm = re.findall(r'([\d.]+) ms', R['timing'])
it = [(int(a), float(b)) for a, b in re.findall(r'iterations=\s*(\d+)\s+verify 中位\s+([\d.]+) ms', R['iters'])]
default_it = int(re.search(r'当前默认迭代次数: (\d+)', R['iters']).group(1))
steps = [
    step(f"默认哈希器是 pbkdf2_sha256,编码形如 pbkdf2_sha256${default_it}$盐$哈希:迭代 {default_it} 次(Django 6.1.1),盐 22 个字符、哈希 44 个字符;同一个密码两次 make_password 结果不同(盐随机);make_password(None) 得到以 ! 开头的「不可用密码」,任何输入都校验失败。", t=tl(L('default')), kv=KV([['默认', 'pbkdf2_sha256'], ['迭代', f'{default_it:,}']], ['迭代'])),
    step("本机单次校验的耗时:" + ';'.join(f"{k} {v[1]:.0f} ms" if v[1] >= 1 else f"{k} <1 ms" for k, v in cost.items()) + "。成本越高,暴力破解越慢,登录也越慢——PBKDF2 与 scrypt、bcrypt 在同一个数量级(约 160–220 ms),argon2(argon2-cffi 默认参数:m=102400, t=2, p=8)约 26 ms,md5 几乎为 0(所以永远不要用 md5 存密码,它只在这里作为对照)。", b=bars([[k, v[1], f"{v[1]:.0f} ms"] for k, v in cost.items()], max(v[1] for v in cost.values()) * 1.1, mark=[len(cost) - 1]), kv=KV([['pbkdf2', f"{cost['pbkdf2_sha256'][1]:.0f} ms / 次"], ['argon2', f"{cost['argon2'][1]:.0f} ms / 次"]], ['pbkdf2'])),
    step("自动升级:库里存的是 md5$… 的旧密码,用户用正确密码登录成功后,Django 顺手把它重新哈希成当前默认的 pbkdf2_sha256(库里的值变成 pbkdf2_sha256$1500000$…)。所以换默认哈希器或提高迭代次数,不需要强制用户改密码。", t=tl(L('upgrade')), kv=KV([['升级时机', '用户下一次成功登录']], ['升级时机'])),
    step(f"抗计时探测:「存在的用户 + 错误密码」{tm[0]} ms、「不存在的用户」{tm[1]} ms、「存在 + 正确密码」{tm[2]} ms——三者几乎一样,因为用户不存在时 Django 也会跑一次哈希。攻击者无法靠响应时间判断用户名是否存在。", b=bars([['存在 + 错误密码(ms)', float(tm[0]), tm[0]], ['不存在的用户(ms)', float(tm[1]), tm[1]], ['存在 + 正确密码(ms)', float(tm[2]), tm[2]]], float(tm[0]) * 1.1, done=[0, 1, 2]), kv=KV([['用户不存在', '也跑一次哈希']], ['用户不存在'])),
    step("迭代次数与耗时成正比:" + ';'.join(f"{a:,} 次 → {b:.1f} ms" for a, b in it) + f"。默认 {default_it:,} 次约 160 ms。硬件变快时,官方每个版本会上调默认迭代次数。", b=bars([[f'{a:,} 次(ms)', b, f"{b:.1f}"] for a, b in it], max(b for a, b in it) * 1.1, mark=[len(it) - 1]), kv=KV([['成本', '与迭代次数成正比']], ['成本'])),
]
A = dict(
    n=74, series='django', tags='Django,密码哈希,PBKDF2,Argon2,真实验证,动画演示',
    desc=f'实测 Django 密码哈希:默认 pbkdf2_sha256 迭代 {default_it:,} 次,本机单次校验 {cost["pbkdf2_sha256"][1]:.0f} ms;argon2 {cost["argon2"][1]:.0f} ms、bcrypt {cost["bcrypt_sha256"][1]:.0f} ms、scrypt {cost["scrypt"][1]:.0f} ms;旧算法密码登录后自动升级;用户不存在时也会哈希一次,耗时与「密码错」接近。',
    lead='Django 存的密码是什么样?校验一次要多久?换算法要不要让用户重置?攻击者能不能靠响应时间猜用户名?这篇在本机实测四种哈希器的耗时,并验证自动升级和抗计时的行为。',
    facts=[(f'{default_it:,} 次', 'Django 6.1.1 默认 PBKDF2 迭代次数,本机单次校验约 %.0f ms' % cost['pbkdf2_sha256'][1]), ('自动升级', '旧算法(如 md5)的密码在用户下一次成功登录时被重新哈希为当前默认算法'), (f'{tm[0]} / {tm[1]} ms', '存在用户错误密码 / 不存在用户的 authenticate 耗时,几乎相同')],
    body=[
        sec('默认编码', '', term('', blk('d74', 1)), '<p>格式 <code>算法$迭代$盐$哈希</code>。盐随机,所以数据库里两个相同的密码看起来不同。</p>'),
        sec('各算法的成本', '', term('', blk('d74', 2)), '<p>耗时是本机 5 次取中位数。argon2 与 bcrypt 需要额外安装(<code>argon2-cffi</code>、<code>bcrypt</code>);argon2 的参数是 argon2-cffi 的默认值,不是调优过的结论。选哪个由安全要求决定,这里的数字只说明「成本」可以调。</p>'),
        sec('自动升级', '', term('', blk('d74', 3)), '<p>实测:登录成功后库里的哈希被换成了当前默认算法。所以 <code>PASSWORD_HASHERS</code> 列表的<b>第一个</b>决定新密码用什么,后面的仅用于校验旧密码。</p>'),
        sec('抗计时探测', '', term('', blk('d74', 4)), '<p>实测的结果是三种情形耗时几乎相同;Django 的做法(据源码,本文没有单独验证)是用户不存在时也做一次密码哈希来消耗相近的时间。</p>'),
        sec('迭代次数', '', term('', blk('d74', 5)), '<p>迭代次数与耗时成正比;对登录接口本身,高成本也意味着容易被当成 CPU 消耗型攻击目标——需要限流(本文没有测)。</p>'),
        sec('分步演示:密码哈希', '', demo('密码哈希', [('t', 'term', '输出'), ('b', 'bars', '耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。argon2-cffi 25.1.0、bcrypt 5.0.0;耗时取本机 5 次(迭代对比 3 次)中位数', '没有验证:GPU / 专用硬件下的破解成本、不同 CPU 上的耗时、argon2 / scrypt 的参数调优建议、密码长度上限与截断(bcrypt 的 72 字节)、认证接口的限流'],
)
