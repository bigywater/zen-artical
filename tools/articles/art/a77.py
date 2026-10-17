import json
from lib import *
txt = out('77').splitlines()
J = json.load(open('out/77.json'))
def block(a, b):
    i = next(k for k, l in enumerate(txt) if l.startswith(a)); j = next((k for k, l in enumerate(txt) if l.startswith(b) and k > i), len(txt))
    return '\n'.join(l for l in txt[i+1:j] if l.strip())
t1 = next(l for l in txt if l.strip().startswith('a == b')); t2 = next(l for l in txt if l.strip().startswith('hmac.compare_digest'))
nums = lambda l: [float(x) for x in l.replace('µs', ' ').split() if x.replace('.', '', 1).isdigit()]
eq, cd = nums(t1), nums(t2)
tag, ft = J['tag'], J['forged_tag']
sh = lambda h: h[:16] + '…' + h[-8:]
FL = lambda cur, done=(): {'nodes': [['服务端签名', ''], ['攻击者拿到 tag', ''], ['补 glue 填充', ''], ['接着算 SHA-256', ''], ['服务端验证', '']], 'cur': cur, 'done': list(done)}
steps = [
    step("服务端对 b'user=ann&role=user' 签名:tag = sha256(secret ‖ message),secret 是 16 字节随机数。", fl=FL([0]),
         kv={'items': [['message', J['msg']], ['tag', sh(tag)]], 'hl': ['tag']}),
    step("攻击者只知道 message、tag 和 secret 的长度(16)。而 SHA-256 的输出 tag 恰好就是它处理完 secret‖message(含填充)后的完整内部状态——8 个 32 位字。", fl=FL([1], [0]),
         kv={'items': [['tag(=内部状态)', sh(tag)], ['secret 长度', '16 字节(已知)']], 'hl': ['tag(=内部状态)']}),
    step(f"SHA-256 在消息末尾会补一个 0x80、若干个 0 和 64 位长度。攻击者能算出 secret‖message 那次补的 {J['glue_len']} 字节填充,把它当作新消息的一部分。", fl=FL([2], [0, 1]),
         kv={'items': [['glue', f"{J['glue_len']} 字节: 0x80 + 零 + 长度 0x0110"], ['要追加的后缀', "b'&role=admin'"]], 'hl': ['glue']}),
    step("把 tag 当初始状态,直接从后缀开始继续跑压缩函数——不需要 secret。得到伪造的 tag。", fl=FL([3], [0, 1, 2]),
         kv={'items': [['伪造 message', 'user=ann&role=user' + '\\x80…\\x01\\x10' + '&role=admin'], ['伪造 tag', sh(ft)]], 'hl': ['伪造 tag']}),
    step("服务端拿 secret 重新算 sha256(secret ‖ 伪造message):和攻击者算的一模一样,验证通过。role=admin 被接受。", fl=FL([4], [0, 1, 2, 3]),
         kv={'items': [['server_verify(伪造 message, 伪造 tag)', 'True'], ['攻击者见过 secret?', '从未']], 'hl': ['server_verify(伪造 message, 伪造 tag)']}),
    step("换成 HMAC:内外两层哈希,外层把内层结果再套一次密钥。同样的伪造方式得到的 tag 是错的,验证失败。", fl=FL([4], [0, 1, 2, 3]),
         kv={'items': [['HMAC tag', sh(J['h_tag'])], ['同样伪造出的 tag', sh(J['h_forged'])], ['通过验证?', 'False']], 'hl': ['通过验证?']}),
]
A = dict(
    n=77,
    tags='Python,标准库,安全,密码学,真实验证,动画演示',
    desc='本机用自己实现并与 hashlib 对拍通过的 SHA-256,真实对 sha256(secret+message) 做长度扩展攻击:不知道 16 字节密钥就伪造出 role=admin 的合法签名并通过服务端验证;同样方法对 hmac 无效;并测得 == 比较在第 1 字节与最后 1 字节不同时耗时相差约 1.6 万倍(0.04 µs 对 632 µs),compare_digest 恒定。',
    lead='「密钥拼在消息前面再取哈希」看起来很合理,却是一个经典的错误。这篇不只是说它错——而是真的写了一个 SHA-256、真的伪造出一个服务端认可的签名,然后换成 HMAC 再试一遍。',
    facts=[('16 字节密钥', '攻击者从未见过它,却伪造出通过验证的 role=admin 签名'), ('False', '同样的攻击对 HMAC-SHA256 验证失败'), (f'{eq[0]:.2f} vs {eq[1]:.0f} µs', '== 比较第 1 字节不同与最后 1 字节不同的耗时')],
    body=[
        sec('做的事:服务端用 sha256(secret + message) 签名', '',
            src('服务端(有缺陷的做法)', '''secret = os.urandom(16)
def server_sign(msg):   return hashlib.sha256(secret + msg).hexdigest()
def server_verify(msg, tag): return hmac.compare_digest(server_sign(msg), tag)

msg = b"user=ann&role=user"
tag = server_sign(msg)      # 发给客户端'''),
            '<p>要做长度扩展攻击,得能「从别人给的哈希值继续算」。标准库的 <code>hashlib</code> 不提供这个接口,所以我自己写了一个纯 Python 的 SHA-256,允许指定初始状态。先确认它没写错:</p>',
            term('', block('== 〇', '== 一'))),
        sec('验证一:伪造出一个服务端认可的 role=admin', '攻击者只知道 message、tag、密钥长度',
            term('', block('== 一', '== 二') + '\n' + block('== 二', '== 三')),
            callout('这里的 tag <b>不是</b>被「破解」了,密钥也没被泄露——攻击者只是利用了 SHA-256 的结构:输出的摘要就是它处理完输入后的内部状态,拿它当起点可以继续往后算。而服务端验证时也是同样从头算,两边的结果自然一样。伪造的消息里夹着 30 字节的 <code>\\x80\\x00…</code> 填充,这是能通过验证的代价——如果服务端解析消息时对这些字节不敏感(比如 URL 参数里后出现的 <code>role</code> 覆盖前面的),攻击就成立了。', True)),
        sec('验证二:HMAC 挡住了同样的攻击', '',
            term('', block('== 三', '== 四')),
            '<p>同样的方法对 <code>hmac.new(secret, msg, sha256)</code> 的 tag 做,得到的伪造 tag 通不过验证——HMAC 会对「密钥+消息」再套一层哈希,输出的摘要不再等于可继续的内部状态。另外 <code>hmac.new</code> 在 3.14 里必须显式传 <code>digestmod</code>,忘了会直接 TypeError,不会悄悄用某个弱默认值。</p>'),
        sec('验证三:比较 tag 也有讲究', '== 会在第一个不同的字节处提前返回',
            term('', block('== 四', 'zzzz')),
            f'<p>两段 20 MB 的数据,<code>==</code> 在第 1 个字节就不同时只要 {eq[0]:.2f} µs,最后 1 个字节才不同时要 {eq[1]:.0f} µs——耗时暴露了「前面有几个字节是对的」,攻击者可以据此逐字节猜出正确的 tag(本次只测了本机内存里的比较,没有在网络上真的猜)。<code>hmac.compare_digest</code> 不管哪里不同都是 {cd[0]:.0f} µs 上下,不泄露位置。代价是它总要比较完整个长度,所以只应该用于比较密钥相关的值。</p>'),
        sec('分步演示:一次长度扩展攻击', '哈希值取自上面实验(截断显示)',
            demo('伪造签名,不需要密钥', [('fl', 'flow', '攻击步骤'), ('kv', 'kv', '这一步的数据')], steps, '这一步的关键数据')),
    ],
    refs=['本机 macOS 27 / Python 3.14.7,标准库 <code>hashlib</code>、<code>hmac</code>;SHA-256 为自己实现,已与 hashlib 对拍 6 组输入一致',
          '没有验证:SHA-3 / BLAKE2 等对长度扩展免疫的哈希、真实网络环境下用时间差猜 tag 的可行性(本次只测了本机内存比较的耗时差)、密钥长度未知时逐个尝试的成本'],
)
