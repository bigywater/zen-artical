from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from . import backup, static_site
from .models import Article, Series


@receiver(pre_save, sender=Article)
def _remember_old_url(sender, instance, **kwargs):
    # 改 url(相当于给文章改名)时,存档目录里那个旧文件名要跟着删掉,
    # 不然会留一份孤儿文件。
    instance._old_url = None
    if instance.pk:
        try:
            instance._old_url = Article.objects.get(pk=instance.pk).url
        except Article.DoesNotExist:
            pass


@receiver(post_save, sender=Article)
def _export_article(sender, instance, **kwargs):
    old_url = getattr(instance, '_old_url', None)
    if old_url and old_url != instance.url:
        backup.delete_article_file(old_url)
        static_site.unpublish_article(old_url)
    backup.write_article_file(instance)
    static_site.publish_article(instance)
    backup.rebuild_manifest()
    static_site.schedule_rebuild()


@receiver(post_delete, sender=Article)
def _remove_article_file(sender, instance, **kwargs):
    backup.delete_article_file(instance.url)
    static_site.unpublish_article(instance.url)
    backup.rebuild_manifest()
    static_site.schedule_rebuild()


@receiver(post_save, sender=Series)
@receiver(post_delete, sender=Series)
def _rebuild_manifest_on_series_change(sender, instance, **kwargs):
    backup.rebuild_manifest()
    static_site.schedule_rebuild()
