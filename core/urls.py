from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('', views.home, name='home'),
    path('sport/<slug:sport_slug>/', views.sport_detail, name='sport_detail'),
    path('sport/<slug:sport_slug>/<str:cat_name>/', views.category_detail, name='category_detail'),
    # AJAX
    path('api/live/', views.home_live_json, name='home_live_json'),
    path('api/medals/', views.medal_tally_json, name='medal_tally_json'),
    path('api/<slug:sport_slug>/<str:cat_name>/scores/', views.category_scores_json, name='category_scores_json'),
    path('api/<slug:sport_slug>/<str:cat_name>/players/', views.category_players_json, name='category_players_json'),
    path('api/announcements/', views.announcements_json, name='announcements_json'),
    # Admin
    path('admin-panel/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-panel/sport/create/', views.create_sport, name='create_sport'),
    path('admin-panel/facilitator/create/', views.create_facilitator, name='create_facilitator'),
    path('admin-panel/facilitator/remove/<slug:sport_slug>/', views.remove_facilitator, name='remove_facilitator'),
    path('admin-panel/college/create/', views.create_college, name='create_college'),
    path('admin-panel/college/remove/<str:code>/', views.remove_college, name='remove_college'),
    # Facilitator
    path('facilitator/', views.facilitator_dashboard, name='facilitator_dashboard'),
    path('facilitator/bracket/<int:cat_id>/setup/', views.setup_bracket, name='setup_bracket'),
    path('facilitator/bracket/<int:cat_id>/reset-scores/', views.reset_scores, name='reset_scores'),
    path('facilitator/bracket/<int:cat_id>/full-reset/', views.full_reset_bracket, name='full_reset_bracket'),
    path('facilitator/category/<int:cat_id>/assign-college/', views.assign_college, name='assign_college'),
    path('facilitator/match/<int:match_id>/score/', views.update_match_score, name='update_match_score'),
    path('facilitator/match/<int:match_id>/details/', views.update_match_details, name='update_match_details'),
    path('facilitator/match/<int:match_id>/next-up/', views.set_next_up, name='set_next_up'),
    # Players
    path('facilitator/participant/<int:participant_id>/add-player/', views.add_player, name='add_player'),
    path('facilitator/player/<int:player_id>/remove/', views.remove_player, name='remove_player'),
    path('facilitator/player/<int:player_id>/status/', views.update_player_status, name='update_player_status'),
    # Championship Awards
    path('facilitator/category/<int:cat_id>/award/', views.save_award, name='save_award'),
    # Announcements
    path('announcements/post/', views.post_announcement, name='post_announcement'),
    path('announcements/remove/<int:ann_id>/', views.remove_announcement, name='remove_announcement'),
]