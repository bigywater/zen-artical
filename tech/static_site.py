"""
文章页和首页 / 分类分页的静态化:后台增删改文章的那一刻就把它们渲染成文件写到
settings.PUBLIC_DIR,平时访问完全不经过 Django,nginx 直接返回。

发布出去的每个页面都做两件事(见 assets.py / files.py):
  1. 页面里的 /assets/... 路径换成带内容哈希的版本,nginx 对它设长期缓存;
  2. 同时写好 .gz,nginx 用 gzip_static 直接返回,不用每次请求现场压缩。

文章页 <url>.html 就是 Article.content_html 发布后的样子;列表页需要渲染模板:

    /                        -> public/index.html
    /page/2/                 -> public/page/2/index.html
    /series/go/              -> public/series/go/index.html
    /series/go/page/2/       -> public/series/go/page/2/index.html

Django 的 ArticleListView 用同一套 build_list_context 渲染同一个模板,所以 nginx
找不到静态文件时回落给 Django,拿到的页面是一样的(runserver 开发时也是这条路)。
"""
import logging

from django.conf import settings
from django.core.paginator import Paginator
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse

from . import assets, seo
from .files import remove_public, write_public
from .models import Article, Series

logger = logging.getLogger(__name__)

PAGE_SIZE = 12
PAGE_WINDOW = 10   # 分页条上最多同时显示多少个页码


def list_url(series_key, page_number):
    """列表页的规范 URL。'all' 表示不筛选分类。"""
    if series_key == 'all':
        if page_number == 1:
            return reverse('article_list')
        return reverse('article_list_page', args=[page_number])
    if page_number == 1:
        return reverse('series_list', args=[series_key])
    return reverse('series_list_page', args=[series_key, page_number])


def page_window(current, total, size=None):
    """当前页附近最多 size 个页码(滑动窗口,当前页尽量排在中间,到头尾时贴边)。

    总页数再多,页面上的链接数也是常数:10000 页也只渲染 10 个页码 + 前后/首末箭头,
    其余页靠翻页到达。
    """
    size = size or PAGE_WINDOW
    if total <= size:
        return list(range(1, total + 1))
    start = min(max(current - size // 2 + 1, 1), total - size + 1)
    return list(range(start, start + size))


def build_list_context(series_key, page_number):
    articles = Article.objects.select_related('series')
    if series_key != 'all':
        articles = articles.filter(series__key=series_key)

    page = Paginator(articles, PAGE_SIZE).get_page(page_number)
    series_list = Series.objects.all()
    labels = {s.key: s.label for s in series_list}
    canonical_path = list_url(series_key, page.number)
    title, description = seo.list_meta(series_key, labels.get(series_key, '全部文章'), page.paginator.count, page)
    return {
        'page': page,
        'series_list': series_list,
        'series_counts': {s.key: s.articles.count() for s in series_list},
        'active_series': series_key,
        'total_articles': Article.objects.count(),
        'canonical_path': canonical_path,
        'page_window': page_window(page.number, page.paginator.num_pages),
        'site_url': settings.SITE_URL,
        'site_domain': settings.SITE_DOMAIN,
        'site_slogan': settings.SITE_SLOGAN,
        'page_title': title,
        'page_description': description,
        'jsonld': seo.list_jsonld(series_key, page, canonical_path, title, description),
    }


def _list_file(url):
    return settings.PUBLIC_DIR / url.lstrip('/') / 'index.html'


def nav_counts():
    """{系列 key: 篇数},侧栏数字的来源。批量发布时算一次传进 publish_article。"""
    from django.db.models import Count
    return dict(Series.objects.annotate(n=Count('articles')).values_list('key', 'n'))


def publish_article(article, mapping=None, counts=None):
    """把一篇文章发布到 PUBLIC_DIR。mapping 是 assets.fingerprint() 的结果,counts 是 nav_counts() 的结果,批量发布时传进来复用。"""
    if mapping is None:
        mapping = assets.fingerprint()
    if counts is None:
        counts = nav_counts()
    # 备案块里的图标路径要在 rewrite 之前插入,这样它也会被换成带哈希的版本
    html = seo.inject_beian(seo.refresh_nav_counts(seo.normalize_domain(article.content_html), counts))
    html = assets.rewrite(html, mapping)
    html = seo.inject_jsonld(html, seo.article_jsonld(article))
    html = seo.inject_baidu(html)
    write_public(settings.PUBLIC_DIR / article.url, html)


def remove_orphans(urls):
    """删掉库里已经不存在的文章留在 PUBLIC_DIR / BACKUP_DIR 顶层的文件(含 .gz)。

    文章从库里删除时,信号会清理对应文件;但整库替换(比如部署时 --with-db)、裸 SQL 删除
    不会触发信号,旧文章的页面就会一直留在 nginx 的目录里继续对外提供。
    只动顶层的 *.html / *.html.gz,index.html 是首页,不算文章。
    """
    removed = 0
    for base, keep in ((settings.PUBLIC_DIR, {'index.html'}), (settings.BACKUP_DIR, set())):
        if not base.is_dir():
            continue
        for path in base.glob('*.html*'):
            name = path.name[:-3] if path.suffix == '.gz' else path.name
            if path.is_file() and name not in urls and name not in keep:
                path.unlink()
                removed += 1
    return removed


def unpublish_article(url):
    remove_public(settings.PUBLIC_DIR / url)


def rebuild_lists(mapping=None):
    """把首页和所有分类的所有分页渲染到 PUBLIC_DIR,并清掉已经不存在的旧分页。"""
    if mapping is None:
        mapping = assets.fingerprint()
    written = set()
    for series_key in ['all', *Series.objects.values_list('key', flat=True)]:
        num_pages = build_list_context(series_key, 1)['page'].paginator.num_pages
        for number in range(1, num_pages + 1):
            context = build_list_context(series_key, number)
            path = _list_file(list_url(series_key, number))
            html = seo.inject_baidu(seo.inject_beian(render_to_string('tech/article_list.html', context)))
            write_public(path, assets.rewrite(html, mapping))
            written.add(path)

    # 文章减少 / 分类被删之后,多出来的旧分页文件要清掉,不然 nginx 会一直返回过期页面。
    for subdir in ('page', 'series'):
        root = settings.PUBLIC_DIR / subdir
        if not root.exists():
            continue
        for path in root.rglob('index.html'):
            if path not in written:
                remove_public(path)
        for directory in [*sorted(root.rglob('*'), reverse=True), root]:
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()
    return len(written)


# 后台一次操作(比如批量删除)会连续触发很多次 save/delete 信号,每次都整站重建太浪费。
# 用 transaction.on_commit 把重建推迟到事务提交之后;_dirty/_built 两个计数保证同一批
# 变更只真正重建一次,而且事务回滚(回调被丢弃)时不会把"已排队"状态卡死。
_dirty = 0
_built = 0


def schedule_rebuild():
    global _dirty
    _dirty += 1

    def run():
        global _built
        if _built == _dirty:
            return
        target = _dirty
        try:
            rebuild_lists()
        except Exception:
            # 数据已经提交了,静态页重建失败不该让后台保存报 500;
            # 记日志,事后跑 `manage.py build_static` 补上即可。
            logger.exception('静态列表页重建失败,请运行 manage.py build_static')
            return
        _built = target

    transaction.on_commit(run)
