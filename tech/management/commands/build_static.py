from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import set_urlconf

from tech import assets, backup, static_site
from tech.models import Article


class Command(BaseCommand):
    help = (
        '从数据库整体重新生成对外文件:备份镜像(BACKUP_DIR)、每篇文章的发布页、'
        '首页和所有分类分页(PUBLIC_DIR),以及静态资源的带哈希副本。幂等,可重复执行。'
        '首次部署、改了 css/图标/模板之后,或日志里出现"静态列表页重建失败"时跑一遍。'
    )

    def handle(self, *args, **options):
        # 命令行里没有请求上下文,reverse() 默认会退回 settings.ROOT_URLCONF
        # (由 DEFAULT_SITE 决定,可能是 zodiac);这里的 publish_article /
        # rebuild_lists 内部会 reverse('series_list') 之类的 tech 专属路由名,
        # 必须显式切到 tech 自己的 urlconf,不依赖 DEFAULT_SITE 是什么。
        set_urlconf(settings.SITE_URLCONF_MAP['tech'])
        mapping = assets.fingerprint()
        counts = static_site.nav_counts()
        count = 0
        urls = set()
        for article in Article.objects.select_related('series').iterator():
            backup.write_article_file(article)
            static_site.publish_article(article, mapping, counts)
            urls.add(article.url)
            count += 1
        backup.rebuild_manifest()
        pages = static_site.rebuild_lists(mapping)
        # 所有页面都已经用新映射重新发布,旧哈希的资源副本这时才可以安全删除
        removed = assets.prune(mapping)
        orphans = static_site.remove_orphans(urls)
        self.stdout.write(self.style.SUCCESS(
            f'文章 {count} 篇, 列表页 {pages} 页, 资源 {len(mapping)} 个(清理旧版本 {removed} 个, 已删除文章的残留文件 {orphans} 个)\n'
            f'  发布目录 {settings.PUBLIC_DIR}\n  备份目录 {settings.BACKUP_DIR}'
        ))
