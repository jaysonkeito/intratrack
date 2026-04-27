from django.contrib import admin
from django.utils.text import slugify
from .models import (
    Sport, SportCategoryConfig, Category, Participant,
    Match, SiteSettings, Announcement
)


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ['event_name', 'event_year']

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


class SportCategoryConfigInline(admin.TabularInline):
    model = SportCategoryConfig
    extra = 1
    verbose_name = "Category"
    verbose_name_plural = "Categories for this sport"


@admin.register(Sport)
class SportAdmin(admin.ModelAdmin):
    list_display  = ['name', 'slug', 'facilitator', 'facilitator_display_name', 'order']
    list_editable = ['order']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [SportCategoryConfigInline]

    fieldsets = (
        ('Sport Info', {
            'fields': ('name', 'slug', 'order')
        }),
        ('Facilitator', {
            'fields': ('facilitator', 'facilitator_display_name'),
            'description': 'Assign the facilitator account for this sport. '
                           'Use the Admin Panel at /admin-panel/ to create facilitator accounts.'
        }),
    )

    def save_model(self, request, obj, form, change):
        if not obj.slug:
            obj.slug = slugify(obj.name)
        super().save_model(request, obj, form, change)
        # Auto-create Category records for each selected config
        for config in obj.category_configs.all():
            Category.objects.get_or_create(sport=obj, name=config.category_key)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display  = ['__str__', 'bracket_type', 'team_count', 'bracket_generated']
    list_filter   = ['sport', 'bracket_type']


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ['slot_label', 'category', 'college']
    list_filter  = ['category__sport']


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display  = ['__str__', 'status', 'score_a', 'score_b', 'round_number', 'is_next_up']
    list_filter   = ['category__sport', 'status']
    list_editable = ['status', 'score_a', 'score_b']


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display  = ['message', 'created_by', 'created_at', 'is_active']
    list_editable = ['is_active']


from .models import Player

@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ['name', 'jersey_number', 'participant', 'status']
    list_filter  = ['status', 'participant__category__sport']
    list_editable = ['status']
