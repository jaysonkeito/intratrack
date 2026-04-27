from django.db import models
from django.contrib.auth.models import User
from django.db.models import Q


SPORT_CHOICES = [
    ('basketball', 'Basketball'),
    ('softball', 'Softball'),
    ('badminton', 'Badminton'),
    ('sepak_takraw', 'Sepak Takraw'),
    ('chess', 'Chess'),
    ('table_tennis', 'Table Tennis'),
    ('volleyball', 'Volleyball'),
    ('soccer', 'Soccer'),
]

CATEGORY_CHOICES = [
    ('men', 'Men'),
    ('women', 'Women'),
    ('men_single', 'Men Single'),
    ('men_doubles', 'Men Doubles'),
    ('women_single', 'Women Single'),
    ('women_doubles', 'Women Doubles'),
    ('mixed', 'Mixed'),
]

SPORT_CATEGORIES = {
    'basketball':   ['men', 'women'],
    'softball':     ['women'],
    'badminton':    ['men_single', 'men_doubles', 'women_single', 'women_doubles', 'mixed'],
    'sepak_takraw': ['men'],
    'chess':        ['men', 'women'],
    'table_tennis': ['men_single', 'men_doubles', 'women_single', 'women_doubles', 'mixed'],
    'volleyball':   ['men', 'women'],
    'soccer':       ['men', 'women'],
}

COLLEGE_CHOICES = [
    ('CAF',  'College of Agriculture and Forestry'),
    ('CAS',  'College of Arts and Sciences'),
    ('CBA',  'College of Business Administration'),
    ('CIT',  'College of Industrial Technology'),
    ('CTED', 'College of Teacher Education'),
    ('CCJE', 'College of Criminal Justice Education'),
]

BRACKET_CHOICES = [
    ('single_elimination', 'Single Elimination'),
    ('double_elimination', 'Double Elimination'),
    ('round_robin',        'Round Robin'),
]


class SiteSettings(models.Model):
    """Singleton model for site-wide settings editable from Django admin."""
    event_year = models.CharField(max_length=10, default='2026')
    event_name = models.CharField(max_length=100, default='Intramurals')

    class Meta:
        verbose_name = 'Site Settings'
        verbose_name_plural = 'Site Settings'

    def __str__(self):
        return f'{self.event_name} {self.event_year}'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Sport(models.Model):
    name = models.CharField(max_length=50, choices=SPORT_CHOICES, unique=True)
    facilitator = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='facilitated_sport'
    )
    facilitator_display_name = models.CharField(
        max_length=100, blank=True,
        help_text="Full name of the facilitator shown to viewers"
    )

    def __str__(self):
        return self.get_name_display()

    def get_categories(self):
        return SPORT_CATEGORIES.get(self.name, [])


class Category(models.Model):
    sport = models.ForeignKey(Sport, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    bracket_type = models.CharField(max_length=30, choices=BRACKET_CHOICES, null=True, blank=True)
    team_count = models.IntegerField(null=True, blank=True)
    bracket_generated = models.BooleanField(default=False)

    class Meta:
        unique_together = ('sport', 'name')
        ordering = ['name']

    def __str__(self):
        return f"{self.sport.get_name_display()} — {self.get_name_display()}"

    def get_standings(self):
        participants = self.participants.all()
        result = []
        for p in participants:
            matches_as_a = Match.objects.filter(category=self, status='finished', participant_a=p)
            matches_as_b = Match.objects.filter(category=self, status='finished', participant_b=p)
            wins = losses = draws = pf = pa = 0
            for m in matches_as_a:
                pf += m.score_a; pa += m.score_b
                if m.score_a > m.score_b: wins += 1
                elif m.score_a < m.score_b: losses += 1
                else: draws += 1
            for m in matches_as_b:
                pf += m.score_b; pa += m.score_a
                if m.score_b > m.score_a: wins += 1
                elif m.score_b < m.score_a: losses += 1
                else: draws += 1
            result.append({
                'participant': p,
                'wins': wins, 'losses': losses, 'draws': draws,
                'pf': pf, 'pa': pa, 'diff': pf - pa,
                'played': wins + losses + draws,
            })
        result.sort(key=lambda x: (-x['wins'], x['losses'], -x['diff']))
        return result


class Participant(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='participants')
    slot_label = models.CharField(max_length=10)
    college = models.CharField(max_length=10, choices=COLLEGE_CHOICES, null=True, blank=True)
    is_eliminated = models.BooleanField(default=False)

    class Meta:
        ordering = ['slot_label']
        unique_together = ('category', 'slot_label')

    def __str__(self):
        if self.college:
            return f"{self.get_college_display()} ({self.slot_label})"
        return f"{self.slot_label} (TBA)"

    def display_name(self):
        return self.college if self.college else self.slot_label


class Match(models.Model):
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('ongoing',   'Ongoing'),
        ('finished',  'Finished'),
    ]

    category      = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='matches')
    participant_a  = models.ForeignKey(Participant, on_delete=models.SET_NULL, null=True, blank=True, related_name='matches_as_a')
    participant_b  = models.ForeignKey(Participant, on_delete=models.SET_NULL, null=True, blank=True, related_name='matches_as_b')
    score_a       = models.IntegerField(default=0)
    score_b       = models.IntegerField(default=0)
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    round_number  = models.IntegerField(default=1)
    match_number  = models.IntegerField(default=1)
    bracket_slot  = models.CharField(max_length=20, blank=True)
    scheduled_time = models.DateTimeField(null=True, blank=True)
    venue         = models.CharField(max_length=100, blank=True)
    is_next_up    = models.BooleanField(default=False)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['round_number', 'match_number']

    def __str__(self):
        a = self.participant_a.display_name() if self.participant_a else 'TBD'
        b = self.participant_b.display_name() if self.participant_b else 'TBD'
        return f"{self.category} | R{self.round_number}M{self.match_number}: {a} vs {b}"

    def winner_participant(self):
        if self.status != 'finished': return None
        if self.score_a > self.score_b: return self.participant_a
        if self.score_b > self.score_a: return self.participant_b
        return None

    def loser_participant(self):
        if self.status != 'finished': return None
        if self.score_a < self.score_b: return self.participant_a
        if self.score_b < self.score_a: return self.participant_b
        return None


class Announcement(models.Model):
    message = models.CharField(max_length=300)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.message[:60]
