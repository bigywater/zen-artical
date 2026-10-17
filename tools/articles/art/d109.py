from lib import *
R = J('d109')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("默认 weak=True,connect 一个在函数里定义的局部函数,函数返回并 gc.collect() 之后 send:局部函数仍然被调用了(LOG=['local called'])。按弱引用的字面意思它应该已被回收,这里却没有。", t=tl(L('local')), mark=[0], kv=KV([['预期', '被回收,信号无人接收'], ['实测', '仍被调用']], ['实测'])),
    step("原因(读源码 + 实测):django/utils/inspect.py 里 _get_func_parameters 有 functools.lru_cache(maxsize=512),connect 时检查签名会把函数放进这个缓存,缓存强引用了它。实测:再 connect 600 个别的函数把缓存(currsize 512)挤满之后,那个局部函数被挤出、回收,send 返回空列表,receivers 变为 0。", t=tl(L('cache')), mark=[0], done=[2], kv=KV([['强引用来源', 'lru_cache(maxsize=512)'], ['被挤出之后', '才会被回收']], ['强引用来源'])),
    step("lambda、functools.partial、模块级函数,在 gc.collect() 之后 send:三个都被调用了(['lambda', 'partial', 'module-level'])。同样是在缓存里、还没被挤出。", t=tl(L('lambda')), kv=KV([['结论', '弱引用的局部对象什么时候消失不确定']], ['结论'])),
    step("绑定方法不同:Django 用 WeakMethod 弱引用对象本身。hnd.on connect 之后,对象存在时 n=1、receivers=1;del hnd + gc.collect() 后 send 返回 [],receivers=0——对象销毁 receiver 就自动消失,不用 disconnect。", t=tl(L('method')), done=[1], kv=KV([['bound method', '对象没了,receiver 也没了']], ['bound method'])),
    step("weak 决定 receiver 会不会「拖住」对象:connect(h.on, weak=True) 后 del h,对象被回收(True);weak=False 时对象没被回收(False)——信号持有了强引用,对象会一直活着,是潜在的内存泄漏。", t=tl(L('leak')), mark=[1], kv=KV([['weak=False', '信号持有强引用,对象不会被回收']], ['weak=False'])),
]
A = dict(
    n=109, series='django', tags='Django,Signal,weakref,内存,真实验证,动画演示',
    desc='Signal 默认对 receiver 用弱引用,但实测局部函数、lambda、partial 在函数返回并 gc 之后仍被调用——因为 connect 时的签名缓存 lru_cache(512) 强引用了它们,挤满缓存后才被回收;绑定方法则随对象销毁自动消失;weak=False 会拖住对象。',
    lead='connect 的 weak 参数默认是 True:信号只弱引用 receiver。常见的说法是「局部函数当 receiver 会被回收」。这篇按这个说法去试,结果和预期不一样,顺着查下去找到了原因。',
    facts=[('局部函数没被回收', 'weak=True 下,gc.collect() 之后仍被调用(Django 6.1.1)'), ('lru_cache(512)', '签名缓存强引用了 connect 过的函数,挤满后才释放'), ('weak=False', '信号持有对象的强引用,对象不会被回收')],
    body=[
        sec('局部函数会不会被回收', '', term('', blk('d109', 1)), '<p>这和我一开始的预期相反,所以我没有直接下结论,而是接着查原因。</p>'),
        sec('原因:签名缓存', '', term('', blk('d109', 2)), '<p>读 Django 源码:<code>django/utils/inspect.py</code> 里的 <code>_get_func_parameters</code> 被 <code>functools.lru_cache(maxsize=512)</code> 装饰,<code>connect</code> 检查 receiver 签名时会调用它,缓存把函数对象强引用住了。实测把缓存挤满(600 个别的函数)后,那个局部函数才被回收。也就是说 weak=True 的局部 receiver「什么时候消失」取决于缓存里还有多少别的函数——行为不确定,<b>不要依赖它</b>。这一点本文只在 Django 6.1.1 + Python 3.14 上验证,别的版本没有测。</p>'),
        sec('lambda / partial / 模块级函数', '', term('', blk('d109', 3))),
        sec('绑定方法', '', term('', blk('d109', 4)), '<p>绑定方法用 <code>WeakMethod</code>:缓存里放的是底层函数,不是实例,所以实例本身可以被回收。</p>'),
        sec('weak=False 的代价', '', term('', blk('d109', 5)), '<p>弱引用的好处:receiver 是对象的方法时,对象不用再手动 disconnect。<code>weak=False</code> 让信号强引用,适合局部函数或 lambda(不然行为不确定),但持有的对象就不会释放。</p>'),
        sec('分步演示', '', demo('Signal 的弱引用', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。自建 Signal;Python 3.14 的 gc.collect();缓存的信息来自 django/utils/inspect.py(读源码)和 cache_info() 的实测', '没有验证:Django 其它版本 / Python 其它版本上同样的缓存行为、connect 之外的强引用来源、多线程下的回收时机'],
)
