from .models import Sport, SiteSettings, Announcement

def all_sports(request):
    settings = SiteSettings.get()
    announcements = list(
        Announcement.objects.filter(is_active=True).values('id', 'message')
    )
    return {
        'all_sports': Sport.objects.all(),
        'site_settings': settings,
        'announcements': announcements,
    }
