from lib import *
R = J('d82'); ch = R['cache']
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("三处都有 shared.html:项目 templates/ 目录(DIRS)、app1/templates/、app2/templates/。render_to_string('shared.html') 得到「shared FROM project templates dir」——DIRS(filesystem 加载器)优先;两个 app 里的(app_directories 加载器)其次。只在某个 app 里的 only1.html、only2.html 都能找到。", t=tl([l.split('/djtmp/')[-1] if '/djtmp/' in l else l for l in L('order')][:6]), kv=KV([['DIRS', '优先'], ['app 模板', '其次']], ['DIRS'])),
    step(f"DIRS 为空时看 INSTALLED_APPS 顺序:[app1, app2] → {R['forward'].split('→')[-1].strip()};[app2, app1] → {R['reverse'].split('→')[-1].strip()}。前面的 app 覆盖后面的同名模板——这也是覆盖第三方 app(比如 admin)模板的办法:把自己的 app 排在它前面,或放进项目 DIRS。", t=tl([R['forward'], R['reverse']], cur=[0, 1]), kv=KV([['同名模板', '先列出的 app 赢']], ['同名模板'])),
    step("找不到模板:TemplateDoesNotExist: missing.html,异常的 chain 里带着尝试记录:依次尝试了 templates/missing.html(DIRS)、app1/templates/missing.html、app2/templates/missing.html,每一处都是 Source does not exist——这就是调试页 Template-loader postmortem 的来源。select_template(['nope1.html', 'only1.html']) 选到第一个存在的 only1.html。", t=tl(L('missing')), kv=KV([['排查', '看 tried 列表']], ['排查'])),
    step(f"cached 加载器:第一次 get_template 编译模板 {ch['cached loader']['first']:.2f} ms,之后每次只要 {ch['cached loader']['median']:.4f} ms(缓存命中);没有 cached 时每次都重新读盘、编译,{ch['没有 cached']['median']:.2f} ms。未显式设置 loaders 时,DEBUG=True 与 DEBUG=False 用的都是 cached.Loader(Django 6.1.1 实测)。", b=bars([['cached 之后每次(ms)', ch['cached loader']['median'], f"{ch['cached loader']['median']:.4f}"], ['无 cached 每次(ms)', ch['没有 cached']['median'], f"{ch['没有 cached']['median']:.2f}"]], ch['没有 cached']['median'] * 1.1, done=[0], mark=[1]), kv=KV([['cached', f"{ch['cached loader']['median']:.4f} ms / 次"], ['无 cached', f"{ch['没有 cached']['median']:.2f} ms / 次"]], ['cached'])),
]
A = dict(
    n=82, series='django', tags='Django,模板,Template Loader,真实验证,动画演示',
    desc=f'实测 Django 模板加载器:同名模板时 DIRS 优先、再按 INSTALLED_APPS 顺序;TemplateDoesNotExist 的 tried 列表列出所有尝试位置;cached 加载器让每次 get_template 从 {ch["没有 cached"]["median"]:.2f} ms 降到 {ch["cached loader"]["median"]:.4f} ms,且 DEBUG 开关不影响默认使用 cached。',
    lead='同名模板出现在多个地方时谁赢?怎么覆盖 admin 的模板?找不到模板时怎么排查?cached 加载器到底省多少?这篇建两个 app 加一个项目模板目录,把这几件事都试一遍。',
    facts=[('DIRS 优先', '项目 DIRS 里的模板优先于 app 里的同名模板,app 之间按 INSTALLED_APPS 顺序'), ('tried', 'TemplateDoesNotExist 带着尝试过的每个路径,调试时直接看'), (f'{ch["没有 cached"]["median"]:.2f} → {ch["cached loader"]["median"]:.4f} ms', '没有 cached vs 有 cached 加载器,get_template 每次的耗时(本机)')],
    body=[
        sec('谁赢', '', term('', blk('d82', 1)), '<p>加载器按 <code>TEMPLATES[0][\'OPTIONS\'][\'loaders\']</code> 的顺序尝试(默认:先 filesystem 再 app_directories,外面包一层 cached)。</p>'),
        sec('INSTALLED_APPS 的顺序', '', term('', blk('d82', 2)), '<p>同名模板的冲突是 Django 里最常见的「莫名其妙」之一,报错里的 <code>tried</code> 列表告诉你每个位置的状态。</p>'),
        sec('missing 与 select_template', '', term('', blk('d82', 3)), '<p>注意这里能看到的是引擎的 <code>chain</code>,而不是直接挂在最外层异常上的 <code>tried</code>(外层的是空的)。</p>'),
        sec('cached 加载器', '', term('', blk('d82', 4)), '<p>cached 加载器把编译后的模板放在进程内存里。开发时改模板会自动重置缓存(第 25 篇)。没有 cached 的对照组每次 <code>get_template</code> 要读文件并编译。</p>'),
        sec('分步演示:模板加载', '', demo('模板加载器', [('t', 'term', '输出'), ('b', 'bars', '耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。三个候选位置由 get_template_sources 列出;耗时为 300 次中位数,模板是循环 40 组的合成模板', '没有验证:多个 TEMPLATES 引擎(Jinja2)并存、加载器的 Origin 与 skip_template 机制、模板热重载在大项目里的开销、cached 加载器缓存的失效边界'],
)
