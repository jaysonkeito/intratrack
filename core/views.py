from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json, math

from .models import (
    Sport, Category, Participant, Match, SiteSettings,
    SPORT_CATEGORIES, COLLEGE_CHOICES, BRACKET_CHOICES, CATEGORY_CHOICES
)
from .bracket_engine import generate_bracket, advance_winner


# ─── Helpers ──────────────────────────────────────────────────────────────────

def is_admin(user):
    return user.is_authenticated and user.is_superuser

def is_facilitator_for(user, sport):
    return (
        user.is_authenticated and
        hasattr(user, 'facilitated_sport') and
        user.facilitated_sport == sport
    )


# ─── Auth ──────────────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    error = None
    if request.method == 'POST':
        user = authenticate(request,
            username=request.POST['username'],
            password=request.POST['password'])
        if user:
            login(request, user)
            if user.is_superuser:
                return redirect('admin_dashboard')
            if hasattr(user, 'facilitated_sport'):
                return redirect('facilitator_dashboard')
            return redirect('home')
        error = 'Invalid username or password.'
    return render(request, 'core/login.html', {'error': error})


def logout_view(request):
    logout(request)
    return redirect('login')


# ─── Public Views ──────────────────────────────────────────────────────────────

def home(request):
    sports = Sport.objects.prefetch_related('categories__matches').all()
    now_playing = []
    up_next = []
    for sport in sports:
        for cat in sport.categories.all():
            for m in cat.matches.filter(status='ongoing'):
                now_playing.append({'match': m, 'category': cat, 'sport': sport})
            for m in cat.matches.filter(is_next_up=True):
                up_next.append({'match': m, 'category': cat, 'sport': sport})
    return render(request, 'core/home.html', {
        'sports': sports,
        'now_playing': now_playing,
        'up_next': up_next,
    })


def sport_detail(request, sport_name):
    sport = get_object_or_404(Sport, name=sport_name)
    categories = sport.categories.prefetch_related(
        'participants', 'matches__participant_a', 'matches__participant_b'
    ).all()
    fac = is_facilitator_for(request.user, sport)
    # Non-facilitator logged-in users (other facilitators) see viewer mode — no special flag needed
    return render(request, 'core/sport_detail.html', {
        'sport': sport,
        'categories': categories,
        'is_facilitator': fac,
    })


def category_detail(request, sport_name, cat_name):
    sport = get_object_or_404(Sport, name=sport_name)
    category = get_object_or_404(Category, sport=sport, name=cat_name)
    matches = category.matches.select_related('participant_a', 'participant_b').all()
    standings = category.get_standings() if category.bracket_type == 'round_robin' else []
    fac = is_facilitator_for(request.user, sport)

    winners_rounds = {}
    losers_rounds = {}
    grand_final = None
    for m in matches:
        if m.round_number == 200:
            grand_final = m
        elif m.round_number >= 100:
            losers_rounds.setdefault(m.round_number, []).append(m)
        else:
            winners_rounds.setdefault(m.round_number, []).append(m)

    return render(request, 'core/category_detail.html', {
        'sport': sport,
        'category': category,
        'matches': matches,
        'standings': standings,
        'winners_rounds': dict(sorted(winners_rounds.items())),
        'losers_rounds': dict(sorted(losers_rounds.items())),
        'grand_final': grand_final,
        'is_facilitator': fac,
        'colleges': COLLEGE_CHOICES,
        'participants': category.participants.all(),
    })


# ─── AJAX ──────────────────────────────────────────────────────────────────────

def category_scores_json(request, sport_name, cat_name):
    sport = get_object_or_404(Sport, name=sport_name)
    category = get_object_or_404(Category, sport=sport, name=cat_name)
    matches = category.matches.select_related('participant_a', 'participant_b').all()
    data = []
    for m in matches:
        data.append({
            'id': m.id,
            'team_a': m.participant_a.display_name() if m.participant_a else 'TBD',
            'team_b': m.participant_b.display_name() if m.participant_b else 'TBD',
            'score_a': m.score_a,
            'score_b': m.score_b,
            'status': m.status,
            'status_display': m.get_status_display(),
            'round_number': m.round_number,
            'is_next_up': m.is_next_up,
        })
    standings = []
    if category.bracket_type == 'round_robin':
        for s in category.get_standings():
            standings.append({
                'name': s['participant'].display_name(),
                'wins': s['wins'], 'losses': s['losses'],
                'diff': s['diff'], 'played': s['played'],
            })
    return JsonResponse({'matches': data, 'standings': standings})


def home_live_json(request):
    now_playing = []
    up_next = []
    for sport in Sport.objects.prefetch_related(
        'categories__matches__participant_a',
        'categories__matches__participant_b'
    ).all():
        for cat in sport.categories.all():
            for m in cat.matches.filter(status='ongoing'):
                now_playing.append({
                    'sport': sport.get_name_display(),
                    'category': cat.get_name_display(),
                    'team_a': m.participant_a.display_name() if m.participant_a else 'TBD',
                    'team_b': m.participant_b.display_name() if m.participant_b else 'TBD',
                    'score_a': m.score_a,
                    'score_b': m.score_b,
                })
            for m in cat.matches.filter(is_next_up=True):
                up_next.append({
                    'sport': sport.get_name_display(),
                    'category': cat.get_name_display(),
                    'team_a': m.participant_a.display_name() if m.participant_a else 'TBD',
                    'team_b': m.participant_b.display_name() if m.participant_b else 'TBD',
                    'venue': m.venue,
                    'scheduled_time': m.scheduled_time.strftime('%b %d, %I:%M %p') if m.scheduled_time else '',
                })
    return JsonResponse({'now_playing': now_playing, 'up_next': up_next})


# ─── Admin (Head Committee) ────────────────────────────────────────────────────

@login_required
def admin_dashboard(request):
    if not is_admin(request.user):
        return redirect('home')
    sports = Sport.objects.prefetch_related('categories').all()
    return render(request, 'core/admin_dashboard.html', {'sports': sports})


@login_required
@require_POST
def create_facilitator(request):
    if not is_admin(request.user):
        return redirect('home')
    username = request.POST.get('username', '').strip()
    password = request.POST.get('password', '').strip()
    display_name = request.POST.get('display_name', '').strip()
    sport_name = request.POST.get('sport')
    sport = get_object_or_404(Sport, name=sport_name)

    if User.objects.filter(username=username).exists():
        user = User.objects.get(username=username)
    else:
        if not password:
            # Redirect back with error — but for simplicity just use a default
            password = 'intra2026'
        user = User.objects.create_user(username=username, password=password)

    sport.facilitator = user
    sport.facilitator_display_name = display_name
    sport.save()

    # Auto-create categories
    for cat_key in SPORT_CATEGORIES.get(sport_name, []):
        Category.objects.get_or_create(sport=sport, name=cat_key)

    return redirect('admin_dashboard')


@login_required
@require_POST
def remove_facilitator(request, sport_name):
    if not is_admin(request.user):
        return redirect('home')
    sport = get_object_or_404(Sport, name=sport_name)
    sport.facilitator = None
    sport.facilitator_display_name = ''
    sport.save()
    return redirect('admin_dashboard')


# ─── Facilitator ───────────────────────────────────────────────────────────────

@login_required
def facilitator_dashboard(request):
    if not hasattr(request.user, 'facilitated_sport'):
        return redirect('home')
    sport = request.user.facilitated_sport
    categories = sport.categories.prefetch_related('participants', 'matches').all()
    return render(request, 'core/facilitator_dashboard.html', {
        'sport': sport,
        'categories': categories,
        'bracket_choices': BRACKET_CHOICES,
    })


@login_required
@require_POST
def setup_bracket(request, cat_id):
    category = get_object_or_404(Category, id=cat_id)
    if not is_facilitator_for(request.user, category.sport):
        return redirect('home')

    bracket_type = request.POST.get('bracket_type')
    team_count = int(request.POST.get('team_count', 4))

    # FIX: Always allow regenerating — delete old data and start fresh
    Match.objects.filter(category=category).delete()
    Participant.objects.filter(category=category).delete()

    category.bracket_type = bracket_type
    category.team_count = team_count
    category.bracket_generated = False
    category.save()

    labels = [f"Team {chr(65 + i)}" for i in range(team_count)]
    for label in labels:
        Participant.objects.create(category=category, slot_label=label)

    generate_bracket(category)
    return redirect('facilitator_dashboard')


@login_required
@require_POST
def assign_college(request, cat_id):
    """AJAX: assign college to a participant slot — autosaves instantly."""
    category = get_object_or_404(Category, id=cat_id)
    if not is_facilitator_for(request.user, category.sport):
        return JsonResponse({'error': 'Not authorized'}, status=403)

    data = json.loads(request.body)
    participant = get_object_or_404(Participant, id=data['participant_id'], category=category)
    participant.college = data.get('college', '') or None
    participant.save()
    return JsonResponse({
        'success': True,
        'display_name': participant.display_name(),
        'slot_label': participant.slot_label,
    })


@login_required
@require_POST
def update_match_score(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    if not is_facilitator_for(request.user, match.category.sport):
        return JsonResponse({'error': 'Not authorized'}, status=403)

    data = json.loads(request.body)
    match.score_a = int(data.get('score_a', match.score_a))
    match.score_b = int(data.get('score_b', match.score_b))
    status = data.get('status', match.status)
    if status in ['scheduled', 'ongoing', 'finished']:
        match.status = status
    match.save()

    if match.status == 'finished':
        advance_winner(match)

    return JsonResponse({'success': True})


@login_required
@require_POST
def set_next_up(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    if not is_facilitator_for(request.user, match.category.sport):
        return JsonResponse({'error': 'Not authorized'}, status=403)

    data = json.loads(request.body)
    flagging = data.get('next_up', True)
    Match.objects.filter(category=match.category, is_next_up=True).update(is_next_up=False)
    if flagging:
        match.is_next_up = True
        match.save()

    return JsonResponse({'success': True})


# ─── Announcements ────────────────────────────────────────────────────────────

@login_required
@require_POST
def post_announcement(request):
    if not (is_admin(request.user) or hasattr(request.user, 'facilitated_sport')):
        return JsonResponse({'error': 'Not authorized'}, status=403)
    data = json.loads(request.body)
    message = data.get('message', '').strip()
    if not message:
        return JsonResponse({'error': 'Empty message'}, status=400)
    from .models import Announcement
    ann = Announcement.objects.create(message=message, created_by=request.user)
    return JsonResponse({
        'success': True,
        'id': ann.id,
        'message': ann.message,
        'by': request.user.get_full_name() or request.user.username,
    })


@login_required
@require_POST
def remove_announcement(request, ann_id):
    if not (is_admin(request.user) or hasattr(request.user, 'facilitated_sport')):
        return JsonResponse({'error': 'Not authorized'}, status=403)
    from .models import Announcement
    ann = get_object_or_404(Announcement, id=ann_id)
    ann.is_active = False
    ann.save()
    return JsonResponse({'success': True})


def announcements_json(request):
    from .models import Announcement
    anns = list(Announcement.objects.filter(is_active=True).values('id', 'message'))
    return JsonResponse({'announcements': anns})
