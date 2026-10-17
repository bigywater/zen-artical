"""
SEO:结构化数据(JSON-LD)和列表页的 title / description。

文章页的 canonical、og:*、description 是文章自己 HTML 里带的(存在数据库里),
这里补的是它没有的部分,并且都在"发布"那一刻生成,不改数据库里的原文:
  - 文章页:TechArticle + BreadcrumbList 结构化数据(发布日期、所属系列、面包屑);
  - 列表页:每个分类、每一页有自己的 title / description,首页是 WebSite、其余是 CollectionPage。
"""
import json
import re
from datetime import date

from django.conf import settings
from django.urls import reverse
from django.utils.html import escape

TAIL = '每个结论都来自本机真实实验与真实源码验证。'


def normalize_domain(html):
    """把页面里残留的旧域名换成当前域名(发布时做,数据库和备份里仍是原文)。"""
    for legacy in settings.LEGACY_SITE_DOMAINS:
        html = html.replace(legacy, settings.SITE_DOMAIN)
    return html


def refresh_nav_counts(html, counts):
    """把文章页侧栏里的文章数换成当前库里的真实数字(发布时做,数据库里的原文不改)。

    侧栏的 "全部文章" 与各系列的数字是生成文章时写进 HTML 的,之后再加文章,老页面里的数字就过期了
    (同一个站点里不同文章页显示不同的总数,和首页对不上)。counts 是 {系列 key: 篇数},
    "全部文章" 取它们的和。页面里没有这些侧栏项时原样返回。
    """
    total = sum(counts.values())
    html = re.sub(r'(全部文章</span>\s*<span class="md3-drawer-count">)\d+', lambda m: m.group(1) + str(total), html, count=1)
    for key, n in counts.items():
        html = re.sub(r'(href="/\?series=%s"[^>]*>(?:(?!</a>).)*?md3-drawer-count">)\d+' % re.escape(key),
                      lambda m: m.group(1) + str(n), html, count=1, flags=re.S)
    return html


def _dump(data):
    # 嵌进 <script> 里:把 "</" 转义掉,标题里出现 </script> 也不会提前结束标签
    return json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')


def _abs(path):
    return settings.SITE_URL + path


def _as_date(value):
    # 刚从 manifest / 表单赋值、还没从数据库重新读出来的实例,date 字段可能还是 'YYYY-MM-DD' 字符串
    return value if isinstance(value, date) else date.fromisoformat(value)


def _website():
    return {'@type': 'WebSite', 'name': settings.SITE_NAME, 'url': _abs('/')}


def article_jsonld(article):
    url = _abs('/' + article.url)
    series = article.series
    published = _as_date(article.date)
    org = {'@type': 'Organization', 'name': settings.SITE_NAME, 'url': _abs('/')}
    node = {
        '@type': 'TechArticle',
        '@id': url + '#article',
        'mainEntityOfPage': {'@type': 'WebPage', '@id': url},
        'headline': article.title,
        'description': article.description,
        'url': url,
        'inLanguage': 'zh-CN',
        'datePublished': published.isoformat(),
        'dateModified': max(published, article.updated_at.date()).isoformat(),
        'articleSection': series.label,
        'author': org,
        'publisher': org,
        'isPartOf': _website(),
    }
    if article.tag_list():
        node['keywords'] = ', '.join(article.tag_list())
    breadcrumb = {
        '@type': 'BreadcrumbList',
        'itemListElement': [
            {'@type': 'ListItem', 'position': 1, 'name': '首页', 'item': _abs('/')},
            {'@type': 'ListItem', 'position': 2, 'name': series.label,
             'item': _abs(reverse('series_list', args=[series.key]))},
            {'@type': 'ListItem', 'position': 3, 'name': article.title, 'item': url},
        ],
    }
    return _dump({'@context': 'https://schema.org', '@graph': [node, breadcrumb]})


def inject_jsonld(html, payload):
    """把 JSON-LD 放进 <head> 结尾。页面自己已经带了结构化数据就不重复加。"""
    if 'application/ld+json' in html or '</head>' not in html:
        return html
    return html.replace('</head>', f'<script type="application/ld+json">{payload}</script></head>', 1)


BAIDU_TONGJI_SNIPPET = """<script>
var _hmt = _hmt || [];
(function() {
  var hm = document.createElement("script");
  hm.src = "https://hm.baidu.com/hm.js?1a03f6d448b0ac97e0132d704c567484";
  var s = document.getElementsByTagName("script")[0]; 
  s.parentNode.insertBefore(hm, s);
})();
</script>
"""


def inject_baidu(html):
    """把百度统计代码原样放进 <head> 结尾。页面里没有 </head> 或已经有了就原样返回。"""
    if '</head>' not in html or 'hm.baidu.com/hm.js' in html:
        return html
    return html.replace('</head>', BAIDU_TONGJI_SNIPPET + '</head>', 1)


def inject_beian(html):
    """在页面底部(</body> 之前)放工信部备案号和公安联网备案号,各自链接到官方查询页。

    样式全部写在行内,不依赖任何 css 文件,文章页和列表页都能用。颜色继承页面、只降一点透明度,
    深浅色主题下都协调。号码没配置就不插;页面里没有 </body>(比如测试里的极简页面)也原样返回。
    """
    icp, psb = settings.SITE_ICP_NUMBER, settings.SITE_PSB_NUMBER
    if (not icp and not psb) or 'site-beian' in html:
        return html
    end = html.rfind('</body>')
    if end == -1:
        return html
    link_style = 'color:inherit;text-decoration:none'
    parts = []
    if icp:
        parts.append(
            f'<a href="https://beian.miit.gov.cn/" target="_blank" rel="noopener noreferrer" '
            f'style="{link_style}">{escape(icp)}</a>'
        )
    if psb:
        code = re.sub(r'\D', '', psb)
        parts.append(
            f'<a href="https://beian.mps.gov.cn/#/query/webSearch?code={code}" target="_blank" '
            f'rel="noopener noreferrer" style="{link_style}">'
            f'<img src="/assets/icons/beian-gongan.png" alt="" width="14" height="15" '
            f'style="vertical-align:-3px;margin-right:4px">{escape(psb)}</a>'
        )
    block = (
        '<div class="site-beian" style="padding:20px 16px 32px;text-align:center;'
        'font-size:12px;line-height:1.9;color:inherit;opacity:.72">'
        + '<span style="margin:0 8px"></span>'.join(parts)
        + '</div>\n'
    )
    return html[:end] + block + html[end:]


def list_meta(series_key, label, count, page):
    """列表页的 title 和 description:每个分类、每一页都不一样,避免被搜索引擎当成重复页面。"""
    slogan = settings.SITE_SLOGAN
    number = page.number
    if series_key == 'all':
        if number == 1:
            return slogan, settings.SITE_DESCRIPTION
        title = f'全部文章 · 第 {number} 页 · {slogan}'
        description = f'全部 {count} 篇文章,第 {number} 页(共 {page.paginator.num_pages} 页)。{TAIL}'
        return title, description
    title = f'{label} · {slogan}' if number == 1 else f'{label} · 第 {number} 页 · {slogan}'
    first = page.object_list[0].title if page.object_list else ''
    if len(first) > 40:
        first = first[:40] + '…'
    if number == 1:
        description = f'{label}系列,共 {count} 篇' + (f'。最新:{first}。' if first else '。') + TAIL
    else:
        description = f'{label}系列,共 {count} 篇,第 {number} 页(共 {page.paginator.num_pages} 页)。{TAIL}'
    return title, description


def list_jsonld(series_key, page, canonical_path, title, description):
    if series_key == 'all' and page.number == 1:
        data = {
            '@context': 'https://schema.org', '@type': 'WebSite', 'name': settings.SITE_NAME,
            'alternateName': settings.SITE_SLOGAN, 'url': _abs('/'),
            'description': description, 'inLanguage': 'zh-CN',
        }
    else:
        start = page.start_index()
        data = {
            '@context': 'https://schema.org', '@type': 'CollectionPage', 'name': title,
            'url': _abs(canonical_path), 'description': description, 'inLanguage': 'zh-CN',
            'isPartOf': _website(),
            'mainEntity': {
                '@type': 'ItemList',
                'itemListElement': [
                    {'@type': 'ListItem', 'position': start + i, 'url': _abs('/' + a.url), 'name': a.title}
                    for i, a in enumerate(page.object_list)
                ],
            },
        }
    return _dump(data)
