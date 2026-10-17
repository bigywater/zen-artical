from django.urls import path

from . import views

urlpatterns = [
    path('', views.ArticleListView.as_view(), name='article_list'),
    path('page/<int:page_number>/', views.ArticleListView.as_view(), name='article_list_page'),
    path('series/<slug:series_key>/', views.ArticleListView.as_view(), name='series_list'),
    path('series/<slug:series_key>/page/<int:page_number>/', views.ArticleListView.as_view(), name='series_list_page'),
    path('<path:url>', views.ArticleDetailView.as_view(), name='article_detail'),
]
