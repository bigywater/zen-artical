import json, math
from lib import *
txt = out('78').splitlines()
J = json.load(open('out/78.json')); R = J['rates']
def block(a, b):
    i = next(k for k, l in enumerate(txt) if l.startswith(a)); j = next((k for k, l in enumerate(txt) if l.startswith(b) and k > i), len(txt))
    return '\n'.join(l for l in txt[i+1:j] if l.strip())
def fmt(sec):
    if sec < 100: return f"{sec:.1f} 秒"
    if sec < 7200: return f"{sec/60:.1f} 分钟"
    return f"{sec/3600:.1f} 小时"
order = [('sha256', 'sha256(口令)'), ('pbkdf2 1000', 'pbkdf2 ×1000'), ('pbkdf2 100000', 'pbkdf2 ×100000'), ('scrypt 16384', 'scrypt n=2^14'), ('pbkdf2 600000', 'pbkdf2 ×600000')]
secs = {k: R[k] * 1e6 for k, _ in order}
notes = [
    "直接 sha256:单核纯 Python 循环每秒能试约 190 万次,枚举完 6 位数字的全部 100 万种只要几分之一秒。",
    "pbkdf2 迭代 1000 次:每次猜测慢了约 600 倍,枚举全部 100 万种要 3 分钟左右。",
    "迭代 10 万次:枚举全部要约 3 小时。",
    "scrypt(n=2^14):每次猜测要 32 ms,而且每次要 16 MiB 内存——攻击者的并行度受内存限制。",
    "pbkdf2 迭代 60 万次:每次 64 ms,枚举 100 万种要约 17.9 小时(单核)。",
]
steps = []
for i in range(len(order)):
    items = [[lbl, math.log10(secs[k]) + 1.5, fmt(secs[k])] for k, lbl in order[:i + 1]]
    steps.append(step(notes[i], b={'items': items, 'max': math.log10(secs['pbkdf2 600000']) + 1.5, 'cur': [i], 'done': list(range(i))}))
speed = J['tries'] / J['el']
A = dict(
    n=78,
    tags='Python,标准库,安全,密码学,真实验证,动画演示',
    desc=f'本机真实暴力枚举 sha256 存储的 6 位数字口令:试了 {J["tries"]} 次,用时 {J["el"]*1000:.0f} ms 就找到;对比 pbkdf2_hmac(60 万次迭代,每次约 64 ms)与 scrypt 的每次耗时,并验证加盐后相同口令不再产生相同哈希。',
    lead='把口令存成 <code>sha256(password)</code> 看起来已经「加密」了,其实攻击者一晚上能试的猜测数多到你想象不到。这篇让脚本真的去枚举一遍,再换成故意做得慢的 <code>pbkdf2_hmac</code> 和 <code>scrypt</code>,看每次猜测到底贵了多少。',
    facts=[(f'{J["el"]*1000:.0f} ms', '单核纯 Python 循环枚举出 sha256 存储的 6 位数字口令'), (f'{R["pbkdf2 600000"]*1e3:.0f} ms / 次', 'pbkdf2_hmac 60 万次迭代,每次猜测的成本'), ('相同口令,不同哈希', '加盐之后,两个人用同一口令也认不出来')],
    body=[
        sec('做的事:先当攻击者', '假设数据库泄露,拿到 sha256(口令) 的十六进制串',
            src('实验脚本(节选)', '''stored = hashlib.sha256(b"482915").hexdigest()   # 泄露出来的值
for i in range(1_000_000):                        # 6 位数字口令的全部空间
    g = f"{i:06d}"
    if hashlib.sha256(g.encode()).hexdigest() == stored: break'''),
            term('', block('== 一', '== 二')),
            f'<p>这是一个没有任何优化的 Python 循环,速度已经约 {speed:,.0f} 次/秒;用 C、多核或显卡,速度只会高几个数量级(这条我没有实测,只是指出瓶颈在猜测速度而不是算法)。口令如果落在常见口令字典里就更快:10 个常见口令的字典,命中 <code>letmein</code> 只用了 9 微秒。</p>'),
        sec('验证一:不加盐,相同口令得到相同哈希', '', term('', block('== 二', '== 三')),
            '<p>ann 和 bob 用了同一个口令,库里的 sha256 一模一样——攻击者不用算,一眼就知道他俩口令相同,还能用一张预先算好的「哈希 → 口令」表(彩虹表)一次查完全库。每人一个随机 16 字节盐之后,同一个口令得到完全不同的值,攻击者只能逐个用户单独猜。盐不需要保密,和哈希一起存就行。</p>'),
        sec('验证二:让每次猜测变贵', '<code>pbkdf2_hmac</code> 的迭代次数、<code>scrypt</code> 的内存参数', term('', block('== 三', '== 四')),
            f'<p>单次 <code>sha256</code> 只要 0.29 µs;<code>pbkdf2_hmac</code> 迭代 60 万次,一次要 {R["pbkdf2 600000"]*1e3:.1f} ms,慢了约 {R["pbkdf2 600000"]/R["sha256"]:,.0f} 倍。对正常用户,一次登录多花 64 ms 完全无感;对要枚举 100 万种可能的攻击者,单核就是 {fmt(secs["pbkdf2 600000"])}。<code>scrypt</code> 除了耗时还要占内存(表里按公式 128·n·r 估算,并非实测),让攻击者不好靠大量并行硬件压价。迭代次数应当随机器变快而调高,而不是写死。</p>'),
        sec('验证三:实际存储和校验', '盐、迭代次数和哈希存在一个字符串里', term('', block('== 四', 'zzzz')),
            '<p>把算法、迭代次数、盐、哈希用 <code>$</code> 拼起来存一个字段,以后调高迭代次数时旧记录仍能按它自己的参数验证。同一口令两次生成的记录不同(盐不同),所以不能拿字符串比较去查「谁用了这个口令」;校验用 <code>hmac.compare_digest</code>(见上一篇)。</p>'),
        sec('分步演示:同一个 6 位数字口令,枚举全部空间要多久', '每个数字都是本机单核实测每次猜测的耗时 × 100 万(条长按对数刻度)',
            demo('每次猜测越贵,枚举越慢', [('b', 'bars', '枚举 100 万种可能所需时间(对数刻度)')], steps, '新加入的算法')),
    ],
    refs=['本机 macOS 27 / Python 3.14.7,标准库 <code>hashlib</code>(<code>sha256</code>、<code>pbkdf2_hmac</code>、<code>scrypt</code>)、<code>hmac.compare_digest</code>',
          '没有验证:argon2、bcrypt(标准库不带)、GPU 攻击的实际速度、迭代次数应该取多少(取决于你的硬件和登录延迟预算)'],
)
