from lib import *
R = J('d26'); ids = R['deploy_ids']
steps = [
    step("没有问题时 python manage.py check:System check identified no issues (0 silenced).,退出码 0。", t=tl([R['ok'][1], 'rc = %d' % R['ok'][0]], cur=[0]), kv=KV([['无问题', 'rc = 0']], ['无问题'])),
    step(f"注册一个返回 Error 的自定义检查(lab.E001):check 失败(rc={R['err'][0]}),输出 SystemCheckError,带 HINT;migrate 与 runserver 也在启动前被拦下(rc={R['err_migrate'][0]} / {R['err_run'][0]}),不会真正执行。", t=tl(R['err'][1].splitlines()[:7], cur=[2, 3], mark=[0]), kv=KV([['Error', '阻止 runserver / migrate / test 等']], ['Error'])),
    step(f"返回 Warning(lab.W001)时:check 仍然 rc={R['warn'][0]},只提示;加 --fail-level WARNING 后 rc={R['warn_fail']}。--tag lab_tag 只运行带这个标签的检查;--tag models 不含它,不出现该警告。", t=tl(R['warn'][1].splitlines(), cur=[2, 3]), n=fl([['check', 'rc=0(只提示)'], ['check --fail-level WARNING', 'rc=1'], ['check --tag models', '不含 lab_tag,无提示']], done=[0, 2], mark=[1]), kv=KV([['Warning', '默认不阻止']], ['Warning'])),
    step("SILENCED_SYSTEM_CHECKS = ['lab.W001'] 把这条检查静音:输出变成 System check identified no issues (1 silenced).。", t=tl([R['silenced']], cur=[0]), kv=KV([['静音', '按检查 id']], ['静音'])),
    step(f"check --deploy 对这个开发向的设置报出 {len(ids)} 个问题:{', '.join(ids)}(rc 仍是 0,因为它们是 Warning)。--deploy 是给上线前用的一组额外检查(第 121–129 篇会展开安全相关的几项)。", t=tl([f'security 检查 id: {i}' for i in ids] + [R['deploy_last']], mark=list(range(len(ids)))), kv=KV([['--deploy', f'{len(ids)} 个警告']], ['--deploy'])),
    step("哪些命令会先跑检查:LAB_ERR=1(自定义 Error 打开)时,check、migrate、showmigrations、makemigrations、test 都被拦下(rc=1);help 与 shell -c 不受影响(rc=0)。", t=tl([f"manage.py {k:<32} rc={v}" for k, v in R['auto'].items()], mark=[i for i, v in enumerate(R['auto'].values()) if v == 1], done=[i for i, v in enumerate(R['auto'].values()) if v == 0]), kv=KV([['被拦', 'check / migrate / makemigrations / test / showmigrations'], ['不拦', 'help / shell']], ['被拦'])),
]
A = dict(
    n=26, series='django', tags='Django,系统检查,check,真实验证,动画演示',
    desc=f'用自定义检查实测 Django 系统检查框架:Error 会阻止 check / migrate / runserver / test 等命令,Warning 默认只提示(--fail-level 可升级为失败);--tag 选择检查、SILENCED_SYSTEM_CHECKS 静音、check --deploy 在开发设置下报出 {len(ids)} 个警告。',
    lead='每次 runserver 或 migrate 前面那句 “System check identified no issues” 是什么?你能往里加自己的检查吗?Error 和 Warning 差在哪?这篇写三个自定义检查,在真实项目里把它们的作用范围逐个验证。',
    facts=[('Error 拦下', '自定义 Error 让 check / migrate / makemigrations / test / runserver 都无法执行'), ('Warning 不拦', 'check 仍然 rc=0;--fail-level WARNING 才让它失败'), (f'{len(ids)} 个', 'check --deploy 对开发向设置报出的警告数')],
    body=[
        sec('无问题与自定义 Error', '', term('', blk('d26', 1)), term('', blk('d26', 2)), '<p>用 <code>@register(Tags.models)</code> 装饰一个返回 <code>Error</code> 列表的函数即可加入检查;检查在 <code>AppConfig.ready()</code> 里导入(这样才会注册)。</p>'),
        sec('Warning、标签与静音', '', term('', blk('d26', 3)), term('', blk('d26', 4)), '<p>标签(<code>Tags.models</code> 或自定义字符串)决定 <code>--tag</code> 能选到它。已知且接受的警告用 <code>SILENCED_SYSTEM_CHECKS</code> 静音。</p>'),
        sec('--deploy', '', term('', blk('d26', 5)), '<p><code>register(..., deploy=True)</code> 的检查只在 <code>--deploy</code> 时运行。上线前把它加进 CI。</p>'),
        sec('哪些命令会检查', '', term('', blk('d26', 6)), '<p>需要数据库或依赖完整配置的命令会先检查;<code>help</code>、<code>shell -c</code> 不会。</p>'),
        sec('分步演示:检查框架', '', demo('系统检查框架', [('t', 'term', '输出'), ('n', 'flow', '命令'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。自定义检查靠环境变量 LAB_ERR / LAB_WARN 开关', '没有验证:数据库相关检查(Tags.database)在 migrate 之外何时运行、check 对多数据库的 --database 选项、Django 自带检查的完整清单、fail-level 取 ERROR / CRITICAL 时的差别'],
)
