from django.db import models


class Series(models.Model):
    key = models.SlugField(unique=True)
    label = models.CharField(max_length=50)
    color = models.CharField(max_length=7)

    class Meta:
        ordering = ['key']
        verbose_name_plural = 'series'

    def __str__(self):
        return self.label


class Article(models.Model):
    title = models.CharField(max_length=200)
    url = models.SlugField(unique=True, max_length=100)
    series = models.ForeignKey(Series, on_delete=models.PROTECT, related_name='articles')
    tags = models.CharField(max_length=200, blank=True)
    date = models.DateField()
    description = models.TextField()
    content_html = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return self.title

    def tag_list(self):
        return [t.strip() for t in self.tags.split(',') if t.strip()]
