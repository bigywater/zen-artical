from django.contrib import admin
from django.contrib.admin import AdminSite
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, User
from django.urls import reverse
from django.utils.html import format_html

from .models import Article

# 独立的 AdminSite：只挂本 app 的模型，避免和 tech app 共用默认 admin.site
# 导致两个站点的后台互相看得到对方的数据模型。默认的 admin.site 完全不在任何
# urlconf 里暴露，所以不会被访问到。
zodiac_admin_site = AdminSite(name="zodiac_admin")
zodiac_admin_site.site_header = "星座志后台"
zodiac_admin_site.site_title = "星座志后台"
zodiac_admin_site.index_title = "内容管理"

# 用默认 admin.site 换成独立 site 之后，User/Group 不会自动出现，手动挂一份，
# 保持和之前单项目时一样能在后台管理账号。
zodiac_admin_site.register(User, UserAdmin)
zodiac_admin_site.register(Group, GroupAdmin)


@admin.register(Article, site=zodiac_admin_site)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "sign", "dimension", "status", "published_at", "updated_at", "wechat_link")
    list_filter = ("status", "dimension", "sign")
    search_fields = ("title", "summary")
    prepopulated_fields = {"slug": ("title",)}
    date_hierarchy = "published_at"
    list_editable = ("status",)
    readonly_fields = ("wechat_link",)
    fieldsets = (
        (None, {"fields": ("title", "slug", "sign", "dimension", "status", "published_at")}),
        ("内容", {"fields": ("summary", "content_html")}),
        ("发布到公众号", {"fields": ("wechat_link",)}),
    )

    @admin.display(description="公众号排版")
    def wechat_link(self, obj):
        if not obj.pk:
            return "先保存文章后可用"
        url = reverse("zodiac:article_wechat", args=[obj.slug])
        return format_html('<a href="{}" target="_blank">复制到公众号 →</a>', url)
