import json
from lib import *
txt = out('76').splitlines()
J = json.load(open('out/76.json'))
def block(a, b):
    i = next(k for k, l in enumerate(txt) if l.startswith(a)); j = next((k for k, l in enumerate(txt) if l.startswith(b) and k > i), len(txt))
    return '\n'.join(l for l in txt[i+1:j] if l.strip())
sr_line = next(l for l in txt if 'SystemRandom 做' in l)
bench = {l.split()[0]: float(l.split()[-4]) for l in block('== 五', 'zzzz').splitlines()}
fo, fs = J['first_obs'], J['first_state']
FL = lambda cur, done=(): {'nodes': [['观察 624 个输出', ''], ['逆变换 untemper', ''], ['setstate 克隆', ''], ['预测未来输出', '']], 'cur': cur, 'done': list(done)}
steps = [
    step("攻击者只能看到受害者的 32 位输出——比如网页上暴露的随机数、每个请求带的「随机」ID。先收集连续 624 个。这里是前 4 个:", fl=FL([0]),
         kv={'items': [[f'输出 #{i}', str(v)] for i, v in enumerate(fo)] + [['……', '共 624 个']], 'hl': [f'输出 #{i}' for i in range(4)]}),
    step("Mersenne Twister 的输出是内部状态字经过 4 步可逆的位运算(tempering)得到的。每个输出都能被精确还原成对应的状态字。", fl=FL([1], [0]),
         kv={'items': [[f'输出 #{i}', f'{fo[i]}  →  状态字 {fs[i]}'] for i in range(4)] + [['……', '624 个全部还原']], 'hl': [f'输出 #{i}' for i in range(4)]}),
    step("624 个状态字正好是整个内部状态。把它们 setstate 进一个全新的 Random 对象,就得到了受害者的完全克隆。", fl=FL([2], [0, 1]),
         kv={'items': [['状态字数量', '624'], ['克隆.setstate', '(3, 624 个状态字 + 索引 624, None)']], 'hl': ['克隆.setstate']}),
    step("克隆预测受害者接下来的 5 个输出——5 个全部一致(浮点数和 random.choices 生成的 12 位令牌也一致)。", fl=FL([3], [0, 1, 2]),
         kv={'items': [[f'第 {i+1} 个', f'预测 {p}  =  真实 {r}'] for i, (p, r) in enumerate(zip(J['pred'], J['real']))], 'hl': [f'第 {i+1} 个' for i in range(5)]}),
    step("同样的攻击对 secrets.SystemRandom(读操作系统熵)命中 0/5——内部没有可还原的状态。", fl=FL([3], [0, 1, 2]),
         kv={'items': [['random.Random', '5 / 5 命中'], ['SystemRandom', '0 / 5 命中']], 'hl': ['SystemRandom']}),
]

A = dict(
    n=76,
    tags='Python,标准库,安全,随机数,真实验证,动画演示',
    desc='本机真实验证:random.seed(42) 两次得到同一串数;观察 random 的 624 个 32 位输出后还原出 Mersenne Twister 完整状态,连续预测出接下来的整数、浮点数和一个 12 位「重置令牌」全部命中,而对 secrets.SystemRandom 同样的攻击命中 0/5;并测得 hashlib 跨进程恒定、内置 hash() 跨进程变化。',
    lead='Python 里有三样东西都长得像「随机」:<code>random</code>、<code>secrets</code>、<code>hashlib</code>。它们分别对应三种完全不同的需求。这篇不讲概念,直接做实验:能复现的、猜不到的、算出来永远一样的,到底各是什么表现。',
    facts=[('624 个输出', '看到这么多 random 的输出,就能预测之后的全部'), ('5 / 5 vs 0 / 5', '同一攻击对 random 与 SystemRandom 的命中数'), (f"{bench['random.getrandbits(64)']:.0f} vs {bench['secrets.randbits(64)']:.0f} ns", 'random.getrandbits(64) 与 secrets.randbits(64) 单次耗时')],
    body=[
        sec('三种需求,三个模块', '',
            table(['需求', '该用', '特征'], [['可复现的模拟、测试数据、洗牌', '<code>random</code>', '给同一个种子,得到同一串数'], ['令牌、密码、盐、任何需要「猜不到」的东西', '<code>secrets</code>', '来自操作系统的熵,没有种子'], ['指纹、缓存 key、文件校验', '<code>hashlib</code>', '同一输入永远同一输出,没有随机性']], mono=False),
            '<p>下面每一行结论都来自一次真实运行。</p>'),
        sec('验证一:random 有种子,secrets 没有', '', term('', block('== 一', '== 二') + '\n' + block('== 二', '== 三')),
            '<p><code>random.seed(42)</code> 两次得到完全一样的 6 个数;不给种子(用系统熵初始化)每次不同。<code>secrets.token_hex</code> 每次不同,而且 <code>SystemRandom.seed(42)</code> 被静默忽略——调用不报错,但结果不可复现。所以「想要可复现」只能用 <code>random</code>,「想要不可预测」就不能用 <code>random</code>。</p>'),
        sec('验证二:看够 624 个输出,random 的未来就是透明的', 'Mersenne Twister 是可逆的',
            src('攻击的核心', '''def untemper(y):        # 撤销输出时的 4 步位运算
    y ^= y >> 18
    y ^= (y << 15) & 0xefc60000
    t = y
    for _ in range(5): t = y ^ ((t << 7) & 0x9d2c5680)
    y = t
    t = y
    for _ in range(3): t = y ^ (t >> 11)
    return t

state = [untemper(victim.getrandbits(32)) for _ in range(624)]
clone = random.Random(); clone.setstate((3, tuple(state + [624]), None))'''),
            term('', block('== 三', '== 四')),
            callout('用 <code>random</code> 生成的密码重置令牌、会话 ID、验证码,只要攻击者能看到足够多的同一个生成器的输出,后面的就能被算出来——上面第 3 行的 12 位令牌就是被<b>原样预测</b>出来的。而对 <code>SystemRandom</code> 做完全相同的事,命中数是 0/5。'),
            '<p>注意攻击者事先<b>不知道</b>受害者的种子(受害者用 <code>os.urandom</code> 播种),只看输出。「随机」和「不可预测」是两回事。</p>'),
        sec('验证三:hashlib 不随机,内置 hash() 也不是它', '', term('', block('== 四', '== 五')),
            '<p>三个新进程里,<code>sha256(b\'hello\')</code> 一模一样;而 <code>hash(\'hello\')</code> 每个进程都不同——字符串的内置哈希被加了进程级随机盐。所以不能拿 <code>hash()</code> 做跨进程/持久化的指纹(存进数据库、当分片 key),这种场景要用 <code>hashlib</code>。反过来,<code>hashlib</code> 的输出也不能当随机数或令牌用:输入相同,输出永远相同,一位之差则完全不同(最后一行)。</p>'),
        sec('验证四:安全是有价格的', '', term('', block('== 五', 'zzzz')),
            f'<p>本机上 <code>secrets.randbits(64)</code> 约 {bench["secrets.randbits(64)"]:.0f} ns,<code>random.getrandbits(64)</code> 只要 {bench["random.getrandbits(64)"]:.0f} ns,相差 {bench["secrets.randbits(64)"]/bench["random.getrandbits(64)"]:.0f} 倍左右。绝大多数场景里令牌一次请求只生成一个,这个差距完全可以忽略——只有在大量生成随机数做模拟时,才值得为速度用 <code>random</code>。</p>'),
        sec('分步演示:从 624 个输出到完全预测', '数字都取自上面实验的真实记录',
            demo('还原 Mersenne Twister 状态', [('fl', 'flow', '攻击步骤'), ('kv', 'kv', '此刻的真实数据')], steps, '这一步的关键数据')),
    ],
    refs=['本机 macOS 27 / Python 3.14.7,标准库 <code>random</code>、<code>secrets</code>、<code>hashlib</code>;攻击代码是我自己写的 untemper,不依赖第三方库',
          '没有验证:更少输出量下的部分还原、非 32 位边界的输出(比如只观察 <code>randint(0, 99)</code>)需要多少样本、哈希算法之间的抗碰撞差异'],
)
