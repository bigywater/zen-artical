from lib import *
R = J('d105')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("同一个函数对象 connect 两次,save 一次只触发 1 次。但换成「工厂函数造出的、代码相同的两个新函数」,每个都是新的函数对象,各算一个 receiver——加上原来的 h,一次 save 触发 3 次。", t=tl(L('identity')), mark=[1], kv=KV([['去重依据', '函数对象的身份,不是代码']], ['去重依据'])),
    step("经典原因:同一个 .py 文件被两个不同的模块名导入(实验里用 spec_from_file_location 模拟 handlers_again),模块代码执行了两遍,@receiver 装饰出两个函数对象:receiver 数从 1 变成 2,保存一次两份 COUNT 各加 1。", t=tl(L('twice')), mark=[1, 2], kv=KV([['重复导入', '两个函数对象 → 触发两次']], ['重复导入'])),
    step("解法:给 @receiver 传 dispatch_uid。同一段代码执行 3 次(每次是新的模块字典、新的函数对象),因为 uid 相同,保存一次只触发 1 次。", t=tl(L('uid')), done=[0], kv=KV([['dispatch_uid', '同 uid 只保留一个']], ['dispatch_uid'])),
    step("在 ready() 之类会重复执行的地方 connect lambda 或局部函数:连续执行 3 次,receiver 增加 3 个,因为每个 lambda 都是新对象。要么用模块级函数,要么加 dispatch_uid。", t=tl(L('ready')), mark=[0], kv=KV([['lambda / 局部函数', '每次都是新 receiver']], ['lambda / 局部函数'])),
]
A = dict(
    n=105, series='django', tags='Django,Signal,重复注册,dispatch_uid,真实验证,动画演示',
    desc='Signal 去重靠的是函数对象的身份:同一个函数 connect 两次只算一个,但工厂函数造的相同代码、被不同模块名导入两次的 @receiver、每次新建的 lambda 都会重复触发;dispatch_uid 让它们只留一个。',
    lead='「保存一次,信号触发两次」是 Django 里常见的坑。这篇不去猜,直接复现能让它发生的几种情形,再用 dispatch_uid 解决。',
    facts=[('函数身份', 'connect 去重按函数对象(或 dispatch_uid),不按代码内容'), ('同文件两个模块名', '导入两次 → @receiver 注册两次'), ('dispatch_uid', '相同 uid 只保留一个 receiver')],
    body=[
        sec('去重的依据', '', term('', blk('d105', 1))),
        sec('同一个文件被导入两次', '', term('', blk('d105', 2)), '<p>实验里用 <code>spec_from_file_location</code> 加载同一个文件、模块名不同来模拟。至于真实项目里是哪种导入路径不一致造成的,本文没有复现,只模拟了「同一文件、两个模块名」。</p>'),
        sec('用 dispatch_uid', '', term('', blk('d105', 3))),
        sec('lambda 与局部函数', '', term('', blk('d105', 4)), '<p>只要 connect 的调用会执行多次(测试里的 setUp、被重复调用的 <code>ready()</code>),传入的又是每次都新建的函数,receiver 就会累加。</p>'),
        sec('分步演示', '', demo('重复注册', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite', '没有验证:runserver 自动重载的两个进程、INSTALLED_APPS 里同时写 app 和 AppConfig 路径是否导致重复(Django 有检查会直接报错,本文没有测)、测试里的重复连接'],
)
