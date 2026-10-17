from lib import *
R = J('d89'); m = R['manifest']
steps = [
    step("ManifestStaticFilesStorage 在 collectstatic 时给每个文件按内容哈希(MD5 前 12 位)加一个副本:css/site.css → css/site.8ba4b5966a42.css 等 5 个,原名文件也保留;并写出 staticfiles.json(键:paths、version、hash),paths 就是「原名 → 带哈希的名字」的映射。", t=tl([f"{k} → {v}" for k, v in m.items()], cur=[0, 1, 2, 3, 4]), kv=KV([['哈希', '内容 MD5 前 12 位'], ['映射表', 'staticfiles.json']], ['映射表'])),
    step("post_process 会改写 CSS 里的引用:@import url('base.css') → url(\"base.7411b9041dad.css\");url('../img/logo.png') → url(\"../img/logo.79b11419e142.png\");带查询串和锚点的 ../img/bg.png?v=1#x 也保留后缀并改写;外部 URL(https://cdn…)与 data: URI 保持原样。被引用的文件先哈希,引用它的 CSS 再哈希——所以 CSS 的哈希取决于它引用的文件。", t=tl(R['css'].replace('; ', ';\n').split('\n') if False else [R['css'][:110], R['css'][110:230], R['css'][230:]]), kv=KV([['CSS 里的 url()', '被改写成带哈希的名字'], ['外部 / data:', '原样']], ['CSS 里的 url()'])),
    step(f"哈希是内容的函数:app.js 内容的 md5[:12] = 5c4e6521f9b0,与 manifest 里的文件名一致({R['md5_match']});内容没变再收集一次,映射不变;把内容改成 console.log(\"app v2\") 后名字变成 {R['change'][1]}(原来 {R['change'][0]})。浏览器对新名字没有缓存,对未变的文件继续用缓存——这就是缓存失效的机制。旧的哈希文件仍在目录里({R['old_kept']}),不会自动删除。", t=tl([f"内容 md5[:12] = 5c4e6521f9b0,manifest 文件名一致 = {R['md5_match']}", f"改内容后:{R['change'][0]} → {R['change'][1]}", f"旧的哈希文件还在目录里:{R['old_kept']}"], cur=[0, 1], mark=[2]), kv=KV([['内容变 → 名字变', '缓存自动失效'], ['旧文件', '不自动删']], ['内容变 → 名字变'])),
    step("{% static %} 在 DEBUG=False 下输出哈希名(<a href=\"/static/css/site.8ba4b5966a42.css\">);清单里没有的文件 → ValueError: Missing staticfiles manifest entry for 'img/missing.png'——模板里引用了一个 collectstatic 没收集到的文件,页面直接 500。", t=tl(R['tag'].splitlines()), mark=[0], done=[1], kv=KV([['清单缺项', '页面 500'], ['所以', '上线前跑 collectstatic 并检查模板引用']], ['清单缺项'])),
    step("manifest_strict = False(通过子类设置):文件在磁盘上但不在清单里时,现算一个哈希名返回(/static/img/late.7f02e16a4a58.png);文件根本不存在仍抛 ValueError: The file 'img/missing.png' could not be found。严格模式(默认)下,磁盘上有但不在清单里的文件同样 ValueError: Missing staticfiles manifest entry。", t=tl(R['nonstrict'].splitlines() + R['strict_late'].splitlines()), kv=KV([['非严格', '只对「磁盘上存在」的文件放行']], ['非严格'])),
]
A = dict(
    n=89, series='django', tags='Django,静态文件,ManifestStaticFilesStorage,缓存,真实验证,动画演示',
    desc='实测 ManifestStaticFilesStorage:文件名加内容 MD5 前 12 位、staticfiles.json 映射;CSS 里的 url() 与 @import 被改写,外部 URL 与 data: 保持不变;内容变名字变(缓存失效);DEBUG=False 时清单缺项直接 ValueError;manifest_strict = False 的边界。',
    lead='静态文件名里那串哈希是怎么来的?CSS 里引用的图片怎么跟着变?模板引用了没收集的文件会怎样?这篇跑一遍 collectstatic + ManifestStaticFilesStorage,把每个环节的产物都展示出来。',
    facts=[('12 位', '文件名里的哈希是内容 MD5 的前 12 位;内容不变名字不变'), ('url() 被改写', 'CSS 里的 url() / @import 被改写成带哈希的名字;外部 URL 与 data: 不动'), ('ValueError', 'DEBUG=False 时 {% static %} 引用清单里没有的文件,直接抛 Missing staticfiles manifest entry')],
    body=[
        sec('文件名与映射表', '', term('', blk('d89', 1)), '<p>模板里 <code>{% static "css/site.css" %}</code> 在生产环境(DEBUG=False)会查这张表,输出带哈希的 URL。</p>'),
        sec('CSS 里的引用', '', term('', blk('d89', 2)), '<p>这一步叫 <code>post_process</code>。因为要先算被引用文件的哈希,所以需要多趟处理(<code>max_post_process_passes</code>,本文没有测)。</p>'),
        sec('哈希与缓存失效', '', term('', blk('d89', 3)), '<p>有了哈希文件名,就可以给静态文件设很长的缓存时间(第 90 篇)。代价是旧版本文件累积;部署时要不要清理,取决于是否需要兼容还没刷新的旧页面。</p>'),
        sec('清单缺项', '', term('', blk('d89', 4)), '<p>常见触发场景:本地开发一直 DEBUG=True 没发现,上线后某个 <code>{% static %}</code> 引用了不存在的文件。CI 里可以对所有模板做一次 DEBUG=False 的渲染检查(本文没有做)。</p>'),
        sec('manifest_strict', '', term('', blk('d89', 5)), '<p>非严格模式是「宽容」而不是「万能」:文件真的不存在仍然报错。</p>'),
        sec('分步演示:文件名哈希', '', demo('ManifestStaticFilesStorage', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。STORAGES["staticfiles"] 设置为 ManifestStaticFilesStorage;DEBUG=False', '没有验证:ManifestFilesMixin 的 manifest_storage、大项目的 post_process 耗时、source map 的引用改写、JS 里 import 的引用(需要 Django 4.2+ 的 support_js_module_import_aggregation 选项)'],
)
