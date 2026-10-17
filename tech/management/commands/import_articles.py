import json
from datetime import date

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.urls import set_urlconf

from tech.models import Article, Series


class Command(BaseCommand):
    help = (
        '从备份目录(manifest.json + 各 .html 原文,默认就是 BACKUP_DIR)导入/重建 Series 和 Article,幂等可重复执行。'
        '用于灾难恢复:sqlite 丢了就先 migrate 建空库,再跑这个命令从备份文件整体恢复。'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dir',
            default=str(settings.BACKUP_DIR),
            help='备份目录路径(默认 settings.BACKUP_DIR)',
        )

    # 放进一个事务:几百次保存触发的列表页重建会推迟到提交后合并成一次
    @transaction.atomic
    def handle(self, *args, **options):
        # 命令行没有请求上下文,save() 触发的信号里 reverse() 需要 tech 自己的
        # urlconf,不能依赖 DEFAULT_SITE 是什么。
        set_urlconf(settings.SITE_URLCONF_MAP['tech'])
        source_dir = options['dir']
        manifest_path = f'{source_dir}/manifest.json'
        try:
            with open(manifest_path, encoding='utf-8') as f:
                manifest = json.load(f)
        except FileNotFoundError:
            raise CommandError(f'找不到 manifest: {manifest_path}')

        series_created = series_updated = 0
        for key, info in manifest['series'].items():
            _, created = Series.objects.update_or_create(
                key=key,
                defaults={'label': info['label'], 'color': info['color']},
            )
            if created:
                series_created += 1
            else:
                series_updated += 1

        article_created = article_updated = 0
        for entry in manifest['articles']:
            article_path = f"{source_dir}/{entry['url']}"
            try:
                with open(article_path, encoding='utf-8') as f:
                    content_html = f.read()
            except FileNotFoundError:
                self.stderr.write(self.style.WARNING(f"跳过(文件不存在): {article_path}"))
                continue

            series = Series.objects.get(key=entry['series'])
            _, created = Article.objects.update_or_create(
                url=entry['url'],
                defaults={
                    'title': entry['title'],
                    'series': series,
                    'tags': ','.join(entry.get('tags', [])),
                    'date': date.fromisoformat(entry['date']),
                    'description': entry.get('desc', ''),
                    'content_html': content_html,
                },
            )
            if created:
                article_created += 1
            else:
                article_updated += 1

        self.stdout.write(self.style.SUCCESS(
            f'Series: {series_created} 新建 / {series_updated} 更新。'
            f' Article: {article_created} 新建 / {article_updated} 更新。'
            f' 总计 Series={Series.objects.count()} Article={Article.objects.count()}'
        ))
