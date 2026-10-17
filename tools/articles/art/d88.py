from lib import *
R = J('d88')
sp = lambda s: s.split(', ', 0)[0]
steps = [
    step("collectstatic 收集三处来源:STATICFILES_DIRS(项目的 assets/)与各 app 的 static/。本例收集 6 个文件到 STATIC_ROOT,另有 2 个因冲突被跳过(shared.txt 在 app1、app2 里各有一份,加上 assets 里的一份,只保留一份)。同名文件谁赢:STATICFILES_DIRS 里的先(内容是 FROM PROJECT assets),其次按 INSTALLED_APPS 顺序;findstatic -v2 列出所有候选位置及顺序:assets、app1、app2。", t=tl(['收集结果:' + R['first'].replace('/private/tmp/claude-501/-Users-w-Desktop-resume-bigywater/ba230915-496f-4157-87cf-8cee4040b1b9/scratchpad/py40/djtmp/', ''), '收集到的文件:' + ', '.join(R['files']), 'shared.txt 的内容:FROM PROJECT assets'] + [l.strip().split('djtmp/')[-1] for l in R['find'].splitlines()[:4]]), cur=[2], kv=KV([['同名文件', 'STATICFILES_DIRS > app 顺序']], ['同名文件'])),
    step(f"增量收集:无变化时再运行 → {R['second']};改了源文件但和上次复制在同一秒内立刻运行 → 仍是「{R['third_fast']['line']}」,目标里还是旧内容({R['third_fast']['content']});等 1.2 秒后再改再运行 → 1 个被复制(目标内容 {R['third']['content']})。collectstatic 比较修改时间且忽略亚秒精度;内容变了但 mtime 没变(用 utime 还原)也会被漏掉。", t=tl([R['second'], '同一秒内改完立刻运行:' + R['third_fast']['line'] + ' 目标内容=' + R['third_fast']['content'], '等 1.2 秒后:' + R['third']['line'] + ' 目标内容=' + R['third']['content'], 'mtime 没变:' + R['mtime']['line'] + ' 目标内容=' + R['mtime']['content']], mark=[1, 3], done=[2]), kv=KV([['判断依据', '修改时间(秒级)']], ['判断依据'])),
    step(f"清理:源里已删除的文件,目标里的旧文件不会自动消失(stale.txt 在,{R['stale_kept']});--clear 先清空再复制({R['clear']['line'].split(', ')[0]});--dry-run 只演示不落盘;--link 创建符号链接而不是复制(site.css 是符号链接:{R['link']['symlink']});-i \"*.js\" 忽略指定模式(收集结果里没有 .js)。", t=tl(['不带 --clear:stale.txt 还在 = ' + str(R['stale_kept']), '--clear:' + R['clear']['line'].split("'")[0].strip(), '--link:' + R['link']['line'].split("'")[0].strip(), '-i \"*.js\":' + R['ignore'].split("'")[0].strip()]), kv=KV([['--clear', '清掉目标里的旧文件'], ['--link', '开发用,生产不推荐']], ['--clear'])),
    step("没有设置 STATIC_ROOT 就运行 collectstatic:ImproperlyConfigured: You're using the staticfiles app without having set the STATIC_ROOT setting to a filesystem path。", t=tl([R['noroot']], mark=[0]), kv=KV([['STATIC_ROOT', 'collectstatic 的必需设置']], ['STATIC_ROOT'])),
]
A = dict(
    n=88, series='django', tags='Django,静态文件,collectstatic,真实验证,动画演示',
    desc='实测 collectstatic:从 STATICFILES_DIRS 与各 app 的 static 收集,同名文件 STATICFILES_DIRS 优先再按 INSTALLED_APPS 顺序;增量复制比较修改时间且忽略亚秒精度(同一秒内改的文件会被漏掉);旧文件不自动删除,--clear / --dry-run / --link / -i 的行为;缺 STATIC_ROOT 报错。',
    lead='collectstatic 从哪里收集?同名文件怎么选?再次运行会重新复制吗?这篇建两个 app 加一个项目 assets 目录,把这些行为逐个试出来,顺便发现「同一秒内改的文件会被漏掉」这个细节。',
    facts=[('STATICFILES_DIRS 优先', '同名文件:STATICFILES_DIRS 里的先于 app 的 static/,app 之间按 INSTALLED_APPS 顺序'), ('秒级', '增量比较修改时间并忽略亚秒精度:同一秒内改完再收集会被判为未修改'), ('不自动删除', '源里删掉的文件,目标(STATIC_ROOT)里的旧副本仍在,除非 --clear')],
    body=[
        sec('收集与同名冲突', '', term('', blk('d88', 1)), '<p>用 <code>findstatic 文件名 -v2</code> 可以查「某个静态文件到底来自哪里、还有哪些被遮蔽」。</p>'),
        sec('增量收集', '', term('', blk('d88', 2)), '<p>这个「同一秒内」的现象,我是在写脚本时无意中踩到的:改完文件立刻 collectstatic,发现没更新。真实部署里两次 collectstatic 通常隔得很久,但自动化测试脚本里会碰到。</p>'),
        sec('清理与选项', '', term('', blk('d88', 3)), '<p>部署脚本一般用 <code>collectstatic --noinput --clear</code>,避免旧文件累积(配合哈希文件名时,旧版本文件是否要保留给还在使用旧页面的客户端,是另一个取舍,第 89 篇)。</p>'),
        sec('必需设置', '', term('', blk('d88', 4)), '<p>开发时(<code>runserver</code>、DEBUG=True)静态文件直接从源目录提供,不需要 collectstatic。</p>'),
        sec('分步演示:collectstatic', '', demo('collectstatic', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite 无关;静态文件由两个 app 与项目 assets 提供', '没有验证:远程存储(S3)后端的 collectstatic、--no-post-process、大量文件下的耗时、跨文件系统的 mtime 精度差异'],
)
