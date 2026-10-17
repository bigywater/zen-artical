from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.staticfiles.storage import staticfiles_storage
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.core.paginator import Paginator

from .constants import DIMENSION_CHOICES, SIGN_CHOICES
from .models import Article


def article_list(request):
    qs = Article.objects.filter(status="published")

    sign = request.GET.get("sign")
    if sign:
        qs = qs.filter(sign=sign)

    dimension = request.GET.get("dimension")
    if dimension:
        qs = qs.filter(dimension=dimension)

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "zodiac/article_list.html", {
        "page_obj": page_obj,
        "sign_choices": SIGN_CHOICES,
        "dimension_choices": DIMENSION_CHOICES,
        "current_sign": sign,
        "current_dimension": dimension,
    })


def article_detail(request, slug):
    article = get_object_or_404(Article, slug=slug, status="published")
    canonical_url = request.build_absolute_uri(article.get_absolute_url())
    return render(request, "zodiac/article_detail.html", {"article": article, "canonical_url": canonical_url})


@staff_member_required
def article_wechat(request, slug):
    article = get_object_or_404(Article, slug=slug)
    return render(request, "zodiac/article_wechat.html", {"article": article})


def favicon(request):
    # 浏览器/爬虫经常不看 <link rel="icon">，直接请求这个约定俗成的路径；
    # 用 staticfiles_storage 取 URL 而不是写死路径，这样生产环境
    # WhiteNoise 加的内容哈希文件名也能对上。
    return HttpResponseRedirect(staticfiles_storage.url("zodiac/icons/favicon.ico"))


def robots_txt(request):
    sitemap_url = request.build_absolute_uri("/sitemap.xml")
    lines = ["User-agent: *", "Allow: /", "Disallow: /admin/", f"Sitemap: {sitemap_url}"]
    return HttpResponse("\n".join(lines), content_type="text/plain")
