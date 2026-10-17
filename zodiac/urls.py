from django.urls import path

from . import views

app_name = "zodiac"

urlpatterns = [
    path("", views.article_list, name="article_list"),
    path("<slug:slug>/", views.article_detail, name="article_detail"),
    path("<slug:slug>/wechat/", views.article_wechat, name="article_wechat"),
]
