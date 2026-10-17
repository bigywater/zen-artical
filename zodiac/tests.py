from datetime import date
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from .models import Article

# 测试环境没跑 collectstatic,清单式存储会因为找不到清单报错,换成普通存储
PLAIN_STATIC = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=PLAIN_STATIC)
class BeianFooterTests(TestCase):
    def test_every_page_footer_has_zodiac_own_beian_numbers(self):
        Article.objects.create(
            sign="aries", dimension="today", slug="aries-daily-2026-10-14", title="t",
            status="published", content_html="<p>x</p>",
        )
        for path in ("/", "/aries-daily-2026-10-14/"):
            html = self.client.get(path).content.decode()
            self.assertIn("京ICP备2026067502号-2", html, path)
            self.assertIn("京公网安备11010502063485号", html, path)
            self.assertIn("https://beian.miit.gov.cn/", html, path)
            self.assertIn("beian.mps.gov.cn/#/query/webSearch?code=11010502063485", html, path)
            # 不能串用 tech 站的那一组备案号
            self.assertNotIn("11010502063487", html, path)
            self.assertNotIn("2026067502号-1", html, path)


@override_settings(STORAGES=PLAIN_STATIC)
class BaiduTongjiTests(TestCase):
    HM = "https://hm.baidu.com/hm.js?5e83ba7299810601116511b8779ba816"

    def test_site_pages_have_zodiac_baidu_snippet_but_wechat_copy_page_does_not(self):
        Article.objects.create(
            sign="aries", dimension="today", slug="aries-daily-2026-10-14", title="t",
            status="published", content_html="<p>x</p>",
        )
        for path in ("/", "/aries-daily-2026-10-14/"):
            html = self.client.get(path).content.decode()
            self.assertEqual(html.count(self.HM), 1, path)
            self.assertLess(html.index(self.HM), html.index("</head>"), path)
            self.assertNotIn("1a03f6d448b0ac97e0132d704c567484", html, path)  # 不能串用 tech 站的统计 ID
        self.assertNotIn("hm.baidu.com", self.client.get("/aries-daily-2026-10-14/wechat/").content.decode())


class SitemapTests(TestCase):
    def test_lists_home_and_published_articles_only(self):
        for slug, status in (("aries-daily-2026-10-14", "published"), ("aries-daily-2026-10-15", "draft")):
            Article.objects.create(
                sign="aries", dimension="today", slug=slug, title="t", status=status, content_html="x",
            )
        body = self.client.get("/sitemap.xml").content.decode()
        self.assertIn("<loc>http://testserver/</loc>", body)
        self.assertIn("/aries-daily-2026-10-14/</loc>", body)
        self.assertNotIn("aries-daily-2026-10-15", body)  # 草稿不能进 sitemap


class PeriodBadgeTests(SimpleTestCase):
    def badge(self, dimension, slug, today):
        article = Article(sign="aries", dimension=dimension, slug=slug)
        with patch("zodiac.models.timezone.localdate", return_value=today):
            return article.period_badge

    def test_today(self):
        slug = "aries-daily-2026-10-14"
        self.assertEqual(self.badge("today", slug, date(2026, 10, 14)), "今日")
        self.assertEqual(self.badge("today", slug, date(2026, 10, 15)), "")

    def test_week_covers_monday_to_sunday(self):
        slug = "aries-week-2026-10-12"
        self.assertEqual(self.badge("week", slug, date(2026, 10, 12)), "本周")
        self.assertEqual(self.badge("week", slug, date(2026, 10, 18)), "本周")
        self.assertEqual(self.badge("week", slug, date(2026, 10, 11)), "")
        self.assertEqual(self.badge("week", slug, date(2026, 10, 19)), "")

    def test_next_months_article_is_not_current_until_that_month(self):
        slug = "aries-month-2026-11"
        self.assertEqual(self.badge("month", slug, date(2026, 10, 31)), "")
        self.assertEqual(self.badge("month", slug, date(2026, 11, 1)), "本月")
        self.assertEqual(self.badge("month", slug, date(2026, 11, 30)), "本月")
        self.assertEqual(self.badge("month", slug, date(2026, 12, 1)), "")

    def test_other_dimensions_and_odd_slugs_get_no_badge(self):
        today = date(2026, 10, 14)
        self.assertEqual(self.badge("career", "taurus-career-2026-10", today), "")
        self.assertEqual(self.badge("today", "aries-hello", today), "")
        self.assertEqual(self.badge("week", "aries-week-2026-13-45", today), "")
