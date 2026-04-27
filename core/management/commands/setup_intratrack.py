from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import Sport, Team, UserProfile

SPORTS = [
    'basketball', 'softball', 'badminton', 'sepak_takraw',
    'chess', 'table_tennis', 'volleyball', 'soccer'
]

SAMPLE_TEAMS = ['Team Alpha', 'Team Bravo', 'Team Charlie', 'Team Delta']

class Command(BaseCommand):
    help = 'Create all 8 sports, sample teams, and scorer accounts'

    def handle(self, *args, **kwargs):
        for sport_key in SPORTS:
            sport, _ = Sport.objects.get_or_create(name=sport_key)
            username = f'scorer_{sport_key}'
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(username=username, password='intra2025')
                UserProfile.objects.create(user=user, is_scorer=True)
                sport.scorer = user
                sport.save()
                self.stdout.write(f'  Created scorer: {username} / intra2025')
            for team_name in SAMPLE_TEAMS:
                Team.objects.get_or_create(name=team_name, sport=sport)
            self.stdout.write(self.style.SUCCESS(f'  {sport.get_name_display()} ready'))

        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', '', 'admin2025')
            self.stdout.write(self.style.SUCCESS('  Superuser: admin / admin2025'))

        self.stdout.write(self.style.SUCCESS('\nIntraTrack setup complete!'))
