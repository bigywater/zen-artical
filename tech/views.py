from django.http import Http404, HttpResponse, HttpResponsePermanentRedirect
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.views.generic import View

from .models import Article, Series
from . import seo
from .static_site import build_list_context, list_url


class ArticleListView(View):
    # 生产环境里这几个 URL 正常都被 nginx 直接用 public/ 下的静态文件应答,
    # 走到这里说明静态文件还没生成,或者页码越界 / 是 /page/1/ 这类非规范路径。
    def get(self, request, series_key='all', page_number=1):
        if series_key != 'all' and not Series.objects.filter(key=series_key).exists():
            raise Http404

        context = build_list_context(series_key, page_number)
        canonical = list_url(series_key, context['page'].number)
        if request.path != canonical:
            return HttpResponsePermanentRedirect(canonical)
        html = seo.inject_baidu(seo.inject_beian(render_to_string('tech/article_list.html', context)))
        return HttpResponse(html, content_type='text/html; charset=utf-8')


class ArticleDetailView(View):
    def get(self, request, url):
        article = get_object_or_404(Article.objects.select_related('series'), url=url)
        html = seo.inject_jsonld(seo.inject_beian(seo.normalize_domain(article.content_html)), seo.article_jsonld(article))
        html = seo.inject_baidu(html)
        return HttpResponse(html, content_type='text/html; charset=utf-8')
