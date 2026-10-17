import re
from datetime import date, timedelta

from django.db import models
from django.urls import reverse
from django.utils import timezone

from .constants import DIMENSION_CHOICES, DIMENSION_DATA, ELEMENT_LABELS, SIGN_CHOICES, SIGN_DATA, ZODIAC_GLYPH

PERIOD_BADGES = {"today": "今日", "week": "本周", "month": "本月"}
_PERIOD_SLUG_RE = {
    "today": re.compile(r"-daily-(\d{4})-(\d{2})-(\d{2})$"),
    "week": re.compile(r"-week-(\d{4})-(\d{2})-(\d{2})$"),
    "month": re.compile(r"-month-(\d{4})-(\d{2})$"),
}


class Article(models.Model):
    STATUS_CHOICES = [("draft", "草稿"), ("published", "已发布")]

    sign = models.CharField("星座", max_length=20, choices=SIGN_CHOICES)
    dimension = models.CharField("内容维度", max_length=20, choices=DIMENSION_CHOICES)
    title = models.CharField("标题", max_length=200)
    slug = models.SlugField("URL别名", max_length=220, unique=True)
    summary = models.CharField("摘要", max_length=300, blank=True)
    content_html = models.TextField("正文(HTML)", blank=True)
    status = models.CharField("状态", max_length=10, choices=STATUS_CHOICES, default="draft")
    published_at = models.DateTimeField("发布时间", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "文章"
        verbose_name_plural = "文章"
        ordering = ["-published_at", "-created_at"]

    def __str__(self):
        return f"[{self.get_sign_display()}] {self.title}"

    def get_absolute_url(self):
        return reverse("zodiac:article_detail", args=[self.slug])

    @property
    def period_badge(self):
        # 今日/本周/本月运势的"当前"标签，过期后自动消失，让读者一眼分清新旧。
        # 按 slug 里的日期判断（sign-daily-YYYY-MM-DD / sign-week-起始日 / sign-month-YYYY-MM），
        # 不按发布时间：下个月的运势可以提前发布，发布时间不等于它适用的时间。
        pattern = _PERIOD_SLUG_RE.get(self.dimension)
        match = pattern.search(self.slug) if pattern else None
        if not match:
            return ""
        today = timezone.localdate()
        try:
            if self.dimension == "month":
                year, month = (int(n) for n in match.groups())
                current = (year, month) == (today.year, today.month)
            else:
                start = date(*(int(n) for n in match.groups()))
                if self.dimension == "week":
                    current = start <= today <= start + timedelta(days=6)
                else:
                    current = start == today
        except ValueError:  # slug 里的日期不合法
            return ""
        return PERIOD_BADGES[self.dimension] if current else ""

    @property
    def sign_info(self):
        return SIGN_DATA[self.sign]

    @property
    def element(self):
        return self.sign_info["element"]

    @property
    def element_label(self):
        return ELEMENT_LABELS[self.element]

    @property
    def dimension_label(self):
        return DIMENSION_DATA[self.dimension]

    @property
    def stars(self):
        return [
            {"name": name, "x": x, "y": y, "bright": bright}
            for name, x, y, bright in self.sign_info["stars"]
        ]

    @property
    def stars_polyline(self):
        return " ".join(f"{x},{y}" for _, x, y, _ in self.sign_info["stars"])

    @property
    def glyph(self):
        return ZODIAC_GLYPH[self.sign]

    @property
    def content_for_wechat(self):
        # 微信公众号粘贴时不会带上伪元素生成的内容（列表符号、分隔线等），
        # 这里把 <li> 的符号写成真实文本，保证复制后还在。
        return self.content_html.replace("<li>", "<li>✿ ")
