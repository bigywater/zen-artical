from lib import *
R = J('d78')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("匿名访问:@login_required(函数视图与 LoginRequiredMixin 的类视图)→ 302,Location: /accounts/login/?next=/secret/(next 里带着原路径,查询串被编码:/secret/%3Fx%3D1%26y%3D2);@permission_required 默认也是 302 去登录页;加 raise_exception=True 则是 403;@user_passes_test 可指定 login_url。", t=tl(L('anon')), kv=KV([['匿名', '302 → LOGIN_URL?next=…'], ['raise_exception=True', '403']], ['匿名'])),
    step("已登录但没有权限时的坑:@permission_required('auth.add_user')(默认)→ 又是 302 去登录页——用户明明登录了却被送去登录页,看起来像循环;raise_exception=True → 403;类视图 PermissionRequiredMixin → 403(已登录用户)。@user_passes_test 的条件不满足 → 302 到 login_url。", t=tl(L('noperm')), n=fl([['函数装饰器 permission_required(默认)', '302 → 登录页'], ['permission_required(raise_exception=True)', '403'], ['PermissionRequiredMixin(已登录)', '403']], mark=[0], done=[1, 2]), kv=KV([['已登录无权限', '装饰器默认重定向,Mixin 默认 403']], ['已登录无权限'])),
    step("有权限的超级用户:所有视图都是 200。匿名 follow=True 跟随重定向后落在登录页,并且登录页收到的 next 就是原来的完整路径与查询串(/secret/?x=1&y=2)。", t=tl(L('ok')), kv=KV([['next', '带原始路径与查询串']], ['next'])),
    step("next 的安全:Django 提供 url_has_allowed_host_and_scheme 判断跳转目标是否安全:/dashboard/ 允许;//evil.com/、https://evil.com/x、javascript:alert(1) 都不允许;自己的主机(https://testserver/x)允许。自定义登录视图跳转 next 时必须用它过滤,防止开放重定向。(Django 自带 LoginView 使用它的说法本文没有实测。)", t=tl(L('next')), kv=KV([['开放重定向', '用 url_has_allowed_host_and_scheme 过滤 next']], ['开放重定向'])),
]
A = dict(
    n=78, series='django', tags='Django,login_required,权限装饰器,真实验证,动画演示',
    desc='实测 login_required / permission_required / user_passes_test 与对应的 Mixin:匿名 302 到 LOGIN_URL?next=…;已登录但无权限时装饰器默认又重定向到登录页(raise_exception=True 才是 403),Mixin 则是 403;next 的安全判断。',
    lead='为什么已经登录的用户点一个没权限的页面,会被送回登录页?装饰器和 Mixin 的行为为什么不一样?这篇把每种情形的响应码和 Location 都列出来。',
    facts=[('302 vs 403', '已登录但无权限:permission_required 装饰器默认 302 到登录页;raise_exception=True 或 PermissionRequiredMixin 是 403'), ('next', '重定向带原路径与查询串,登录页据此跳回'), ('开放重定向', '自己处理 next 时要用 url_has_allowed_host_and_scheme 过滤')],
    body=[
        sec('匿名用户', '', term('', blk('d78', 1)), '<p><code>LOGIN_URL</code> 决定去哪里登录(本实验设为 <code>/accounts/login/</code>)。</p>'),
        sec('已登录但权限不足', '', term('', blk('d78', 2)), '<p>装饰器版本默认重定向,是因为它把「没权限」当成「换个账号试试」。对已经登录的用户这几乎总是错的——用 <code>raise_exception=True</code>,或自己抛 <code>PermissionDenied</code>。</p>'),
        sec('有权限时', '', term('', blk('d78', 3)), '<p>一切正常。</p>'),
        sec('next 参数的安全', '', term('', blk('d78', 4)), '<p>开放重定向是钓鱼的常用手段:把 <code>next</code> 指到外部站点。</p>'),
        sec('分步演示:访问控制装饰器', '', demo('login_required 与权限装饰器', [('t', 'term', '响应'), ('n', 'flow', '对比'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。django.test.Client;LOGIN_URL = /accounts/login/', '没有验证:AJAX / API 请求下的响应(重定向对它们通常不合适)、REDIRECT_FIELD_NAME 自定义、Django 自带 LoginView 对 next 的过滤实测、多个权限的 permission_required 元组、在 ASGI 下的表现'],
)
