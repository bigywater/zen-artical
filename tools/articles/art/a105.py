from lib import *
txt = out('105').splitlines()
def block(a, b):
    i = next(k for k, l in enumerate(txt) if l.startswith(a)); j = next((k for k, l in enumerate(txt) if l.startswith(b) and k > i), len(txt))
    return '\n'.join(l for l in txt[i+1:j] if l.strip())
FL = lambda cur, done=(): {'nodes': [['时间', '依赖「现在」'], ['patch 陷阱', '打在哪里'], ['随机数', '种子 / 注入'], ['网络', '禁止外连'], ['sleep', '别真的等']], 'cur': cur, 'done': list(done)}
steps = [
    step("依赖真实时钟的测试:is_business_hours()(9 点到 17 点返回 True)。一天 24 个整点里只有 8 个通过——同一个测试,几点跑结果不同,这就是「间歇失败」的来源。", fl=FL([0]),
         kv={'items': [['通过的整点', '9 10 11 12 13 14 15 16'], ['24 小时里', '8 小时通过 / 16 小时失败']], 'hl': ['24 小时里']}),
    step("patch('time.time') 只替换 time 模块里的属性:代码写成 time.time() 的地方生效了(1234.0);但代码里 from time import time as time_fn 拿走的那份引用没被替换,仍然是真实时间戳。", fl=FL([1], [0]),
         kv={'items': [['time.time()', '1234.0(被替换)'], ['shop.time_fn()', '≈ 1.79e9(仍是真实时间戳)']], 'hl': ['shop.time_fn()']}),
    step("要 patch「使用它的地方」:patch('shop.time_fn') 才生效。而 datetime.datetime.now 是内置类型的属性,直接 patch 报 TypeError: immutable type。", fl=FL([1], [0]),
         kv={'items': [["patch('shop.time_fn')", '1234.0(生效)'], ["patch('datetime.datetime.now')", "TypeError: cannot set 'now' attribute of immutable type"]], 'hl': ["patch('datetime.datetime.now')"]}),
    step("更好的办法:把「现在」当作参数传进去(now=None 默认取真实时间)。测试直接传 datetime(2026,9,29,10,0) 得 True、23:00 得 False,不需要任何 patch。", fl=FL([0], [1]),
         kv={'items': [['is_business_hours(10:00)', 'True'], ['is_business_hours(23:00)', 'False']], 'hl': ['is_business_hours(10:00)']}),
    step("随机数:seed(42) 两次得到同一串 [6,1,1,6,3,2];注入一个独立的 Random(7) 实例也可复现,并且完全不碰全局状态。", fl=FL([2], [0, 1]),
         kv={'items': [['seed(42) 两次', '[6, 1, 1, 6, 3, 2] 相同'], ['Random(7) 两个实例', '[3, 2, 4, 6, 1, 1] 相同']], 'hl': ['Random(7) 两个实例']}),
    step("依赖全局随机状态的测试有顺序耦合:test_b 没有设种子,却期望 seed(0) 之后的第二个值 98。顺序 a→b:2 passed;顺序 b→a:1 failed。", fl=FL([2], [0, 1]),
         kv={'items': [['a → b', '2 passed'], ['b → a', '1 failed, 1 passed']], 'hl': ['b → a']}),
    step("网络:连一个不会应答的地址(203.0.113.1,文档保留地址)。无保护:等到 0.60 s 超时(TimeoutError);加了「禁外网」fixture:0.0003 s 内立刻 RuntimeError;连本机回环地址仍然允许。", fl=FL([3], [0, 1, 2]),
         b={'items': [['无保护', 600, '0.60 s'], ['有保护', 0.3, '0.0003 s']], 'max': 600, 'cur': [1]}),
    step("sleep:一个带 2 次重试、每次等 0.5 s 的函数。真实 sleep 的测试 1.12 s;把 time.sleep 换成记录列表后 0.07 s,而且可以断言「睡了 [0.5, 0.5]」。", fl=FL([4], [0, 1, 2, 3]),
         b={'items': [['真实 sleep', 1120, '1.12 s'], ['patch 掉 sleep', 70, '0.07 s']], 'max': 1120, 'cur': [1]}),
]
A = dict(
    n=105,
    tags='Python,测试,pytest,mock,真实验证,动画演示',
    desc='本机真实验证:依赖真实时钟的测试在一天 24 个整点里只有 8 个通过;patch("time.time") 对 from time import time 拿走的引用无效、patch 内置类型 datetime.now 报 TypeError;把时钟当参数传入可免于 patch;共享全局 random 状态会造成 a→b 通过而 b→a 失败;禁外网 fixture 让不可达地址的连接由 0.60 s 超时变成 0.0003 s 立刻报错;patch 掉 sleep 让重试测试从 1.12 s 降到 0.07 s。',
    lead='测试最怕「不确定」:现在几点、随机数是多少、网络通不通。这三样不受你控制,测试就会间歇失败。这篇把三类问题各用一个真实实验讲清:怎么让时间、随机、网络变得可控,以及 <code>patch</code> 最容易踩的那个坑。',
    facts=[('8 / 24', '不控制时间的测试,一天 24 个整点里通过的个数'), ('0.60 s → 0.0003 s', '连接不可达地址:无保护(超时)与「禁外网」fixture 下的耗时'), ('1.12 s → 0.07 s', '带两次重试等待的测试:真实 sleep 与 patch 掉 sleep')],
    body=[
        sec('验证一:依赖「现在」的测试是不稳定的', '', src('shop.py', '''def is_business_hours():
    h = datetime.datetime.fromtimestamp(time.time()).hour
    return 9 <= h < 17'''), term('', block('== 一', '== 二')),
            '<p>这里为了统计,我用 <code>patch</code> 把时间依次设到 24 个整点。结论是:一个直接断言 <code>is_business_hours()</code> 为 True 的测试,只在 9 到 16 点之间通过,其余 16 个小时都会失败——CI 半夜跑就红了。</p>'),
        sec('验证二:patch 打在哪里', '', term('', block('== 二', '== 三')),
            '<p>这是最常见的 <code>patch</code> 陷阱:<code>patch("time.time")</code> 替换的是 <code>time</code> 模块里的名字,代码里写 <code>time.time()</code> 的地方会生效,但如果是 <code>from time import time as time_fn</code> 那样把名字拿到自己模块里,拿走的那份引用不会变,得 <code>patch("shop.time_fn")</code>——<b>要 patch「被使用的地方」,而不是「被定义的地方」</b>。另外 <code>datetime.datetime.now</code> 是内置类型上的属性,不能直接替换,会得到 <code>TypeError</code>(常见做法是 patch 整个 <code>datetime</code> 名字,或者用专门的库)。</p>'),
        sec('验证三:更好的办法——把时钟传进去', '', src('clock.py', '''def is_business_hours(now=None):
    now = now or datetime.datetime.now()
    return 9 <= now.hour < 17'''), term('', block('== 三', '== 四')),
            '<p>如果时间是函数的参数,测试就直接传一个固定时间——不需要 patch、不依赖真实时钟、不会有「打在哪里」的困扰。生产代码不传参数时走默认。这种「依赖注入」比 patch 更直接,代价是需要改接口。</p>'),
        sec('验证四:随机数——种子与独立实例', '', term('', block('== 四', '== 五')),
            '<p><code>random.seed(42)</code> 两次能复现同一串数;更稳妥的是给函数传一个独立的 <code>random.Random(种子)</code> 实例,它和全局状态互不干扰。全局状态的坏处在最后两行:<code>test_a</code> 设了种子并断言第一个值,<code>test_b</code> 没设种子,「碰巧」断言了第二个值。按 a→b 运行,两个都通过;按 b→a 运行,b 失败——它的结果取决于测试的执行顺序。这类 bug 在开启随机测试顺序或并行运行时才会暴露。</p>'),
        sec('验证五:禁止真实网络', '', src('conftest.py(节选)', '''@pytest.fixture
def no_network(monkeypatch):
    real = socket.socket.connect
    def guard(self, addr, *a, **k):
        host = addr[0] if isinstance(addr, tuple) else addr
        if host not in ("127.0.0.1", "::1", "localhost"):
            raise RuntimeError(f"测试里不允许访问外部网络: {addr}")
        return real(self, addr, *a, **k)
    monkeypatch.setattr(socket.socket, "connect", guard)'''), term('', block('== 五', '== 六')),
            '<p>用一个 fixture 替换 <code>socket.connect</code>:除回环地址外一律抛异常。实验里连的是 <code>203.0.113.1</code>(文档保留地址,不会有真实主机应答,不会对任何人发流量):没有保护时要等 0.60 s 才超时;有保护时 0.3 毫秒就报错,而且报错信息直接说明「测试里试图访问外网」——比一个莫名其妙的超时好排查得多,也让测试不再因为网络抖动而随机失败。</p>'),
        sec('验证六:别真的 sleep', '', term('', block('== 六', 'zzzz')),
            '<p>带重试的函数每次失败后 <code>time.sleep(delay)</code>。把 <code>time.sleep</code> 换成「往列表里记一下」的函数,测试从 1.12 s 降到 0.07 s,而且可以顺便断言「一共等了 [0.5, 0.5]」——既快又验证了重试的间隔逻辑。</p>'),
        sec('分步演示:让时间、随机、网络、sleep 都变得可控', '所有数字取自上面的真实实验',
            demo('测试的不确定性', [('fl', 'flow', '哪一类'), ('kv', 'kv', '观察'), ('b', 'bars', '耗时(ms)')], steps, '当前主题')),
    ],
    refs=['本机 macOS 27 / Python 3.14.7,pytest 9.1.1(临时虚拟环境),标准库 <code>unittest.mock</code>;网络实验只访问文档保留地址 203.0.113.1(不会有应答)和本机回环',
          '没有验证:freezegun / time-machine / pytest-socket 等专门的库、asyncio 的事件循环时钟(<code>loop.time</code>)、时区与夏令时相关的问题'],
)
