"""
技术站点专属 urlconf。只包含 tech app 自己的 admin / sitemap / robots.txt /
文章路由,不会 import 或暴露 zodiac app 的任何东西。

对外发布页面(首页、分类列表、文章正文)平时不走这里——生产环境 nginx 直接从
settings.PUBLIC_DIR 读静态文件应答,Django 只在静态文件还没生成、或者页码越界
这类边缘情况兜底(见 tech/views.py 的注释),以及承担 admin 后台的职责。
"""
from django.conf import settings
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse
from django.urls import include, path
from django.views.static import serve

from tech.admin import tech_admin_site
from tech.sitemaps import ArticleSitemap, ListSitemap

sitemaps = {'lists': ListSitemap, 'articles': ArticleSitemap}


def robots_txt(request):
    content = f'User-agent: *\nAllow: /\nDisallow: /admin/\n\nSitemap: {settings.SITE_URL}/sitemap.xml\n'
    return HttpResponse(content, content_type='text/plain; charset=utf-8')


urlpatterns = [
    path('admin/', tech_admin_site.urls),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='sitemap'),
    path('robots.txt', robots_txt, name='robots_txt'),
]

if settings.DEBUG:
    # 生产环境 /assets/、/favicon.ico、/site.webmanifest 都由 nginx 直接指到
    # PUBLIC_DIR 下对应文件;本地开发时用这几条顶一下。必须排在 tech.urls 的
    # include 之前 —— 那边 `<path:url>` 是个通配路由,会先把这些请求当成文章
    # url 接住,永远轮不到这里。
    urlpatterns += [
        path('assets/<path:path>', serve, {'document_root': settings.PUBLIC_DIR / 'assets'}),
        path('favicon.ico', serve, {'document_root': settings.PUBLIC_DIR, 'path': 'favicon.ico'}),
        path('site.webmanifest', serve, {'document_root': settings.PUBLIC_DIR, 'path': 'site.webmanifest'}),
    ]

urlpatterns += [
    path('', include('tech.urls')),
]
