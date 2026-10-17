from lib import *
R = J('d13'); b = R['bad']
steps = [
    step("Django 启动分三个阶段:先 apps_ready(所有 app 的 AppConfig 创建好),再 models_ready(所有 models 模块导入完),最后 ready(所有 ready() 调用完)。在 lab/models.py 被导入的那一刻:apps_ready=True、models_ready=False、ready=False。", t=tl(['(lab/models.py 导入时) apps_ready=True models_ready=False ready=False'], cur=[0]), kv=KV([['models 导入时', 'apps_ready=True, models_ready=False']], ['models 导入时'])),
    step("在 LabConfig.ready() 里:apps_ready=True、models_ready=True、ready=False——所有模型都已加载,但整个注册表还没有宣布 ready(其它 app 的 ready() 可能还没跑)。setup() 结束后三个标志都是 True。", t=tl(['(LabConfig.ready() 里) apps_ready=True models_ready=True ready=False', '(setup() 结束后) apps_ready=True models_ready=True ready=True'], cur=[0, 1]), kv=KV([['ready() 里', 'models_ready=True, ready=False']], ['ready() 里'])),
    step("注册表内容:app_configs 的顺序就是 INSTALLED_APPS 的顺序(contenttypes, auth, lab, other);get_models() 按 app 顺序列出模型,共 6 个(ContentType、Permission、Group、User、Item、Thing);Item 的 app_label = lab。", n=fl([['contenttypes', ''], ['auth', ''], ['lab', 'Item'], ['other', 'Thing']], done=[0, 1, 2, 3]), kv=KV([['app 顺序', '= INSTALLED_APPS 顺序']], ['app 顺序'])),
    step("setup() 之前使用:apps.get_model → AppRegistryNotReady: Models aren't loaded yet;直接 import 一个模型模块 → AppRegistryNotReady: Apps aren't loaded yet。这就是「在模块顶层 import 模型」在 settings 或 apps.py 里会炸的原因。", n=fl([['setup() 之前 get_model', "Models aren't loaded yet"], ['setup() 之前 import 模型', "Apps aren't loaded yet"]], mark=[0, 1]), kv=KV([['报错类型', 'AppRegistryNotReady']], ['报错类型'])),
    step(f"配置错误的原文:同一个 app 写两次、或同时写 'lab' 和 'lab.apps.LabConfig'、或两个 app label 相同,全都是 {b['dup_name'].split(': ', 1)[1]};写了不存在的 app → {b['missing']};模型所在的包不在 INSTALLED_APPS → RuntimeError。", t=tl([b['dup_name'][-60:], b['dup_cfg'][-60:], b['dup_label'][-60:], b['missing'], b['stray'][:100]], mark=[0, 1, 2, 3, 4]), kv=KV([['重复', "Application labels aren't unique"]], ['重复'])),
    step(f"AppConfig 自动发现(不写 'lab.apps.LabConfig',只写 'lab'):apps.py 里有两个子类且 B 标了 default = True → 用 {R['auto1'].split()[0]};两个都没标 default → 用基类 {R['auto2']}(悄悄退回默认,你的子类不生效);没有 apps.py → 也是 {R['auto3']}。", n=fl([['两个子类,B default=True', R['auto1'].split()[0]], ['两个子类都没标', R['auto2'] + '(退回默认)'], ['没有 apps.py', R['auto3']]], done=[0], mark=[1]), kv=KV([['多个子类没标 default', '退回基类,不报错']], ['多个子类没标 default'])),
]
A = dict(
    n=13, series='django', tags='Django,App Registry,INSTALLED_APPS,真实验证,动画演示',
    desc='实测 Django 应用注册表:apps_ready / models_ready / ready 三个标志在 models 导入时与 ready() 里各是什么值;setup() 前使用会怎样;重复 label、不存在的 app 的报错原文;AppConfig 自动发现遇到多个子类且都没标 default 时会悄悄退回基类。',
    lead='INSTALLED_APPS 是怎么变成 apps 注册表的?为什么在 apps.py 或 settings 里 import 模型会炸?这篇把注册表的三个阶段、各种配置错误的报错原文,以及 AppConfig 自动发现的一个安静的坑,都用真实项目跑一遍。',
    facts=[('3 个标志', 'apps_ready → models_ready → ready:models 导入时只有 apps_ready,ready() 里 models_ready 为 True'), ('AppRegistryNotReady', 'setup() 之前 get_model 或 import 模型都会报这个错'), ('安静的坑', 'apps.py 里有多个 AppConfig 子类且都没标 default = True 时,退回基类 AppConfig,不报错')],
    body=[
        sec('三个阶段', '', term('', blk('d13', 1)), '<p>在 <code>lab/models.py</code> 与 <code>ready()</code> 里各打印一次三个标志。注册表按 INSTALLED_APPS 的顺序排列 app,<code>get_models()</code> 也按这个顺序返回。模型的 <code>app_label</code> 由它所在的 app 决定。</p>'),
        sec('setup() 之前使用注册表', '', term('', blk('d13', 2)), '<p>在 <code>settings.py</code>、<code>apps.py</code> 顶层、或脚本里没 <code>django.setup()</code> 就 import 模型,都会得到 <code>AppRegistryNotReady</code>。解决办法:把导入挪到函数里、或 <code>ready()</code> 里。</p>'),
        sec('配置错误的报错原文', '', term('', blk('d13', 3)), '<p>label 重复时 Django 会拒绝启动;写了不存在的 app 得到普通的 <code>ModuleNotFoundError</code>;模型所在的包没进 INSTALLED_APPS 时,导入这个模型会得到「doesn\'t declare an explicit app_label」。</p>'),
        sec('AppConfig 的自动发现', '', term('', blk('d13', 4)), '<p>只写 <code>\'lab\'</code> 时,Django 去 <code>lab/apps.py</code> 找 AppConfig 子类:只有一个就用它;有多个时看谁标了 <code>default = True</code>;<b>多个都没标</b>时,这次实测退回基类 <code>AppConfig</code> 且不报错——你在子类里写的 <code>ready()</code>、<code>verbose_name</code> 就悄悄失效了。写成 <code>\'lab.apps.LabConfig\'</code> 可以避免歧义。</p>'),
        sec('分步演示:注册表的状态', '', demo('App Registry', [('t', 'term', '标志'), ('n', 'flow', '注册表'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D, '没有验证:apps.py 存在但没有任何 AppConfig 子类时的行为、多 app 共享同一模块的情形、apps.populate 的线程安全(文档说明但本文未测)、swappable 模型(AUTH_USER_MODEL)在注册表里的延迟解析'],
)
