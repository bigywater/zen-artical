from django.conf import settings
from django.http import HttpResponseNotFound


class HostSiteMiddleware:
    """
    一个 Django project、两个对外完全独立的站点（星座 / 技术），
    靠请求的 Host 头分流到各自的 urlconf，互相之间没有任何可见关联：

    - 每个站点用自己的 urlconf（含各自独立的 admin、sitemap、robots.txt）
    - 静态文件路径按站点前缀做交叉拦截，防止有人在 A 域名底下探测到 B 站点的
      /static/<other_app>/... 文件，从而看出两个站点是同一套后端

    站点归属通过环境变量配置（见 settings.py 的 SITE_HOST_MAP），本地开发时
    Host 匹配不上任何一组会退回 settings.DEFAULT_SITE。
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(":")[0]
        site = settings.SITE_HOST_MAP.get(host, settings.DEFAULT_SITE)
        request.site = site

        # 交叉静态文件拦截：zodiac 站点不能读到 /static/tech/...，反之亦然。
        # STATIC_URL（'static/'）本身没有前导斜杠，而 request.path 总是有，
        # 所以这里要补上，不然 startswith 永远不命中。
        static_prefix = "/" + settings.STATIC_URL.lstrip("/")
        if request.path.startswith(static_prefix):
            sub_path = request.path[len(static_prefix):]
            for other_app in settings.SITE_APPS.values():
                if other_app == settings.SITE_APPS[site]:
                    continue
                if sub_path.startswith(f"{other_app}/"):
                    return HttpResponseNotFound()

        request.urlconf = settings.SITE_URLCONF_MAP[site]
        return self.get_response(request)
