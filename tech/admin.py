from django.contrib import admin
from django.contrib.admin import AdminSite
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, User
from django.shortcuts import get_object_or_404, render
from django.urls import path
from django.utils.html import format_html

from .models import Article, Series
from .wechat_export import render_wechat_html

# 独立的 AdminSite：只挂本 app 的模型，避免和 zodiac app 共用默认 admin.site
# 导致两个站点的后台互相看得到对方的数据模型。默认的 admin.site 完全不在任何
# urlconf 里暴露，所以不会被访问到。
tech_admin_site = AdminSite(name="tech_admin")
tech_admin_site.site_header = "技术站后台"
tech_admin_site.site_title = "技术站后台"
tech_admin_site.index_title = "内容管理"

tech_admin_site.register(User, UserAdmin)
tech_admin_site.register(Group, GroupAdmin)


@admin.register(Series, site=tech_admin_site)
class SeriesAdmin(admin.ModelAdmin):
    list_display = ('key', 'label', 'color')
    search_fields = ('key', 'label')


@admin.register(Article, site=tech_admin_site)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'series', 'date', 'url', 'wechat_link')
    list_filter = ('series',)
    search_fields = ('title', 'description', 'tags')
    date_hierarchy = 'date'
    change_form_template = 'tech/admin_article_change_form.html'

    def wechat_link(self, obj):
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">复制到公众号</a>',
            f'{obj.pk}/wechat/',
        )
    wechat_link.short_description = '公众号'

    def get_urls(self):
        urls = [
            path('<int:object_id>/wechat/', self.admin_site.admin_view(self.wechat_copy_view),
                 name='tech_article_wechat'),
        ]
        return urls + super().get_urls()

    def wechat_copy_view(self, request, object_id):
        article = get_object_or_404(Article, pk=object_id)
        wechat_html = render_wechat_html(article.content_html)
        return render(request, 'tech/admin_wechat_copy.html', {
            'article': article,
            'wechat_html': wechat_html,
        })
