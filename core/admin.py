from django.contrib import admin
from .models import Sport, Category, Participant, Match, SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ['event_name', 'event_year']

    def has_add_permission(self, request):
        # Only allow one instance
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Sport)
class SportAdmin(admin.ModelAdmin):
    list_display = ['get_name_display', 'facilitator', 'facilitator_display_name']


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'bracket_type', 'team_count', 'bracket_generated']


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ['slot_label', 'category', 'college']


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'status', 'score_a', 'score_b', 'round_number', 'is_next_up']
    list_filter = ['category__sport', 'status']


from .models import Announcement

@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ['message', 'created_by', 'created_at', 'is_active']
    list_editable = ['is_active']
