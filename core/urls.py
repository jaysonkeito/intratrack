from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('', views.home, name='home'),
    path('sport/<str:sport_name>/', views.sport_detail, name='sport_detail'),
    path('sport/<str:sport_name>/<str:cat_name>/', views.category_detail, name='category_detail'),
    path('api/live/', views.home_live_json, name='home_live_json'),
    path('api/<str:sport_name>/<str:cat_name>/scores/', views.category_scores_json, name='category_scores_json'),
    path('api/announcements/', views.announcements_json, name='announcements_json'),
    path('admin-panel/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-panel/facilitator/create/', views.create_facilitator, name='create_facilitator'),
    path('admin-panel/facilitator/remove/<str:sport_name>/', views.remove_facilitator, name='remove_facilitator'),
    path('facilitator/', views.facilitator_dashboard, name='facilitator_dashboard'),
    path('facilitator/bracket/<int:cat_id>/setup/', views.setup_bracket, name='setup_bracket'),
    path('facilitator/category/<int:cat_id>/assign-college/', views.assign_college, name='assign_college'),
    path('facilitator/match/<int:match_id>/score/', views.update_match_score, name='update_match_score'),
    path('facilitator/match/<int:match_id>/next-up/', views.set_next_up, name='set_next_up'),
    path('announcements/post/', views.post_announcement, name='post_announcement'),
    path('announcements/remove/<int:ann_id>/', views.remove_announcement, name='remove_announcement'),
]
