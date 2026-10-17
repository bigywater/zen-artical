"""
ROOT_URLCONF 只在 HostSiteMiddleware 认不出 Host（本地开发裸访问 127.0.0.1、
健康检查等场景）时才会被用到——正常请求都会被中间件按 Host 换成
urls_zodiac / urls_tech，两个真实站点互不相关。
"""
from django.conf import settings

if settings.DEFAULT_SITE == "tech":
    from zen.urls_tech import urlpatterns
else:
    from zen.urls_zodiac import urlpatterns
