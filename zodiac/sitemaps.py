from django.contrib.sitemaps import Sitemap
from django.db.models import Max
from django.urls import reverse

from .models import Article


class HomeSitemap(Sitemap):
    """首页(文章列表)。每天都有新文章,是搜索引擎回访最该关注的入口。"""
    changefreq = "daily"
    priority = 1.0

    def items(self):
        return ["zodiac:article_list"]

    def location(self, name):
        return reverse(name)

    def lastmod(self, name):
        return Article.objects.filter(status="published").aggregate(latest=Max("updated_at"))["latest"]


class ArticleSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.7

    def items(self):
        return Article.objects.filter(status="published")

    def lastmod(self, obj):
        return obj.updated_at
