from lib import *
R = J('d11'); ce = R['check_events']; qe = R['req_events']; sm = R['setup_ms']
def ev(L, keys): return [f"+{t:>6.1f} ms  {s}" for t, s in L if any(k in s for k in keys)]
smv = list(sm.values())
steps = [
    step("python manage.py check:进程刚起,还什么都没导入。manage.py 本身只做一件事——设置 DJANGO_SETTINGS_MODULE,然后调用 execute_from_command_line。", n=fl([['manage.py', 'setdefault DJANGO_SETTINGS_MODULE'], ['execute_from_command_line', '接管']], cur=[0]), kv=KV([['已导入的项目模块', '无']], ['已导入的项目模块'])),
    step(f"第一次读到设置(+{ce[0][0]:.1f} ms)才导入 proj/settings.py。settings 是惰性的:光 import 它不会加载(第 12 篇)。", t=tl([f"+{t:>6.1f} ms  {s}" for t, s in ce[:1]], cur=[0]), kv=KV([['第 1 个事件', ce[0][1]]], ['第 1 个事件'])),
    step(f"django.setup() → apps.populate 第一阶段:按 INSTALLED_APPS 导入每个 app 的模块并创建 AppConfig 实例。lab/apps.py 在 +{ce[1][0]:.1f} ms 被导入,LabConfig.__init__ 紧随其后。", t=tl([f"+{t:>6.1f} ms  {s}" for t, s in ce[:3]], cur=[1, 2]), kv=KV([['阶段 1', '导入 apps.py,创建 AppConfig']], ['阶段 1'])),
    step(f"第二阶段:导入每个 app 的 models(+{ce[3][0]:.1f} ms 导入 lab/models.py)——这一步在 setup() 里占的时间最长(从 +{ce[2][0]:.1f} 到 +{ce[3][0]:.1f} ms;耗时构成没有再拆开测)。", t=tl([f"+{t:>6.1f} ms  {s}" for t, s in ce[:4]], cur=[3]), b=bars([['导入 apps.py 之后 → models 导入完成(ms)', ce[3][0] - ce[2][0], f"{ce[3][0] - ce[2][0]:.1f}"], ['settings → apps.py(ms)', ce[1][0] - ce[0][0], f"{ce[1][0] - ce[0][0]:.1f}"]], max(ce[3][0] - ce[2][0], ce[1][0]) * 1.1, mark=[0]), kv=KV([['阶段 2', '导入所有 models']], ['阶段 2'])),
    step(f"第三阶段:所有模型都加载完,依次调用每个 AppConfig.ready()(+{ce[4][0]:.1f} ms)。ready() 里可以放心引用任何 app 的模型(第 13、14 篇)。", t=tl([f"+{t:>6.1f} ms  {s}" for t, s in ce[:5]], cur=[4]), kv=KV([['阶段 3', 'ready()']], ['阶段 3'])),
    step(f"urls、views、中间件模块不在 setup() 里导入。check 命令是因为系统检查才去导入它们(+{ce[5][0]:.1f} ms urls、+{ce[6][0]:.1f} ms views、+{ce[7][0]:.1f} ms mw);处理请求时则是第一个请求才导入:urls / views / 中间件都出现在「发出第 1 个请求」之后,第 2 个请求不再导入。", t=tl([f"+{t:>6.1f} ms  {s}" for t, s in qe[5:]][:12], cur=[1, 2, 3, 4, 5]), kv=KV([['urls / views / 中间件', '按需导入(首个请求或系统检查时)']], ['urls / views / 中间件'])),
    step(f"django.setup() 的耗时随 INSTALLED_APPS 增加只是缓慢增长:{list(sm)[0]} {smv[0]:.0f} ms;四个 contrib app {smv[1]:.0f} ms;再加 admin 与 staticfiles {smv[2]:.0f} ms(每种 5 次取中位数)。", b=bars([[k, v, f"{v:.0f} ms"] for k, v in sm.items()], max(smv) * 1.1, done=[0, 1], mark=[2]), kv=KV([['结论', '启动耗时主要是导入 Django 自己']], ['结论'])),
]
A = dict(
    n=11, series='django', tags='Django,启动流程,AppConfig,真实验证,动画演示',
    desc=f'在一个带打点的真实 Django 项目里,按时间顺序记录 manage.py check 与一次请求中各模块被导入、被调用的次序:settings → apps.py → models → ready() → urls / views / 中间件;并量了 django.setup() 的耗时({smv[0]:.0f}→{smv[2]:.0f} ms)。',
    lead='manage.py 敲下回车之后,Django 到底按什么顺序把 settings、apps、models、urls 一个个拉起来?这篇在项目的每个入口都加了打点,不靠记忆里的源码顺序,直接看时间戳。',
    facts=[(f'+{ce[4][0]:.0f} ms', 'manage.py check 里 ready() 被调用的时刻(从第一次读 settings 起算)'), ('按需', 'urls / views / 中间件不在 setup() 里导入,首个请求(或系统检查)才导入'), (f'{smv[0]:.0f}→{smv[2]:.0f} ms', 'django.setup() 中位耗时:1 个 app → 加上 admin、staticfiles(本机)')],
    body=[
        sec('manage.py check 的时间线', '', term('', blk('d11', 1)), '<p>每个模块顶部都写了一行打点,记录被导入的时刻;<code>AppConfig.__init__</code> 与 <code>ready()</code> 里同样打点。settings 是第一个出现的——它在第一次读取设置时才导入。接着 <code>django.setup()</code> 里按次序发生:导入 <code>apps.py</code>、创建 <code>AppConfig</code> 实例、导入 <code>models</code>、调用 <code>ready()</code>。urls、views、中间件模块在这条命令里晚一点才被导入(系统检查用到了它们)。</p>'),
        sec('处理一次请求时的顺序', '', term('', blk('d11', 2)), '<p>用 <code>django.test.Client</code> 在同一个进程里发两个请求。<code>setup()</code> 结束之后什么也没导入;<b>第一个请求</b>才导入中间件、<code>ROOT_URLCONF</code>、视图模块,并构建中间件链(<code>MW.__init__</code>);第二个请求只走 <code>__call__</code> 和视图。所以「第一个请求比后面慢」的一部分就是这些模块的导入(用测试客户端量的,不等于真实服务器的首请求耗时)。</p>'),
        sec('setup() 有多贵', '', term('', blk('d11', 3)), '<p>三种 INSTALLED_APPS 规模各在全新进程里 <code>django.setup()</code> 五次取中位数:数字随 app 增加缓慢增长。这个数字包含了导入 Django 自身模块的时间(<code>manage.py</code> 每个命令都要付一次),所以命令行工具启动慢主要是它。</p>'),
        sec('分步演示:启动的三个阶段', '', demo('Django 启动过程', [('n', 'flow', '入口'), ('t', 'term', '带打点的事件'), ('b', 'bars', '耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。事件时间取自项目里每个模块顶部写入日志文件的 perf_counter 时间戳(相对第一条事件)', '没有验证:django.setup() 内部各函数(configure_logging、set_script_prefix)的耗时占比、runserver 与 gunicorn 下的首请求耗时、Python 字节码缓存(.pyc)冷热对启动时间的影响、不同 Python 版本之间的差别'],
)
