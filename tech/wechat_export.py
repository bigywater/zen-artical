"""
把 MD3 模板文章(content_html,完整 HTML 文档)转换成微信公众号编辑器能正常吃的
版本:去掉外部样式表、CSS 变量、drawer/topbar/next-post 这些站点外壳,把每个元素
的样式写成行内 style,颜色沿用文章本身的浅色主题 token(深色模式在公众号里没有
意义,直接写死浅色数值)。

公众号富文本编辑器的限制:
- 不认 <style>/<link>、不认 class、不认 CSS 变量,只认元素自身的 style="" 属性
- <a href> 在正文里基本会被吞掉或者变成奇怪的链接卡片,所以正文里的链接一律
  降级成普通加粗文字,不保留 href
- <ul>/<li> 有时候会被公众号的粘贴清洗器吃掉项目符号,保险起见改成
  "<p>• 文本</p>" 这种形式
- 代码块里的换行不能只靠 white-space:pre-wrap,保险起见把 \n 显式转成 <br/>
"""
import re
from html import escape as _esc

from django.conf import settings
from lxml import html as lhtml

INK = '#211C16'
INK_DIM = '#6E6255'
LINE = '#E9E0D3'
JAVA_C = '#E76F00'
JAVA_SOFT = '#FBEADA'
MEM_C = '#2F6FB0'
MEM_SOFT = '#E4EEF9'
PAPER = '#FFFFFF'
CODE_BG = '#241E14'
CODE_INK = '#F0E9DC'
CODE_PATH = '#D9C7A3'

MONO_FONT = "ui-monospace,'SFMono-Regular',Menlo,Consolas,'Liberation Mono',monospace"
BODY_FONT = "-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif"


def _classes(el):
    return (el.get('class') or '').split()


def _inline(el):
    """把一个元素的内部内容(文本+允许的行内标签)渲染成公众号安全的行内样式HTML。"""
    parts = []
    if el.text:
        parts.append(_esc(el.text))
    for child in el:
        cls = _classes(child)
        inner = _inline(child)
        tag = child.tag
        if tag == 'span' and 'mono' in cls:
            parts.append(
                f'<span style="font-family:{MONO_FONT};background:#F5EFE4;'
                f'color:#B85C00;padding:1px 5px;border-radius:4px;font-size:14px;">{inner}</span>'
            )
        elif tag == 'a':
            parts.append(f'<span style="color:{JAVA_C};font-weight:600;">{inner}</span>')
        elif tag in ('b', 'strong'):
            parts.append(f'<strong style="font-weight:700;">{inner}</strong>')
        else:
            parts.append(inner)
        if child.tail:
            parts.append(_esc(child.tail))
    return ''.join(parts)


def _code_block(text):
    text = (text or '').strip('\n')
    escaped = _esc(text)
    return escaped.replace('\n', '<br/>')


def _render_src(blockquote):
    span = blockquote.find('span')
    if span is not None:
        path = (span.text or '').strip()
        code = span.tail or ''
    else:
        path = ''
        code = blockquote.xpath('string(.)')
    out = [f'<section style="background:{CODE_BG};color:{CODE_INK};border-radius:10px;'
           f'padding:16px 18px;margin:16px 0;font-family:{MONO_FONT};font-size:13px;'
           f'line-height:1.7;white-space:pre-wrap;word-break:break-word;">']
    if path:
        out.append(f'<p style="color:{CODE_PATH};font-size:12px;margin:0 0 8px;">{_esc(path)}</p>')
    out.append(f'<p style="margin:0;">{_code_block(code)}</p>')
    out.append('</section>')
    return ''.join(out)


def _render_term(div):
    span = div.find('span')
    pre = div.find('pre')
    label = (span.text or '').strip() if span is not None else ''
    code = pre.xpath('string(.)') if pre is not None else ''
    out = [f'<section style="background:{CODE_BG};color:{CODE_INK};border-radius:10px;'
           f'padding:16px 18px;margin:16px 0;font-family:{MONO_FONT};font-size:13px;'
           f'line-height:1.7;white-space:pre-wrap;word-break:break-word;">']
    if label:
        out.append(
            f'<p style="display:inline-block;background:{JAVA_SOFT};color:{JAVA_C};'
            f'font-size:11px;letter-spacing:.05em;padding:2px 8px;border-radius:5px;'
            f'margin:0 0 10px;">{_esc(label)}</p>'
        )
    out.append(f'<p style="margin:0;">{_code_block(code)}</p>')
    out.append('</section>')
    return ''.join(out)


def _render_callout(div):
    is_b = 'b' in _classes(div)
    border = MEM_C if is_b else JAVA_C
    bg = MEM_SOFT if is_b else JAVA_SOFT
    return (
        f'<section style="border-left:3px solid {border};background:{bg};'
        f'border-radius:0 10px 10px 0;padding:14px 18px;margin:20px 0;font-size:15px;'
        f'color:{INK};line-height:1.8;">{_inline(div)}</section>'
    )


def _render_table(table):
    rows = []
    thead = table.find('thead')
    if thead is not None:
        cells = ''.join(
            f'<td style="text-align:left;color:{INK_DIM};font-weight:600;font-size:13px;'
            f'padding:8px 10px;border-bottom:2px solid {LINE};">{_inline(th)}</td>'
            for th in thead.xpath('.//th')
        )
        rows.append(f'<tr>{cells}</tr>')
    tbody = table.find('tbody')
    if tbody is not None:
        for tr in tbody.xpath('./tr'):
            cells = ''.join(
                f'<td style="padding:9px 10px;border-bottom:1px solid {LINE};'
                f'font-size:14px;color:{INK};">{_inline(td)}</td>'
                for td in tr.xpath('./td')
            )
            rows.append(f'<tr>{cells}</tr>')
    return (
        f'<section><table style="width:100%;border-collapse:collapse;margin:20px 0;">'
        f'{"".join(rows)}</table></section>'
    )


def _render_p(p):
    return f'<p style="font-size:16px;color:{INK};line-height:1.85;margin:0 0 16px;">{_inline(p)}</p>'


def _render_h2(h2):
    return (
        f'<p style="font-size:19px;font-weight:700;color:{INK};margin:32px 0 6px;'
        f'line-height:1.4;padding-left:10px;border-left:4px solid {JAVA_C};">{_inline(h2)}</p>'
    )


def _render_h2sub(p):
    return f'<p style="font-size:14px;color:{INK_DIM};margin:0 0 18px;line-height:1.7;">{_inline(p)}</p>'


def _render_refs(div):
    h3 = div.find('h3')
    heading = (h3.text or '').strip() if h3 is not None else '参考与说明'
    items = []
    ul = div.find('ul')
    if ul is not None:
        for li in ul.xpath('./li'):
            items.append(
                f'<p style="font-size:14px;color:{INK_DIM};line-height:1.8;margin:0 0 8px;">'
                f'• {_inline(li)}</p>'
            )
    return (
        f'<section style="background:{PAPER};border:1px solid {LINE};border-radius:12px;'
        f'padding:20px 22px;margin-top:24px;">'
        f'<p style="margin:0 0 10px;font-size:15px;font-weight:700;color:{INK};">{_esc(heading)}</p>'
        f'{"".join(items)}</section>'
    )


def _render_section(section):
    """section 是普通内容段落(不是 refs、不是 next-post 导航),按原始顺序渲染其子元素。"""
    out = []
    for child in section:
        cls = _classes(child)
        tag = child.tag
        if tag == 'h2':
            out.append(_render_h2(child))
        elif tag == 'p' and 'h2-sub' in cls:
            out.append(_render_h2sub(child))
        elif tag == 'blockquote' and 'src' in cls:
            out.append(_render_src(child))
        elif tag == 'div' and 'term' in cls:
            out.append(_render_term(child))
        elif tag == 'div' and 'callout' in cls:
            out.append(_render_callout(child))
        elif tag == 'table':
            out.append(_render_table(child))
        elif tag == 'p':
            out.append(_render_p(child))
        # 其余(next-post 链接块等)忽略
    return ''.join(out)


def render_wechat_html(full_html: str) -> str:
    """把文章完整 HTML(Article.content_html)转换成可以直接复制进公众号编辑器的行内样式HTML。"""
    doc = lhtml.fromstring(full_html)
    out = []

    hero_inner = doc.xpath("//div[contains(concat(' ',normalize-space(@class),' '),' hero-inner ')]")
    if hero_inner:
        hero_inner = hero_inner[0]
        eyebrow = hero_inner.xpath(".//div[contains(concat(' ',normalize-space(@class),' '),' eyebrow ')]")
        if eyebrow:
            text = eyebrow[0].xpath('string(.)').strip()
            out.append(
                f'<p style="font-family:{MONO_FONT};font-size:13px;letter-spacing:.05em;'
                f'text-transform:uppercase;color:{JAVA_C};margin:0 0 12px;">{_esc(text)}</p>'
            )
        h1 = hero_inner.find('h1')
        if h1 is not None:
            out.append(
                f'<p style="font-size:22px;font-weight:700;color:{INK};line-height:1.45;'
                f'margin:0 0 16px;">{_inline(h1)}</p>'
            )
        intro_p = hero_inner.find('p')
        if intro_p is not None:
            out.append(_render_p(intro_p))
        hero_fact = hero_inner.xpath(".//div[contains(concat(' ',normalize-space(@class),' '),' hero-fact ')]")
        if hero_fact:
            for stat in hero_fact[0].xpath('./div'):
                num = stat.find('div')
                lbl = num.getnext() if num is not None else None
                num_text = num.xpath('string(.)').strip() if num is not None else ''
                lbl_text = lbl.xpath('string(.)').strip() if lbl is not None else ''
                out.append(
                    f'<section style="border:1px solid {LINE};border-radius:10px;'
                    f'padding:12px 16px;margin:0 0 10px;background:{PAPER};">'
                    f'<p style="font-family:{MONO_FONT};font-size:15px;font-weight:700;'
                    f'color:{JAVA_C};margin:0;">{_esc(num_text)}</p>'
                    f'<p style="font-size:13px;color:{INK_DIM};margin:4px 0 0;">{_esc(lbl_text)}</p>'
                    f'</section>'
                )

    wrap = doc.xpath("//div[contains(concat(' ',normalize-space(@class),' '),' wrap ')]")
    if wrap:
        for section in wrap[0].xpath('./section'):
            if section.xpath("./div[contains(concat(' ',normalize-space(@class),' '),' refs ')]"):
                out.append(_render_refs(section.find('div')))
                continue
            if section.xpath("./a[contains(concat(' ',normalize-space(@class),' '),' next-post ')]"):
                continue  # 站内导航,公众号用不上
            out.append(_render_section(section))

    out.append(
        f'<p style="text-align:center;color:#B3A692;font-size:12px;margin-top:32px;">'
        f'数据来自本机真实实验 · {settings.SITE_DOMAIN}</p>'
    )

    return '\n'.join(out)
