from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.db.models import Max

from .models import Article, Series
from .static_site import list_url


class CanonicalSitemap(Sitemap):
    """sitemap 里的域名永远是规范域名,不跟着请求的 Host 走
    (否则用 IP、别名域名访问时,会给搜索引擎一份指向错误域名的 sitemap)。"""
    protocol = 'https'

    def get_domain(self, site=None):
        return settings.SITE_DOMAIN


class ListSitemap(CanonicalSitemap):
    """首页和每个分类的第一页。分页(第 2 页起)不放,它们靠列表页里的翻页链接被发现。"""
    priority = 0.8
    changefreq = 'weekly'

    def items(self):
        return ['all', *Series.objects.values_list('key', flat=True)]

    def location(self, key):
        return list_url(key, 1)

    def lastmod(self, key):
        articles = Article.objects.all() if key == 'all' else Article.objects.filter(series__key=key)
        return articles.aggregate(latest=Max('date'))['latest']


class ArticleSitemap(CanonicalSitemap):
    priority = 0.7
    changefreq = 'monthly'

    def items(self):
        return Article.objects.all()

    def location(self, obj):
        return f'/{obj.url}'

    def lastmod(self, obj):
        return obj.date
