"""
双保险备份:每次 Article/Series 增删改,都把当前数据库状态原样镜像写到
settings.BACKUP_DIR 下的 <url>.html 文件 + manifest.json。

这样 sqlite 数据库本身丢失、损坏,或者跑 Django 的服务器整个没了,只要这个
备份目录还在(比如同步一份到本地电脑、或者放进 git),就能在任何一台新机器
上跑 `python manage.py migrate` + `python manage.py import_articles`
把数据库完整重建回来,不依赖 sqlite 文件本身的存活。

这里存的是文章原文,不做任何改写。对外发布的版本(资源路径换成带哈希的、附带 .gz)
在 static_site.py 里生成,写到 PUBLIC_DIR。
"""
import json

from django.conf import settings

from .files import atomic_write


def _manifest_path():
    return settings.BACKUP_DIR / 'manifest.json'


def rebuild_manifest():
    from .models import Article, Series

    manifest = {
        'series': {
            s.key: {'label': s.label, 'color': s.color}
            for s in Series.objects.all()
        },
        'articles': [
            {
                'title': a.title,
                'series': a.series.key,
                'tags': a.tag_list(),
                'date': a.date.isoformat(),
                'desc': a.description,
                'url': a.url,
            }
            for a in Article.objects.select_related('series').order_by('-date')
        ],
    }
    atomic_write(_manifest_path(), json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')


def write_article_file(article):
    atomic_write(settings.BACKUP_DIR / article.url, article.content_html)


def delete_article_file(url):
    path = settings.BACKUP_DIR / url
    if path.exists():
        path.unlink()
