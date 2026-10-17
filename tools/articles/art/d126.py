from lib import *
R = J('d126')
def S(k): return [l for l in out('d126').split('== ')[k].splitlines()[1:] if l.strip()]
B = S(4)
steps = [
    step("XFrameOptionsMiddleware 默认给所有响应加 X-Frame-Options: DENY;@xframe_options_sameorigin 改成 SAMEORIGIN;@xframe_options_exempt 让这个视图不带该头;再叠加 csp_override 的 frame-ancestors 'self' / 'none' 会发出 Content-Security-Policy: frame-ancestors …。", t=tl(S(1)), done=[0, 1, 2, 3, 4], kv=KV([['默认', 'DENY'], ['可改', 'SAMEORIGIN / exempt / CSP frame-ancestors']], ['默认'])),
    step("全局设置 X_FRAME_OPTIONS 只有两个取值:'DENY'(默认)与 'SAMEORIGIN',对应响应头同名。", t=tl(S(2)), kv=KV([['X_FRAME_OPTIONS', 'DENY / SAMEORIGIN']], ['X_FRAME_OPTIONS'])),
    step("真实 Chrome 里的结果(父页面在 http://localhost:9540,跨源 iframe 指向 http://127.0.0.1:9540):DENY 的页面,同源和跨源 iframe 都被拦截;SAMEORIGIN 的页面,同源加载成功、跨源被拦截;exempt(没有任何头)的页面,同源与跨源都能嵌入。", t=tl(B[:4]), mark=[1], done=[3], kv=KV([['DENY', '谁都不能嵌'], ['SAMEORIGIN', '只有同源能嵌'], ['无头', '谁都能嵌']], ['无头'])),
    step("CSP 的 frame-ancestors:'self' 时同源加载成功、跨源被拦截(控制台:Framing 'http://127.0.0.1:9540/' violates … frame-ancestors 'self');'none' 时同源和跨源都被拦截。控制台还记录了 X-Frame-Options 被拒:Refused to display 'http://localhost:9540/' in a frame because it set 'X-Frame-Options' to 'deny'。", t=tl(B[4:]), mark=[0, 1], kv=KV([["frame-ancestors 'self'", '等价于 SAMEORIGIN'], ["frame-ancestors 'none'", '等价于 DENY']], ["frame-ancestors 'none'"])),
]
A = dict(
    n=126, series='django', tags='Django,安全,点击劫持,X-Frame-Options,CSP,真实验证,动画演示',
    desc="点击劫持防护:XFrameOptionsMiddleware 默认 X-Frame-Options: DENY;在真实 Chrome 里测 5 种页面的同源与跨源 iframe:DENY 全拦、SAMEORIGIN 只放同源、exempt 全放行、CSP frame-ancestors 'self' / 'none' 同样生效。",
    lead='点击劫持靠的是把你的页面用透明 iframe 盖在别人的页面上。Django 用 X-Frame-Options 防它;Django 6 之后也可以用 CSP 的 frame-ancestors。这篇用真实的 Chrome 嵌入同源和跨源的 iframe,看每种设置的实际效果。',
    facts=[('默认 DENY', 'XFrameOptionsMiddleware 给所有响应加 X-Frame-Options: DENY'), ('同源 vs 跨源', 'SAMEORIGIN 与 frame-ancestors \'self\':同源能嵌、跨源被拦'), ('真浏览器', '5 种页面 × 同源 / 跨源 10 个 iframe 在 Chrome 里逐个检查')],
    body=[
        sec('服务端发出的头', '', term('', blk('d126', 1)), '<p>单个视图可以用装饰器覆盖全局设置:<code>@xframe_options_sameorigin</code>、<code>@xframe_options_exempt</code>、<code>@xframe_options_deny</code>。</p>'),
        sec('全局设置', '', term('', blk('d126', 2))),
        sec('浏览器里的实际结果', '', term('', blk('d126', 4), tag='实测 · Chrome + chrome-devtools'), '<p>同源 iframe 的结果是用脚本读 <code>contentDocument</code>(能读到页面文字即加载成功,读不到说明被拦截);跨源 iframe 脚本读不到内容,所以是我看截图判断的:被拦截的显示为灰色破损图标或空白,加载成功的能看到页面内容。这一节是在浏览器里手工检查后记录的,不是脚本自动生成的。</p>'),
        sec('该选哪个', '', '<p>X-Frame-Options 只能表达「禁止 / 同源」,CSP 的 <code>frame-ancestors</code> 还能指定允许哪些具体的站点来嵌入。两个同时存在时浏览器如何取舍,本文没有验证(我只测了单独出现的情形)。</p>'),
        sec('分步演示', '', demo('防点击劫持', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。runserver(--noreload)+ Chrome(chrome-devtools);父页面用 localhost、跨源 iframe 用 127.0.0.1(端口相同、主机名不同即为不同源)', '没有验证:移动端浏览器、旧浏览器对 frame-ancestors 的支持、X-Frame-Options 与 CSP 同时出现时的优先级、ALLOW-FROM(已废弃)、点击劫持的其它形式(拖拽、光标欺骗)'],
)
