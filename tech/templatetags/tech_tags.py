from django import template

from tech.static_site import list_url

register = template.Library()


@register.simple_tag
def list_page_url(series_key, page_number):
    return list_url(series_key, page_number)
