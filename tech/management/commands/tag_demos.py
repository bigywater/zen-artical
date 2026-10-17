from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import set_urlconf

from tech import backup, static_site
from tech.demos import TAG, has_animation_demo
from tech.models import Article


class Command(BaseCommand):
    help = (
        f'给所有有动画演示的文章加上「{TAG}」标签(判据见 tech/demos.py)。幂等,只增不删,可重复执行;'
        '新写了文章之后跑一遍即可。用 .update() 写库,不会改动文章的 updated_at,写完自动重新发布受影响的页面。'
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='只列出会改哪些文章,不写库')

    def handle(self, *args, **options):
        # 命令行没有请求上下文,publish_article() 内部 reverse() 需要 tech 自己
        # 的 urlconf,不能依赖 DEFAULT_SITE 是什么。
        set_urlconf(settings.SITE_URLCONF_MAP['tech'])
        to_tag = []
        has_tag_without_demo = []
        already = 0
        for article in Article.objects.select_related('series').iterator():
            tags = article.tag_list()
            demo = has_animation_demo(article.content_html)
            if demo and TAG not in tags:
                to_tag.append((article, ','.join([*tags, TAG])))
            elif demo:
                already += 1
            elif TAG in tags:
                has_tag_without_demo.append(article.url)

        if options['dry_run']:
            for article, _ in to_tag:
                self.stdout.write(f'  将打标签: {article.url}')
            self.stdout.write(f'共 {len(to_tag)} 篇需要打标签,{already} 篇已有(dry-run,未写库)')
            return

        done = skipped = 0
        for article, new_tags in to_tag:
            # 带上"旧 tags 没变"的条件:别的进程刚好改过这篇文章的话,这次就跳过,不覆盖它的改动
            if Article.objects.filter(pk=article.pk, tags=article.tags).update(tags=new_tags):
                article.tags = new_tags
                static_site.publish_article(article)   # JSON-LD 的 keywords 跟着更新
                done += 1
            else:
                skipped += 1
        if done:
            backup.rebuild_manifest()
            static_site.rebuild_lists()

        self.stdout.write(self.style.SUCCESS(f'新打标签 {done} 篇,原本就有 {already} 篇'))
        if skipped:
            self.stdout.write(self.style.WARNING(f'{skipped} 篇在运行期间被别的进程修改过,已跳过,再跑一次即可'))
        if has_tag_without_demo:
            self.stdout.write(self.style.WARNING(
                f'{len(has_tag_without_demo)} 篇带着「{TAG}」标签但没有检测到演示组件(不会自动删除): '
                + ', '.join(has_tag_without_demo[:5])
            ))
