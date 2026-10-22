"""
Django settings for zen project.

这是"星座志"和技术站两个 SEO 内容站共用的一个 Django project：同一套代码、
同一个数据库文件，但通过 Host 头分流到互不相关的 urlconf / admin / 模板 /
静态资源命名空间，两个域名在外部看起来是完全独立的两个网站。见
zen/middleware.py 和 urls_zodiac.py / urls_tech.py。
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


# 上线前必须通过环境变量设置一个新的 DJANGO_SECRET_KEY，不要沿用这个开发默认值。
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-3a#)y0o1+zpe9hukq7umr0(+)z8-x3&29bn58jsp6yqh12di^t',
)

# 本地开发默认开 DEBUG；上线时设置环境变量 DJANGO_DEBUG=False。
DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'

# 上线时把两个站点各自的真实域名都填进来（逗号分隔），例如：
#   DJANGO_ALLOWED_HOSTS="zuoxinzhi.com,www.zuoxinzhi.com,bigywater.com,www.bigywater.com"
ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get(
        'DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost'
    ).split(',') if h.strip()
]


# ---- 站点分流配置 ----
# 星座站 / 技术站各自绑定哪些域名，上线时通过环境变量覆盖。本地开发不用配置，
# 裸 Host（127.0.0.1、localhost）会落到 DEFAULT_SITE。
ZODIAC_HOSTS = [
    h.strip() for h in os.environ.get('ZODIAC_HOSTS', '').split(',') if h.strip()
]
TECH_HOSTS = [
    h.strip() for h in os.environ.get('TECH_HOSTS', '').split(',') if h.strip()
]

# Host 匹配不到 ZODIAC_HOSTS / TECH_HOSTS 时（本地开发、健康检查等）用哪个站点兜底。
DEFAULT_SITE = os.environ.get('DEFAULT_SITE', 'zodiac')

SITE_URLCONF_MAP = {
    'zodiac': 'zen.urls_zodiac',
    'tech': 'zen.urls_tech',
}
# 各站点对应的 app 名（同时也是它 static/templates 目录下的命名空间前缀）。
SITE_APPS = {
    'zodiac': 'zodiac',
    'tech': 'tech',
}
SITE_HOST_MAP = {}
SITE_HOST_MAP.update({h: 'zodiac' for h in ZODIAC_HOSTS})
SITE_HOST_MAP.update({h: 'tech' for h in TECH_HOSTS})


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    'zodiac',
    'tech',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # 必须在 WhiteNoise 之前：既要在静态文件被处理前完成按 Host 的分流拦截，
    # 也要在其它中间件之前把 request.urlconf 定下来。
    'zen.middleware.HostSiteMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'zen.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'zen.wsgi.application'


# Database
# 两个站点共用同一个数据库文件，但各自的数据在各自的 app（zodiac_article /
# 未来的 tech 模型）里，不会互相查询到对方的数据。

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
# 两个 app 的静态文件各自放在 zodiac/static/zodiac/... 和 tech/static/tech/...
# 命名空间下，collectstatic 后互不覆盖；HostSiteMiddleware 另外会拦截跨站点的
# 静态文件请求（比如技术站域名底下探测 /static/zodiac/...）。

STATIC_URL = 'static/'
STATIC_ROOT = Path(os.environ.get('DJANGO_STATIC_ROOT', BASE_DIR / 'staticfiles'))
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}


# ---- 生产环境安全项 ----
# TLS 在 nginx 终止，nginx 通过 X-Forwarded-Proto 告诉 Django 原始请求是不是 https。
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Django 默认是 same-origin,跨站请求不带 referrer,百度统计会提示"referrer被禁用"、
# 拿不到来源。改成浏览器默认值:同站带完整地址,跨站只带域名。
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# 本地开发是 http，这两个只在上线（DJANGO_DEBUG=False）时打开，不然本地登录后台会因为
# cookie 要求 https 而直接失效。
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

# 两个站点各自的域名都要能通过 CSRF 校验提交表单（主要是后台登录/保存）。
CSRF_TRUSTED_ORIGINS = [f'https://{host}' for host in ALLOWED_HOSTS if host not in ('127.0.0.1', 'localhost')]

# http -> https 跳转和 HSTS 头都由 nginx 统一发（静态页和动态页都要有，Django 只管得到
# 动态页，两边都发会让动态页出现重复的头），Django 这层不重复做。includeSubDomains /
# preload 是几乎撤不回的承诺，等两个站点都稳定、确认需要时再手动开。
SILENCED_SYSTEM_CHECKS = ['security.W008', 'security.W004', 'security.W005', 'security.W021']


MAILERS = {
    'default': {
        'BACKEND': 'django.core.mail.backends.console.EmailBackend',
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ---- 技术站（tech app）专属配置 ----
# 下面这些设置只有 tech/*.py 会用到，zodiac 完全不读它们，两边没有交叉依赖。

# 对外发布目录:nginx 的 root 直接指到这里。文章页和列表页全部由程序生成,不要手工放文章进去。
#   - <url>.html、index.html、page/、series/ —— 文章页和首页/分类分页,资源路径已换成
#     带内容哈希的版本,并附带 .gz(nginx gzip_static 直接返回);后台保存文章时由
#     tech/static_site.py 的信号自动写出;
#   - assets/、favicon.ico、site.webmanifest —— 手工维护的站点资源(assets/ 里的文件
#     会由 tech/assets.py 生成带哈希的副本)。
# 文章页和列表页可以用 `manage.py build_static` 从数据库整体重新生成。
PUBLIC_DIR = BASE_DIR / 'public'

# 文章原文的备份镜像(和数据库逐字一致,不做任何改写),数据库的双保险:
# 每次增删改 Article/Series,tech/backup.py 的信号处理器都会把最新内容写到这里。
# sqlite 丢了或者服务器没了,只要这个目录还在,跑一遍 `manage.py import_articles`
# 就能把数据库完整重建回来。
BACKUP_DIR = BASE_DIR / 'backup'

# 技术站的站点身份。域名只在这里写一处,模板、robots.txt、JSON-LD、nginx 之外的代码
# 都从这里读。上线时通过环境变量覆盖成真实域名。
# 注意:每篇文章的 HTML 是存在数据库里的,里面的 canonical / og:url 也带着域名,
# 换域名时要把数据库里的文章一并替换一次,再跑 build_static。
SITE_DOMAIN = os.environ.get('TECH_SITE_DOMAIN', 'bigywater.tech')
SITE_URL = f'https://{SITE_DOMAIN}'
SITE_NAME = os.environ.get('TECH_SITE_NAME', 'bigywater')
SITE_SLOGAN = os.environ.get('TECH_SITE_SLOGAN', '知其然，知其所以然')
# 旧域名。历史文章的生成脚本把它写死在 canonical / og:url / 侧栏品牌里,每次往库里
# 发布新文章都会把旧域名写回去。发布页面时统一换成 SITE_DOMAIN(不改数据库原文),
# 这样即使生成脚本还没改,线上输出也不会带着旧域名。
LEGACY_SITE_DOMAINS = [
    h.strip() for h in os.environ.get('TECH_LEGACY_SITE_DOMAINS', 'bigywater.dev').split(',') if h.strip()
]
SITE_DESCRIPTION = os.environ.get(
    'TECH_SITE_DESCRIPTION',
    '算法与数据结构、Go 内部原理、Kubernetes、MongoDB、Redis、MySQL/InnoDB 等,均来自本机真实实验与真实源码验证。',
)

# 工信部 ICP 备案号和公安联网备案号。备案按域名,只属于 tech 站,只往 tech 的页面里插
# (见 tech/seo.py 的 inject_beian),不会出现在 zodiac 站。
SITE_ICP_NUMBER = os.environ.get('TECH_ICP_NUMBER', '京ICP备2026067502号-1')
SITE_PSB_NUMBER = os.environ.get('TECH_PSB_NUMBER', '京公网安备11010502063487号')
