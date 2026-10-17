"""
星座站点专属 urlconf。只包含 zodiac app 自己的 admin / sitemap / robots.txt /
文章路由，不会 import 或暴露 tech app 的任何东西。
"""
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from zodiac.admin import zodiac_admin_site
from zodiac.sitemaps import ArticleSitemap, HomeSitemap
from zodiac.views import favicon, robots_txt

urlpatterns = [
    path("admin/", zodiac_admin_site.urls),
    path("sitemap.xml", sitemap, {"sitemaps": {"home": HomeSitemap, "articles": ArticleSitemap}}, name="sitemap"),
    path("robots.txt", robots_txt, name="robots_txt"),
    path("favicon.ico", favicon, name="favicon"),
    path("", include("zodiac.urls")),
]
