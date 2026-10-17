import gzip
import io
import json
import re
import tempfile
from datetime import date
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.db import connection, transaction
from django.test import TestCase, override_settings

from . import assets, demos, seo, static_site
from .models import Article, Series

PAGE = '<html><head><link rel="stylesheet" href="/assets/css/site.css"></head><body>{}</body></html>'


class SiteDirsMixin:
    """把 PUBLIC_DIR / BACKUP_DIR 指到临时目录,PUBLIC_DIR/assets 里放一份样例 css 和图标。"""

    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.public = Path(tmp.name) / 'public'
        self.backup = Path(tmp.name) / 'backup'
        (self.public / 'assets/css').mkdir(parents=True)
        (self.public / 'assets/css/site.css').write_text('body{color:red}', encoding='utf-8')
        (self.public / 'assets/icon.png').write_bytes(b'\x89PNG fake')
        # 列表模板真实引用的资源也要有,「发布页里的引用都存在」这类检查才有意义
        (self.public / 'assets/icons').mkdir()
        (self.public / 'assets/css/md3-shell.css').write_text('.shell{}', encoding='utf-8')
        (self.public / 'assets/icons/favicon.svg').write_text('<svg/>', encoding='utf-8')
        (self.public / 'assets/icons/favicon-192.png').write_bytes(b'\x89PNG 192')
        (self.public / 'assets/icons/apple-touch-icon.png').write_bytes(b'\x89PNG apple')
        (self.public / 'assets/icons/beian-gongan.png').write_bytes(b'\x89PNG beian')  # 备案块里的公安图标
        override = override_settings(PUBLIC_DIR=self.public, BACKUP_DIR=self.backup)
        override.enable()
        self.addCleanup(override.disable)

        self.go = Series.objects.create(key='go', label='Go', color='#00aaff')
        self.redis = Series.objects.create(key='redis', label='Redis', color='#ff3300')

    def make_articles(self, n, series=None, prefix='p'):
        # 信号里的重建挂在 on_commit 上;TestCase 包在事务里,这里显式执行回调
        with self.captureOnCommitCallbacks(execute=True):
            for i in range(n):
                Article.objects.create(
                    title=f'{prefix}{i}', url=f'{prefix}{i}.html', series=series or self.go,
                    date=date(2026, 1, 1), description='d', content_html=PAGE.format(f'{prefix}{i}'),
                )

    def hashed_css(self):
        return assets.fingerprint()['/assets/css/site.css']


class StaticSiteTests(SiteDirsMixin, TestCase):
    def test_saving_article_publishes_page_and_list_pages(self):
        self.make_articles(1)
        self.assertIn('p0', (self.public / 'p0.html').read_text(encoding='utf-8'))
        index = (self.public / 'index.html').read_text(encoding='utf-8')
        self.assertIn('<title>知其然，知其所以然</title>', index)
        self.assertIn('href="/p0.html"', index)
        self.assertTrue((self.public / 'series/go/index.html').exists())
        self.assertTrue((self.public / 'series/redis/index.html').exists())  # 空分类也有页面

    def test_canonical_points_to_each_list_page_itself(self):
        self.make_articles(static_site.PAGE_SIZE + 1)
        site = settings.SITE_URL
        self.assertIn(f'rel="canonical" href="{site}/"', (self.public / 'index.html').read_text(encoding='utf-8'))
        page2 = (self.public / 'page/2/index.html').read_text(encoding='utf-8')
        self.assertIn(f'rel="canonical" href="{site}/page/2/"', page2)
        series = (self.public / 'series/go/index.html').read_text(encoding='utf-8')
        self.assertIn(f'rel="canonical" href="{site}/series/go/"', series)

    def test_pagination_files_and_links(self):
        self.make_articles(static_site.PAGE_SIZE + 1)
        self.assertTrue((self.public / 'page/2/index.html').exists())
        self.assertIn('href="/page/2/"', (self.public / 'index.html').read_text(encoding='utf-8'))
        self.assertTrue((self.public / 'series/go/page/2/index.html').exists())

    def test_stale_pages_are_removed_when_articles_shrink(self):
        self.make_articles(static_site.PAGE_SIZE + 1)
        self.assertTrue((self.public / 'page/2/index.html.gz').exists())
        with self.captureOnCommitCallbacks(execute=True):
            Article.objects.filter(url='p0.html').delete()
        self.assertFalse((self.public / 'page').exists())
        self.assertFalse((self.public / 'p0.html').exists())
        self.assertFalse((self.public / 'p0.html.gz').exists())
        self.assertFalse((self.backup / 'p0.html').exists())

    def test_deleting_series_removes_its_pages(self):
        self.make_articles(1, series=self.redis, prefix='r')
        self.assertTrue((self.public / 'series/redis/index.html').exists())
        with self.captureOnCommitCallbacks(execute=True):
            Article.objects.all().delete()
            self.redis.delete()
        self.assertFalse((self.public / 'series/redis').exists())

    def test_renaming_url_removes_old_files(self):
        self.make_articles(1)
        with self.captureOnCommitCallbacks(execute=True):
            article = Article.objects.get(url='p0.html')
            article.url = 'renamed.html'
            article.save()
        self.assertTrue((self.public / 'renamed.html.gz').exists())
        for base in (self.public, self.backup):
            self.assertFalse((base / 'p0.html').exists())
        self.assertFalse((self.public / 'p0.html.gz').exists())

    def test_many_changes_in_one_transaction_rebuild_once(self):
        with mock.patch.object(static_site, 'rebuild_lists', wraps=static_site.rebuild_lists) as rebuild:
            with self.captureOnCommitCallbacks(execute=True):
                for i in range(5):
                    Article.objects.create(
                        title=f'b{i}', url=f'b{i}.html', series=self.go, date=date(2026, 1, 1),
                        description='d', content_html='x',
                    )
        self.assertEqual(rebuild.call_count, 1)

    def test_rolled_back_transaction_does_not_wedge_later_rebuilds(self):
        try:
            with transaction.atomic():
                Article.objects.create(
                    title='x', url='x.html', series=self.go, date=date(2026, 1, 1),
                    description='d', content_html='x',
                )
                raise RuntimeError
        except RuntimeError:
            pass
        self.make_articles(1)
        self.assertIn('href="/p0.html"', (self.public / 'index.html').read_text(encoding='utf-8'))

    def test_rebuild_failure_does_not_break_saving(self):
        with mock.patch.object(static_site, 'rebuild_lists', side_effect=OSError('disk full')):
            with self.assertLogs('tech.static_site', level='ERROR'):
                self.make_articles(1)
        self.assertTrue(Article.objects.filter(url='p0.html').exists())

    def test_no_temp_files_left_behind(self):
        self.make_articles(3)
        self.assertEqual(list(self.public.rglob('.tmp-*')) + list(self.backup.rglob('.tmp-*')), [])


class BuildStaticTests(SiteDirsMixin, TestCase):
    def test_build_static_regenerates_everything(self):
        self.make_articles(2)
        for base in (self.public, self.backup):
            for path in base.glob('*.html*'):
                path.unlink()
        for path in self.public.rglob('index.html*'):
            path.unlink()
        call_command('build_static', stdout=io.StringIO())
        self.assertTrue((self.public / 'p0.html').exists())
        self.assertTrue((self.public / 'index.html.gz').exists())
        self.assertTrue((self.backup / 'p0.html').exists())
        self.assertTrue((self.backup / 'manifest.json').exists())

    def test_backup_dir_can_restore_database(self):
        # 灾难恢复:清空数据库,只靠备份目录(文章原文 + manifest.json)重建
        self.make_articles(3)
        expected = {a.url: (a.title, a.series.key, a.content_html) for a in Article.objects.select_related('series')}
        # 用裸 SQL 清库来模拟"数据库文件丢了":走 ORM 的 delete() 会触发信号,连备份目录一起删掉
        with connection.cursor() as cursor:
            cursor.execute(f'DELETE FROM {Article._meta.db_table}')
        self.assertEqual(Article.objects.count(), 0)
        call_command('import_articles', dir=str(self.backup), stdout=io.StringIO())
        restored = {a.url: (a.title, a.series.key, a.content_html) for a in Article.objects.select_related('series')}
        self.assertEqual(restored, expected)

    def test_prune_only_after_full_rebuild(self):
        self.make_articles(1)
        old = self.hashed_css()
        (self.public / 'assets/css/site.css').write_text('body{color:blue}', encoding='utf-8')
        call_command('build_static', stdout=io.StringIO())
        new = self.hashed_css()
        self.assertNotEqual(old, new)
        self.assertFalse((self.public / old.lstrip('/')).exists())          # 旧版本已清理
        self.assertFalse((self.public / (old.lstrip('/') + '.gz')).exists())
        self.assertIn(new, (self.public / 'p0.html').read_text(encoding='utf-8'))  # 页面已换成新哈希


class AssetFingerprintTests(SiteDirsMixin, TestCase):
    def test_hashed_copy_is_written_with_gz_for_text_only(self):
        mapping = assets.fingerprint()
        css = mapping['/assets/css/site.css']
        self.assertRegex(css, r'^/assets/css/site\.[0-9a-f]{8}\.css$')
        self.assertEqual((self.public / css.lstrip('/')).read_text(encoding='utf-8'), 'body{color:red}')
        self.assertTrue((self.public / (css.lstrip('/') + '.gz')).exists())
        png = mapping['/assets/icon.png']
        self.assertTrue((self.public / png.lstrip('/')).exists())
        self.assertFalse((self.public / (png.lstrip('/') + '.gz')).exists())   # png 不预压缩

    def test_hash_is_stable_and_changes_with_content(self):
        first = assets.fingerprint()
        self.assertEqual(assets.fingerprint(), first)                          # 幂等
        (self.public / 'assets/css/site.css').write_text('body{color:blue}', encoding='utf-8')
        self.assertNotEqual(assets.fingerprint()['/assets/css/site.css'], first['/assets/css/site.css'])

    def test_hashed_copies_are_not_fingerprinted_again(self):
        assets.fingerprint()
        assets.fingerprint()
        self.assertEqual(len(assets.fingerprint()), 7)   # 7 个源文件,没有把哈希副本再当成源文件

    def test_rewrite_only_touches_known_assets(self):
        mapping = assets.fingerprint()
        html = '<link href="/assets/css/site.css"> 提到 /assets/other.css 和 /assets/css/site.css.'
        out = assets.rewrite(html, mapping)
        self.assertIn(f'href="{mapping["/assets/css/site.css"]}"', out)
        self.assertIn('/assets/other.css', out)            # 不存在的路径原样保留
        self.assertIn('/assets/css/site.css.', out)        # 句末带标点的不是精确路径,不动

    def test_missing_assets_dir_is_fine(self):
        import shutil
        shutil.rmtree(self.public / 'assets')
        self.assertEqual(assets.fingerprint(), {})
        self.assertEqual(assets.rewrite('<a href="/assets/x.css">', {}), '<a href="/assets/x.css">')


class PublishedFilesTests(SiteDirsMixin, TestCase):
    def test_published_page_uses_hashed_assets_but_backup_stays_raw(self):
        self.make_articles(1)
        raw = PAGE.format('p0')
        self.assertEqual((self.backup / 'p0.html').read_text(encoding='utf-8'), raw)      # 备份 = 原文
        published = (self.public / 'p0.html').read_text(encoding='utf-8')
        self.assertNotEqual(published, raw)
        self.assertIn(self.hashed_css(), published)
        self.assertEqual(Article.objects.get(url='p0.html').content_html, raw)            # 数据库也没变

    def test_gz_matches_plain_file(self):
        self.make_articles(static_site.PAGE_SIZE + 1)
        checked = 0
        for gz in self.public.rglob('*.gz'):
            plain = gz.with_name(gz.name[:-3])
            self.assertEqual(gzip.decompress(gz.read_bytes()), plain.read_bytes(), gz)
            checked += 1
        self.assertGreater(checked, 5)

    def test_every_asset_reference_in_published_html_exists(self):
        self.make_articles(static_site.PAGE_SIZE + 1)
        for html in list(self.public.rglob('*.html')):
            for ref in re.findall(r'/assets/[A-Za-z0-9_./-]+', html.read_text(encoding='utf-8')):
                self.assertTrue((self.public / ref.lstrip('/')).exists(), f'{html.name} 引用了不存在的 {ref}')


class ListViewFallbackTests(SiteDirsMixin, TestCase):
    """nginx 找不到静态文件时回落到 Django:内容要和静态页一致,非规范路径要 301。"""

    def setUp(self):
        super().setUp()
        for i in range(static_site.PAGE_SIZE + 1):
            Article.objects.create(
                title=f't{i}', url=f't{i}.html', series=self.go, date=date(2026, 1, 1),
                description='d', content_html='x',
            )

    def test_dynamic_render_matches_static_render(self):
        from django.template.loader import render_to_string
        expected = seo.inject_baidu(seo.inject_beian(render_to_string('tech/article_list.html', static_site.build_list_context('go', 2))))
        self.assertEqual(self.client.get('/series/go/page/2/').content.decode(), expected)

    def test_non_canonical_paths_redirect(self):
        self.assertEqual(self.client.get('/page/1/')['Location'], '/')
        self.assertEqual(self.client.get('/series/go/page/1/')['Location'], '/series/go/')
        self.assertEqual(self.client.get('/page/999/')['Location'], '/page/2/')

    def test_unknown_series_is_404(self):
        self.assertEqual(self.client.get('/series/nope/').status_code, 404)

    def test_article_detail_still_served(self):
        r = self.client.get('/t0.html')
        self.assertEqual((r.status_code, r.content), (200, b'x'))


class BeianTests(SiteDirsMixin, TestCase):
    ICP = '京ICP备2026067502号-1'
    PSB = '京公网安备11010502063487号'

    def test_injected_before_body_end_with_both_numbers_and_links(self):
        html = seo.inject_beian(PAGE.format('x'))
        self.assertIn(self.ICP, html)
        self.assertIn(self.PSB, html)
        self.assertIn('https://beian.miit.gov.cn/', html)
        self.assertIn('https://beian.mps.gov.cn/#/query/webSearch?code=11010502063487', html)
        self.assertLess(html.index('site-beian'), html.index('</body>'))

    def test_idempotent_and_leaves_pages_without_body_alone(self):
        once = seo.inject_beian(PAGE.format('x'))
        self.assertEqual(seo.inject_beian(once), once)
        self.assertEqual(seo.inject_beian('x'), 'x')

    def test_skipped_when_numbers_not_configured(self):
        with override_settings(SITE_ICP_NUMBER='', SITE_PSB_NUMBER=''):
            self.assertEqual(seo.inject_beian(PAGE.format('x')), PAGE.format('x'))

    def test_published_article_and_list_pages_carry_it(self):
        self.make_articles(1)
        for path in ('index.html', 'p0.html'):
            html = (self.public / path).read_text(encoding='utf-8')
            self.assertIn(self.ICP, html, path)
            self.assertIn(self.PSB, html, path)
            # 图标路径也被换成了带哈希的版本(和其他静态资源一样享受长期缓存)
            self.assertRegex(html, r'/assets/icons/beian-gongan\.[0-9a-f]{8}\.png', path)


class SeoTests(SiteDirsMixin, TestCase):
    def jsonld(self, path):
        html = (self.public / path).read_text(encoding='utf-8')
        blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
        self.assertEqual(len(blocks), 1, f'{path} 应该恰好有一段 JSON-LD')
        return json.loads(blocks[0])

    def meta(self, path, name):
        html = (self.public / path).read_text(encoding='utf-8')
        return re.search(rf'<meta (?:name|property)="{name}" content="([^"]*)"', html).group(1)

    def test_home_keeps_slogan_title_and_is_a_website(self):
        self.make_articles(1)
        html = (self.public / 'index.html').read_text(encoding='utf-8')
        self.assertIn(f'<title>{settings.SITE_SLOGAN}</title>', html)
        data = self.jsonld('index.html')
        self.assertEqual((data['@type'], data['url']), ('WebSite', settings.SITE_URL + '/'))

    def test_every_list_page_has_its_own_title_and_description(self):
        self.make_articles(static_site.PAGE_SIZE + 1)
        self.make_articles(1, series=self.redis, prefix='r')
        files = ['index.html', 'page/2/index.html', 'series/go/index.html', 'series/go/page/2/index.html', 'series/redis/index.html']
        titles = [re.search(r'<title>(.*?)</title>', (self.public / f).read_text(encoding='utf-8')).group(1) for f in files]
        descs = [self.meta(f, 'description') for f in files]
        self.assertEqual(len(set(titles)), len(files), titles)
        self.assertEqual(len(set(descs)), len(files), descs)
        self.assertIn('Go', titles[2])
        self.assertIn('第 2 页', titles[1])
        for f, title in zip(files, titles):     # og:title / twitter:title 和 <title> 一致
            self.assertEqual(self.meta(f, 'og:title'), title)
            self.assertEqual(self.meta(f, 'twitter:title'), title)

    def test_series_page_is_a_collection_with_absolute_item_urls(self):
        self.make_articles(3)
        data = self.jsonld('series/go/index.html')
        self.assertEqual(data['@type'], 'CollectionPage')
        items = data['mainEntity']['itemListElement']
        self.assertEqual([i['position'] for i in items], [1, 2, 3])
        self.assertTrue(all(i['url'].startswith(settings.SITE_URL + '/') for i in items))

    def test_article_page_has_techarticle_and_breadcrumb(self):
        self.make_articles(1)
        graph = self.jsonld('p0.html')['@graph']
        article = next(n for n in graph if n['@type'] == 'TechArticle')
        crumbs = next(n for n in graph if n['@type'] == 'BreadcrumbList')['itemListElement']
        self.assertEqual(article['url'], f'{settings.SITE_URL}/p0.html')
        self.assertEqual((article['datePublished'], article['articleSection']), ('2026-01-01', 'Go'))
        self.assertEqual([c['name'] for c in crumbs], ['首页', 'Go', 'p0'])
        self.assertEqual(crumbs[1]['item'], f'{settings.SITE_URL}/series/go/')

    def test_jsonld_is_only_added_to_published_pages_not_to_backup_or_db(self):
        self.make_articles(1)
        self.assertNotIn('ld+json', (self.backup / 'p0.html').read_text(encoding='utf-8'))
        self.assertNotIn('ld+json', Article.objects.get(url='p0.html').content_html)

    def test_jsonld_is_not_duplicated_and_is_script_safe(self):
        with self.captureOnCommitCallbacks(execute=True):
            Article.objects.create(
                title='标题里有 </script><b>', url='evil.html', series=self.go, date=date(2026, 1, 1),
                description='d', content_html=PAGE.format('x'),
            )
        html = (self.public / 'evil.html').read_text(encoding='utf-8')
        html = html.replace(seo.BAIDU_TONGJI_SNIPPET, '')   # 数 </script> 的个数时去掉统计脚本
        self.assertEqual(html.count('application/ld+json'), 1)
        self.assertEqual(html.count('</script>'), 1)          # 标题里的 </script> 已被转义,没有提前结束标签
        self.assertEqual(seo.inject_jsonld(html, '{}'), html)  # 已经有了就不再加
        self.assertEqual(self.jsonld('evil.html')['@graph'][0]['headline'], '标题里有 </script><b>')

    def test_dynamic_fallback_article_page_also_has_jsonld(self):
        Article.objects.create(title='t', url='t.html', series=self.go, date=date(2026, 1, 1),
                               description='d', content_html=PAGE.format('x'))
        self.assertIn('application/ld+json', self.client.get('/t.html').content.decode())

    def test_sitemap_lists_home_series_and_articles(self):
        self.make_articles(2)
        body = self.client.get('/sitemap.xml').content.decode()
        # 不管请求带什么 Host,sitemap 里都是规范域名
        self.assertNotIn('testserver', body)
        self.assertIn(f'<loc>{settings.SITE_URL}/</loc>', body)
        locs = re.findall(r'<loc>https?://[^/]+(/[^<]*)</loc>', body)
        self.assertIn('/', locs)
        self.assertIn('/series/go/', locs)
        self.assertIn('/series/redis/', locs)
        self.assertIn('/p0.html', locs)
        self.assertNotIn('/page/2/', locs)

    def test_robots_points_to_sitemap_and_hides_admin(self):
        body = self.client.get('/robots.txt').content.decode()
        self.assertIn('Disallow: /admin/', body)
        self.assertIn(f'Sitemap: {settings.SITE_URL}/sitemap.xml', body)


STEP_DEMO = '<div class="demo"><button>上一步</button><button>下一步</button></div><script>var x=1;</script>'
MANUAL_DEMO = '<div class="demo"><button>5 个分片</button></div><script>render();</script>'
LANG_TABS = '<div class="lang-tabs"><button>Python</button><button>Java</button><button>Go</button></div><script>tabs();</script>'


class DemoDetectionTests(TestCase):
    def test_step_buttons_with_script_is_a_demo(self):
        self.assertTrue(demos.has_animation_demo('<button>▶ 自动播放</button><script>go()</script>'))
        self.assertTrue(demos.has_animation_demo(STEP_DEMO))

    def test_demo_block_with_script_is_a_demo_even_without_step_buttons(self):
        self.assertTrue(demos.has_animation_demo(MANUAL_DEMO))

    def test_code_language_tabs_are_not_a_demo(self):
        self.assertFalse(demos.has_animation_demo(LANG_TABS))

    def test_mentioning_demo_or_simulation_is_not_a_demo(self):
        self.assertFalse(demos.has_animation_demo('<p>用代码模拟一次,顺带演示了一个场景</p>'))

    def test_buttons_or_container_without_script_is_not_a_demo(self):
        self.assertFalse(demos.has_animation_demo('<div class="demo"><button>下一步</button></div>'))
        self.assertFalse(demos.has_animation_demo('<script></script><button>下一步</button>'))   # 空脚本不算


class TagDemosCommandTests(SiteDirsMixin, TestCase):
    def make(self, url, html, tags='a,b'):
        with self.captureOnCommitCallbacks(execute=True):
            return Article.objects.create(title=url, url=url, series=self.go, date=date(2026, 1, 1),
                                          description='d', content_html=html, tags=tags)

    def run_cmd(self, *args):
        out = io.StringIO()
        call_command('tag_demos', *args, stdout=out)
        return out.getvalue()

    def test_tags_only_articles_with_demos_and_keeps_existing_tags_in_order(self):
        self.make('demo.html', PAGE.format(STEP_DEMO), tags='x,y')
        self.make('lang.html', PAGE.format(LANG_TABS))
        self.make('plain.html', PAGE.format('nothing'))
        self.run_cmd()
        self.assertEqual(Article.objects.get(url='demo.html').tags, f'x,y,{demos.TAG}')
        self.assertEqual(Article.objects.get(url='lang.html').tags, 'a,b')
        self.assertEqual(Article.objects.get(url='plain.html').tags, 'a,b')

    def test_is_idempotent(self):
        self.make('demo.html', PAGE.format(STEP_DEMO))
        self.run_cmd()
        self.assertIn('原本就有 1 篇', self.run_cmd())
        self.assertEqual(Article.objects.get(url='demo.html').tags.count(demos.TAG), 1)

    def test_handles_articles_without_any_tags(self):
        self.make('demo.html', PAGE.format(STEP_DEMO), tags='')
        self.run_cmd()
        self.assertEqual(Article.objects.get(url='demo.html').tags, demos.TAG)

    def test_dry_run_writes_nothing(self):
        self.make('demo.html', PAGE.format(STEP_DEMO))
        self.assertIn('demo.html', self.run_cmd('--dry-run'))
        self.assertEqual(Article.objects.get(url='demo.html').tags, 'a,b')

    def test_does_not_touch_updated_at_and_republishes_pages(self):
        article = self.make('demo.html', PAGE.format(STEP_DEMO))
        before = Article.objects.get(pk=article.pk).updated_at
        self.run_cmd()
        self.assertEqual(Article.objects.get(pk=article.pk).updated_at, before)
        self.assertIn(demos.TAG, (self.public / 'index.html').read_text(encoding='utf-8'))        # 列表卡片上的标签
        self.assertIn(demos.TAG, (self.public / 'demo.html').read_text(encoding='utf-8'))         # JSON-LD keywords
        manifest = json.loads((self.backup / 'manifest.json').read_text(encoding='utf-8'))
        self.assertIn(demos.TAG, manifest['articles'][0]['tags'])

    def test_skips_article_changed_by_someone_else_meanwhile(self):
        article = self.make('demo.html', PAGE.format(STEP_DEMO))
        real_update = Article.objects.filter

        def racy_filter(*a, **kw):
            Article.objects.all().filter(pk=article.pk).update(tags='changed-elsewhere')   # 别的进程抢先改了(走 QuerySet,不经过被替换的 manager.filter)
            return real_update(*a, **kw)
        with mock.patch.object(Article.objects, 'filter', side_effect=racy_filter):
            out = self.run_cmd()
        self.assertIn('已跳过', out)
        self.assertEqual(Article.objects.get(pk=article.pk).tags, 'changed-elsewhere')

    def test_warns_about_tag_without_demo_but_does_not_remove_it(self):
        self.make('odd.html', PAGE.format('nothing'), tags=f'a,{demos.TAG}')
        self.assertIn('没有检测到演示组件', self.run_cmd())
        self.assertIn(demos.TAG, Article.objects.get(url='odd.html').tags)


class LegacyDomainAndOrphanTests(SiteDirsMixin, TestCase):
    LEGACY_PAGE = ('<html><head><link rel="canonical" href="https://bigywater.dev/old.html">'
                   '<meta property="og:site_name" content="bigywater.dev"></head>'
                   '<body><a class="md3-topbar-brand" href="/">bigywater.dev</a></body></html>')

    def test_published_page_uses_current_domain_but_backup_and_db_keep_the_original(self):
        with self.captureOnCommitCallbacks(execute=True):
            Article.objects.create(title='t', url='old.html', series=self.go, date=date(2026, 1, 1),
                                   description='d', content_html=self.LEGACY_PAGE)
        published = (self.public / 'old.html').read_text(encoding='utf-8')
        self.assertNotIn('bigywater.dev', published)
        self.assertIn(f'href="{settings.SITE_URL}/old.html"', published)
        self.assertIn('bigywater.dev', (self.backup / 'old.html').read_text(encoding='utf-8'))
        self.assertIn('bigywater.dev', Article.objects.get(url='old.html').content_html)
        self.assertNotIn('bigywater.dev', gzip.decompress((self.public / 'old.html.gz').read_bytes()).decode('utf-8'))

    def test_dynamic_fallback_also_uses_current_domain(self):
        Article.objects.create(title='t', url='old.html', series=self.go, date=date(2026, 1, 1),
                               description='d', content_html=self.LEGACY_PAGE)
        self.assertNotIn('bigywater.dev', self.client.get('/old.html').content.decode())

    def test_build_static_removes_files_of_articles_no_longer_in_the_database(self):
        self.make_articles(2)
        with connection.cursor() as cursor:      # 裸 SQL 删除:不触发信号,模拟整库替换
            cursor.execute(f"DELETE FROM {Article._meta.db_table} WHERE url = 'p1.html'")
        self.assertTrue((self.public / 'p1.html').exists())
        out = io.StringIO()
        call_command('build_static', stdout=out)
        for base in (self.public, self.backup):
            self.assertFalse((base / 'p1.html').exists(), base)
        self.assertFalse((self.public / 'p1.html.gz').exists())
        self.assertTrue((self.public / 'p0.html').exists())
        self.assertTrue((self.public / 'index.html').exists())          # 首页不是文章,不能被当孤儿删掉
        self.assertTrue((self.backup / 'manifest.json').exists())
        self.assertIn('残留文件 3 个', out.getvalue())                    # p1.html + p1.html.gz + backup 里的 p1.html

    def test_orphan_cleanup_leaves_everything_else_alone(self):
        self.make_articles(1)
        (self.public / 'favicon.ico').write_bytes(b'x')
        (self.public / 'notes.txt').write_text('keep', encoding='utf-8')
        call_command('build_static', stdout=io.StringIO())
        self.assertTrue((self.public / 'favicon.ico').exists())
        self.assertTrue((self.public / 'notes.txt').exists())
        self.assertTrue((self.public / 'assets/css/site.css').exists())


class PaginationWindowTests(SiteDirsMixin, TestCase):
    def test_window_is_at_most_ten_contiguous_pages_containing_current(self):
        for total in (1, 2, 9, 10, 11, 12, 29, 100, 10000):
            for current in sorted({1, 2, 3, 5, 6, 7, total // 2 or 1, total - 1 or 1, total}):
                if current > total:
                    continue
                w = static_site.page_window(current, total)
                self.assertLessEqual(len(w), 10, (current, total))
                self.assertIn(current, w, (current, total))
                self.assertEqual(w, list(range(w[0], w[0] + len(w))), (current, total))     # 连续
                self.assertTrue(1 <= w[0] and w[-1] <= total, (current, total))
                self.assertEqual(len(w), min(total, 10), (current, total))                   # 页数够多时总是满 10 个

    def test_window_slides_and_sticks_to_edges(self):
        self.assertEqual(static_site.page_window(1, 29), list(range(1, 11)))
        self.assertEqual(static_site.page_window(5, 29), list(range(1, 11)))
        self.assertEqual(static_site.page_window(6, 29), list(range(2, 12)))     # 当前页排第 5 位
        self.assertEqual(static_site.page_window(15, 29), list(range(11, 21)))
        self.assertEqual(static_site.page_window(29, 29), list(range(20, 30)))
        self.assertEqual(static_site.page_window(5000, 10000), list(range(4996, 5006)))

    def test_rendered_pagination_never_lists_all_pages(self):
        with mock.patch.object(static_site, 'PAGE_SIZE', 1):
            self.make_articles(30)                                   # 每页 1 篇 -> 30 页
        html = (self.public / 'page/15/index.html').read_text(encoding='utf-8')
        nums = [int(n) for n in re.findall(r'<a class="page-btn(?: active)?" href="[^"]*"(?: aria-current="page")?>(\d+)</a>', html)]
        self.assertEqual(nums, list(range(11, 21)))                  # 只有 10 个页码
        self.assertIn('aria-current="page">15<', html)
        self.assertIn('rel="prev" href="/page/14/"', html)
        self.assertIn('rel="next" href="/page/16/"', html)
        self.assertIn('title="第一页"', html)
        self.assertIn('href="/page/30/" title="最后一页', html)      # 首末页跳转

    def test_first_and_last_page_disable_the_matching_arrows(self):
        with mock.patch.object(static_site, 'PAGE_SIZE', 1):
            self.make_articles(30)
        first = (self.public / 'index.html').read_text(encoding='utf-8')
        self.assertEqual(first.count('page-btn disabled'), 2)         # « 和 ‹
        last = (self.public / 'page/30/index.html').read_text(encoding='utf-8')
        self.assertEqual(last.count('page-btn disabled'), 2)          # › 和 »

    def test_short_lists_have_no_first_last_arrows_and_no_pagination_for_one_page(self):
        with mock.patch.object(static_site, 'PAGE_SIZE', 1):
            self.make_articles(3)
        html = (self.public / 'page/2/index.html').read_text(encoding='utf-8')
        self.assertNotIn('&laquo;', html)
        self.assertNotIn('&raquo;', html)
        self.assertEqual(len(re.findall(r'class="page-btn(?: active)?" href', html)), 3)
        self.make_articles(0)
        one = static_site.build_list_context('redis', 1)              # 空分类只有 1 页
        self.assertEqual(one['page_window'], [1])


class BaiduTongjiTests(TestCase):
    PAGE = '<html><head><title>x</title></head><body>b</body></html>'

    def test_snippet_inserted_verbatim_once_before_head_end(self):
        html = seo.inject_baidu(self.PAGE)
        self.assertIn(seo.BAIDU_TONGJI_SNIPPET + '</head>', html)
        self.assertIn('https://hm.baidu.com/hm.js?1a03f6d448b0ac97e0132d704c567484', html)
        self.assertEqual(seo.inject_baidu(html), html)  # 重复调用不会插第二份

    def test_page_without_head_is_unchanged(self):
        self.assertEqual(seo.inject_baidu('plain'), 'plain')
