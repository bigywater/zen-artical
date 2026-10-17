from lib import *
R = J('d12')
steps = [
    step("from django.conf import settings 之后,proj.settings 还没有被导入,settings._wrapped 还是一个 object 占位(empty)。settings 是 LazySettings。", t=tl(['from django.conf import settings', "'proj.settings' in sys.modules → False", 'settings._wrapped 类型 → object(占位)'], cur=[1, 2]), kv=KV([['导入 settings', '不加载设置模块']], ['导入 settings'])),
    step("第一次读取 settings.DEBUG:此刻才按 DJANGO_SETTINGS_MODULE 导入 proj.settings,_wrapped 变成真正的 Settings 对象,settings.SETTINGS_MODULE = proj.settings。", t=tl(['读取 settings.DEBUG', "'proj.settings' in sys.modules → True", 'settings._wrapped 类型 → Settings', 'settings.SETTINGS_MODULE = proj.settings'], cur=[1, 2, 3]), kv=KV([['首次读取', '才导入设置模块']], ['首次读取'])),
    step(f"出错时的样子:没设环境变量 → ImproperlyConfigured: Requested setting DEBUG, but settings are not configured…;环境变量指向不存在的模块 → 直接是 {R['badmod']}。", n=fl([['没有 DJANGO_SETTINGS_MODULE', 'ImproperlyConfigured'], ['DJANGO_SETTINGS_MODULE=nope.settings', 'ModuleNotFoundError']], mark=[0, 1]), kv=KV([['两种错误', '不同的异常类型']], ['两种错误'])),
    step("只有全大写的名字算设置:settings.MY_UPPER = 2;小写的 my_lower 读取 → AttributeError,hasattr 为 False。没写的设置取 global_settings 里的默认值(本版本共 150 个大写默认项),例如 DEFAULT_CHARSET = utf-8。", t=tl(['settings.MY_UPPER = 2', 'settings.my_lower → AttributeError', 'global_settings 大写项 = 150', 'DEFAULT_CHARSET(没写,取默认) = utf-8'], cur=[0, 3], mark=[1]), kv=KV([['规则', '全大写才算设置']], ['规则'])),
    step("override_settings 内 settings.DEBUG 变成 False,退出后还原;但 proj.extra 在导入时就 STALE = settings.DEBUG 读了一次,它不会跟着变(True),而每次调用时才读的 fresh() 会变(False)。直接赋值 settings.DEBUG = False 则一直生效、不会还原。", n=fl([['override_settings(DEBUG=False)', 'settings.DEBUG = False'], ['模块级 STALE', '仍是 True'], ['函数里每次读 fresh()', 'False'], ['退出 with', '还原为 True']], mark=[1], done=[2, 3]), kv=KV([['导入时读 settings', '会得到「旧值」']], ['导入时读 settings'])),
    step("settings.configure() 只能调用一次:第二次 → RuntimeError: Settings already configured。INSTALLED_APPS 写成字符串 → ImproperlyConfigured: The INSTALLED_APPS setting must be a list or a tuple。", n=fl([['configure(DEBUG=True)', 'OK'], ['configure(DEBUG=False)', 'RuntimeError'], ["INSTALLED_APPS = '…'", 'ImproperlyConfigured']], done=[0], mark=[1, 2]), kv=KV([['configure', '只能一次']], ['configure'])),
]
A = dict(
    n=12, series='django', tags='Django,settings,配置,真实验证,动画演示',
    desc='实测 Django settings:import settings 时不加载、首次读取才导入;缺环境变量与写错模块名是两种不同的错误;只有全大写名字算设置(默认项 150 个);override_settings 对导入时读取过的值无效;configure() 只能调用一次。',
    lead='DJANGO_SETTINGS_MODULE 是怎么变成 settings.XXX 的?为什么在模块顶层写 X = settings.DEBUG 有时会「不跟着变」?这篇用一个真实项目,一条一条验证 settings 的惰性加载、大小写规则和覆盖行为。',
    facts=[('惰性', 'import settings 不导入设置模块,第一次读取属性才导入'), ('150', '本版本 global_settings 里全大写的默认设置个数'), ('模块级读取', 'override_settings 不会改变模块导入时已经读走的值')],
    body=[
        sec('惰性加载', '', term('', blk('d12', 1)), '<p><code>settings</code> 是 <code>LazySettings</code>:导入时里面只有占位,第一次属性访问才读环境变量、导入设置模块。所以可以先 <code>import</code> 再决定用哪个设置模块(比如在 <code>manage.py</code> 里先 <code>setdefault</code> 环境变量)。</p>'),
        sec('出错时的样子', '', term('', blk('d12', 2)), '<p>没配置和配错模块名是两种不同的异常,排查时看异常类型就能分清:前者是 <code>ImproperlyConfigured</code>,后者是普通的 <code>ModuleNotFoundError</code>。</p>'),
        sec('什么算设置、默认值从哪来', '', term('', blk('d12', 3)), '<p>只有全大写的名字会被读成设置(设置模块里的小写变量、类实例上的属性都不是)。没写的设置来自 <code>django.conf.global_settings</code>。<code>manage.py diffsettings</code> 只列出与默认值不同的项,输出里带 <code>###</code> 的是默认里不存在的自定义设置。</p>'),
        sec('运行时改设置', '', term('', blk('d12', 4)), '<p><code>override_settings</code> 是测试里的正规做法,退出时还原。要记住的陷阱:<b>在模块顶层读取设置</b>(<code>X = settings.DEBUG</code>)只读一次,之后的覆盖影响不到它——需要动态值时,在函数里读,或者用 <code>SimpleLazyObject</code> 之类延迟到使用时。直接赋值 <code>settings.DEBUG = False</code> 在进程内一直生效,不要在生产代码里这么做。</p>'),
        sec('configure() 与类型检查', '', term('', blk('d12', 5)), '<p>不依赖设置文件、在脚本里用 Django 时可以调用 <code>settings.configure(...)</code>,但只能调用一次。</p>'),
        sec('分步演示:settings 何时加载', '', demo('settings 加载', [('t', 'term', '观察'), ('n', 'flow', '过程'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。每个观察都在全新的子进程里做,避免互相污染', '没有验证:settings 模块里 import 其它设置模块(from .base import *)的常见分层写法的加载顺序、环境变量 DJANGO_SETTINGS_MODULE 在多进程服务器(gunicorn)里的传递、LazySettings 对线程的影响、settings 被 pickle 的情形'],
)
