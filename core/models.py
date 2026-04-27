from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify


# ─── Category & College constants (these are fixed by intramurals rules) ─────

CATEGORY_CHOICES = [
    ('men', 'Men'),
    ('women', 'Women'),
    ('men_single', 'Men Single'),
    ('men_doubles', 'Men Doubles'),
    ('women_single', 'Women Single'),
    ('women_doubles', 'Women Doubles'),
    ('mixed', 'Mixed'),
]

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

ALL_POSSIBLE_CATEGORIES = [
    ('men', 'Men'),
    ('women', 'Women'),
    ('men_single', 'Men Single'),
    ('men_doubles', 'Men Doubles'),
    ('women_single', 'Women Single'),
    ('women_doubles', 'Women Doubles'),
    ('mixed', 'Mixed'),
]


# ─── Site Settings ────────────────────────────────────────────────────────────

class SiteSettings(models.Model):
    event_year  = models.CharField(max_length=10, default='2026')
    event_name  = models.CharField(max_length=100, default='Intramurals')

    class Meta:
        verbose_name = 'Site Settings'
        verbose_name_plural = 'Site Settings'

    def __str__(self):
        return f'{self.event_name} {self.event_year}'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


# ─── Sport (now fully dynamic) ────────────────────────────────────────────────

class Sport(models.Model):
    name         = models.CharField(max_length=80, unique=True,
                       help_text="Full sport name, e.g. 'Basketball' or 'Arnis'")
    slug         = models.SlugField(max_length=80, unique=True, blank=True,
                       help_text="Auto-generated URL key. Leave blank.")
    facilitator  = models.OneToOneField(
                       User, on_delete=models.SET_NULL, null=True, blank=True,
                       related_name='facilitated_sport')
    facilitator_display_name = models.CharField(
                       max_length=100, blank=True,
                       help_text="Full name of facilitator shown to viewers")
    order        = models.PositiveIntegerField(default=0,
                       help_text="Display order on the homepage (lower = first)")

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    # Keep get_name_display() compatible with old template calls
    def get_name_display(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


# ─── SportCategoryConfig — which categories a sport uses ─────────────────────

class SportCategoryConfig(models.Model):
    """Admin selects which categories apply to a sport."""
    sport        = models.ForeignKey(Sport, on_delete=models.CASCADE,
                       related_name='category_configs')
    category_key = models.CharField(max_length=30, choices=ALL_POSSIBLE_CATEGORIES)

    class Meta:
        unique_together = ('sport', 'category_key')
        ordering = ['category_key']

    def __str__(self):
        return f"{self.sport.name} — {self.get_category_key_display()}"


# ─── Category (bracket instance for a sport+category combo) ──────────────────

class Category(models.Model):
    sport         = models.ForeignKey(Sport, on_delete=models.CASCADE,
                        related_name='categories')
    name          = models.CharField(max_length=30, choices=ALL_POSSIBLE_CATEGORIES)
    bracket_type  = models.CharField(max_length=30, choices=BRACKET_CHOICES,
                        null=True, blank=True)
    team_count    = models.IntegerField(null=True, blank=True)
    bracket_generated = models.BooleanField(default=False)

    class Meta:
        unique_together = ('sport', 'name')
        ordering = ['name']

    def __str__(self):
        return f"{self.sport.name} — {self.get_name_display()}"

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


# ─── Participant ───────────────────────────────────────────────────────────────

class Participant(models.Model):
    category     = models.ForeignKey(Category, on_delete=models.CASCADE,
                       related_name='participants')
    slot_label   = models.CharField(max_length=10)
    college      = models.CharField(max_length=10, choices=COLLEGE_CHOICES,
                       null=True, blank=True)
    is_eliminated = models.BooleanField(default=False)

    class Meta:
        ordering = ['slot_label']
        unique_together = ('category', 'slot_label')

    def __str__(self):
        return f"{self.college or self.slot_label} ({self.category})"

    def display_name(self):
        return self.college if self.college else self.slot_label


# ─── Match ────────────────────────────────────────────────────────────────────

class Match(models.Model):
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('ongoing',   'Ongoing'),
        ('finished',  'Finished'),
    ]

    category       = models.ForeignKey(Category, on_delete=models.CASCADE,
                         related_name='matches')
    participant_a  = models.ForeignKey(Participant, on_delete=models.SET_NULL,
                         null=True, blank=True, related_name='matches_as_a')
    participant_b  = models.ForeignKey(Participant, on_delete=models.SET_NULL,
                         null=True, blank=True, related_name='matches_as_b')
    score_a        = models.IntegerField(default=0)
    score_b        = models.IntegerField(default=0)
    status         = models.CharField(max_length=20, choices=STATUS_CHOICES,
                         default='scheduled')
    round_number   = models.IntegerField(default=1)
    match_number   = models.IntegerField(default=1)
    bracket_slot   = models.CharField(max_length=20, blank=True)
    scheduled_time = models.DateTimeField(null=True, blank=True)
    venue          = models.CharField(max_length=100, blank=True)
    is_next_up     = models.BooleanField(default=False)
    updated_at     = models.DateTimeField(auto_now=True)

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


# ─── Announcement ─────────────────────────────────────────────────────────────

class Announcement(models.Model):
    message    = models.CharField(max_length=300)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active  = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.message[:60]
