from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils.text import slugify
from django.db.models import Q
import json

from .models import (
    Sport, SportCategoryConfig, Category, Participant, Match,
    SiteSettings, Announcement, CollegeProfile, Player,
    ChampionshipAward, FacilitatorSession,
    COLLEGE_CHOICES, BRACKET_CHOICES, ALL_POSSIBLE_CATEGORIES, get_college_choices
)
from .bracket_engine import generate_bracket, advance_winner

MAX_FACILITATOR_DEVICES = 2


# ─── Helpers ──────────────────────────────────────────────────────────────────

def is_admin(user):
    return user.is_authenticated and user.is_superuser

def is_facilitator_for(user, sport):
    return (
        user.is_authenticated and
        hasattr(user, 'facilitated_sport') and
        user.facilitated_sport == sport
    )

def _register_facilitator_session(user, session_key):
    """Register/refresh this session key. Evict oldest if over limit."""
    obj, created = FacilitatorSession.objects.get_or_create(
        user=user, session_key=session_key
    )
    if not created:
        # Touch last_seen via save
        obj.save()

    # Enforce max 2 devices: keep only the 2 most recent
    sessions = list(FacilitatorSession.objects.filter(user=user).order_by('-last_seen'))
    if len(sessions) > MAX_FACILITATOR_DEVICES:
        for old in sessions[MAX_FACILITATOR_DEVICES:]:
            old.delete()

def _is_facilitator_session_allowed(user, session_key):
    """Check if this session key is in the allowed list for this user."""
    allowed_keys = list(
        FacilitatorSession.objects.filter(user=user)
        .order_by('-last_seen')
        .values_list('session_key', flat=True)[:MAX_FACILITATOR_DEVICES]
    )
    return session_key in allowed_keys


# ─── Auth ──────────────────────────────────────────────────────────────────────

def login_view(request):
    # Redirect already-authenticated users to their dashboard
    if request.user.is_authenticated:
        if request.user.is_superuser:
            return redirect('admin_dashboard')
        if hasattr(request.user, 'facilitated_sport'):
            return redirect('facilitator_dashboard')
        return redirect('home')
    error = None
    if request.method == 'POST':
        user = authenticate(request,
            username=request.POST['username'],
            password=request.POST['password'])
        if user:
            login(request, user)
            # For facilitators: register this device session
            if not user.is_superuser and hasattr(user, 'facilitated_sport'):
                _register_facilitator_session(user, request.session.session_key)
            if user.is_superuser:
                return redirect('admin_dashboard')
            if hasattr(user, 'facilitated_sport'):
                return redirect('facilitator_dashboard')
            return redirect('home')
        error = 'Invalid username or password.'
    return render(request, 'core/login.html', {'error': error})


def logout_view(request):
    user = request.user
    sk = request.session.session_key
    logout(request)
    # Remove this device's session record
    if user.is_authenticated:
        FacilitatorSession.objects.filter(user=user, session_key=sk).delete()
    return redirect('login')


# ─── Medal Tally helper ───────────────────────────────────────────────────────

def compute_medal_tally():
    from collections import defaultdict
    tally = defaultdict(lambda: {'gold': 0, 'silver': 0, 'bronze': 0, 'total': 0})

    for category in Category.objects.filter(bracket_generated=True):
        if category.bracket_type == 'round_robin':
            standings = category.get_standings()
            medals = [('gold', 0), ('silver', 1), ('bronze', 2)]
            for medal, idx in medals:
                if idx < len(standings):
                    college = standings[idx]['participant'].college
                    if college:
                        tally[college][medal] += 1
                        tally[college]['total'] += 1

        elif category.bracket_type in ['single_elimination', 'double_elimination']:
            final = (Match.objects.filter(
                category=category, status='finished', round_number=200
            ).first() or
            Match.objects.filter(
                category=category, status='finished'
            ).order_by('-round_number', '-match_number').first())

            if final:
                winner = final.winner_participant()
                loser  = final.loser_participant()
                if winner and winner.college:
                    tally[winner.college]['gold'] += 1
                    tally[winner.college]['total'] += 1
                if loser and loser.college:
                    tally[loser.college]['silver'] += 1
                    tally[loser.college]['total'] += 1

    result = []
    profiles = {p.code: p for p in CollegeProfile.objects.all()}
    for college_code, counts in tally.items():
        profile = profiles.get(college_code)
        result.append({
            'code': college_code,
            'name': profile.get_full_name() if profile else college_code,
            'short_name': profile.short_name if profile else college_code,
            'logo_url': profile.logo.url if profile and profile.logo else None,
            'gold':   counts['gold'],
            'silver': counts['silver'],
            'bronze': counts['bronze'],
            'total':  counts['total'],
        })
    result.sort(key=lambda x: (-x['gold'], -x['silver'], -x['bronze']))
    return result


def get_college_logo_url(college_profiles, code):
    profile = college_profiles.get(code)
    if profile and profile.logo:
        try:
            return profile.logo.url
        except Exception:
            return None
    return None


# ─── Public Views ──────────────────────────────────────────────────────────────

def home(request):
    sports = Sport.objects.prefetch_related('categories__matches').all()
    now_playing, up_next = [], []
    for sport in sports:
        for cat in sport.categories.all():
            for m in cat.matches.filter(status='ongoing'):
                now_playing.append({'match': m, 'category': cat, 'sport': sport})
            for m in cat.matches.filter(is_next_up=True, status__in=['scheduled']):
                up_next.append({'match': m, 'category': cat, 'sport': sport})

    college_profiles = {p.code: p for p in CollegeProfile.objects.all()}
    medal_tally = compute_medal_tally()
    for item in medal_tally:
        profile = college_profiles.get(item['code'])
        if profile and profile.logo:
            try:
                item['logo_url'] = profile.logo.url
            except Exception:
                item['logo_url'] = None
        else:
            item['logo_url'] = None

    return render(request, 'core/home.html', {
        'sports': sports,
        'now_playing': now_playing,
        'up_next': up_next,
        'medal_tally': medal_tally,
        'college_profiles': college_profiles,
    })


def medal_tally_json(request):
    return JsonResponse({'tally': compute_medal_tally()})


def sport_detail(request, sport_slug):
    sport = get_object_or_404(Sport, slug=sport_slug)
    categories = sport.categories.prefetch_related(
        'participants', 'matches__participant_a', 'matches__participant_b'
    ).all()
    return render(request, 'core/sport_detail.html', {
        'sport': sport,
        'categories': categories,
        'is_facilitator': is_facilitator_for(request.user, sport),
    })


def category_detail(request, sport_slug, cat_name):
    sport = get_object_or_404(Sport, slug=sport_slug)
    category = get_object_or_404(Category, sport=sport, name=cat_name)
    matches = category.matches.select_related('participant_a', 'participant_b').all()
    standings = category.get_standings() if category.bracket_type == 'round_robin' else []
    fac = is_facilitator_for(request.user, sport)

    winners_rounds, losers_rounds, grand_final = {}, {}, None
    for m in matches:
        if m.round_number == 200:
            grand_final = m
        elif m.round_number >= 100:
            losers_rounds.setdefault(m.round_number, []).append(m)
        else:
            winners_rounds.setdefault(m.round_number, []).append(m)

    college_profiles = {p.code: p for p in CollegeProfile.objects.all()}

    # Championship awards
    awards = {a.award_type: a for a in category.awards.all()}
    is_championship_done = (grand_final and grand_final.status == 'finished') or \
        (not grand_final and any(m.status == 'finished' for m in matches))

    return render(request, 'core/category_detail.html', {
        'sport': sport, 'category': category, 'matches': matches,
        'standings': standings,
        'winners_rounds': dict(sorted(winners_rounds.items())),
        'losers_rounds': dict(sorted(losers_rounds.items())),
        'grand_final': grand_final,
        'is_facilitator': fac,
        'colleges': get_college_choices(),
        'participants': category.participants.prefetch_related('players').all(),
        'college_profiles': college_profiles,
        'awards': awards,
        'is_championship_done': is_championship_done,
        'college_choices': get_college_choices(),
    })


# ─── AJAX ─────────────────────────────────────────────────────────────────────

def category_scores_json(request, sport_slug, cat_name):
    sport = get_object_or_404(Sport, slug=sport_slug)
    category = get_object_or_404(Category, sport=sport, name=cat_name)
    matches = category.matches.select_related('participant_a', 'participant_b').all()
    data = [{'id': m.id,
             'team_a': m.participant_a.display_name() if m.participant_a else 'TBD',
             'team_b': m.participant_b.display_name() if m.participant_b else 'TBD',
             'score_a': m.score_a, 'score_b': m.score_b,
             'status': m.status, 'status_display': m.get_status_display(),
             'is_next_up': m.is_next_up,
             'scheduled_time': m.scheduled_time.strftime('%b %d, %I:%M %p') if m.scheduled_time else '',
             } for m in matches]
    standings = []
    if category.bracket_type == 'round_robin':
        for s in category.get_standings():
            standings.append({'name': s['participant'].display_name(),
                               'wins': s['wins'], 'losses': s['losses'],
                               'diff': s['diff'], 'played': s['played']})
    return JsonResponse({'matches': data, 'standings': standings})


def home_live_json(request):
    now_playing, up_next = [], []
    for sport in Sport.objects.prefetch_related(
        'categories__matches__participant_a',
        'categories__matches__participant_b').all():
        for cat in sport.categories.all():
            for m in cat.matches.filter(status='ongoing'):
                now_playing.append({
                    'sport': sport.name, 'category': cat.get_name_display(),
                    'sport_slug': sport.slug, 'cat_name': cat.name,
                    'match_id': m.id,
                    'team_a': m.participant_a.display_name() if m.participant_a else 'TBD',
                    'team_b': m.participant_b.display_name() if m.participant_b else 'TBD',
                    'score_a': m.score_a, 'score_b': m.score_b,
                    'scheduled_time': m.scheduled_time.strftime('%b %d, %I:%M %p') if m.scheduled_time else '',
                    'venue': m.venue,
                })
            for m in cat.matches.filter(is_next_up=True, status='scheduled'):
                up_next.append({
                    'sport': sport.name, 'category': cat.get_name_display(),
                    'sport_slug': sport.slug, 'cat_name': cat.name,
                    'match_id': m.id,
                    'team_a': m.participant_a.display_name() if m.participant_a else 'TBD',
                    'team_b': m.participant_b.display_name() if m.participant_b else 'TBD',
                    'venue': m.venue,
                    'scheduled_time': m.scheduled_time.strftime('%b %d, %I:%M %p') if m.scheduled_time else '',
                })
    return JsonResponse({'now_playing': now_playing, 'up_next': up_next})


def announcements_json(request):
    anns = list(Announcement.objects.filter(is_active=True).values('id', 'message'))
    return JsonResponse({'announcements': anns})


def category_players_json(request, sport_slug, cat_name):
    sport = get_object_or_404(Sport, slug=sport_slug)
    category = get_object_or_404(Category, sport=sport, name=cat_name)
    data = []
    for p in category.participants.prefetch_related('players').all():
        players = [{'id': pl.id, 'name': pl.name,
                    'jersey_number': pl.jersey_number, 'status': pl.status}
                   for pl in p.players.all()]
        data.append({'slot': p.slot_label, 'college': p.display_name(), 'players': players})
    return JsonResponse({'roster': data})


# ─── Admin Panel ──────────────────────────────────────────────────────────────

@login_required
def admin_dashboard(request):
    if not is_admin(request.user):
        if hasattr(request.user, 'facilitated_sport'):
            return redirect('facilitator_dashboard')
        return redirect('home')
    sports = Sport.objects.prefetch_related('categories', 'category_configs').all()
    colleges = CollegeProfile.objects.all()
    return render(request, 'core/admin_dashboard.html', {
        'sports': sports,
        'all_categories': ALL_POSSIBLE_CATEGORIES,
        'colleges': colleges,
    })


@login_required
@require_POST
def create_sport(request):
    if not is_admin(request.user):
        return redirect('home')
    sport_name = request.POST.get('sport_name', '').strip()
    if not sport_name:
        return redirect('admin_dashboard')
    slug = slugify(sport_name)
    sport, _ = Sport.objects.get_or_create(slug=slug, defaults={'name': sport_name})
    sport.name = sport_name
    sport.save()
    selected_cats = request.POST.getlist('categories')
    SportCategoryConfig.objects.filter(sport=sport).delete()
    for cat_key in selected_cats:
        SportCategoryConfig.objects.get_or_create(sport=sport, category_key=cat_key)
        Category.objects.get_or_create(sport=sport, name=cat_key)
    return redirect('admin_dashboard')


@login_required
@require_POST
def create_facilitator(request):
    if not is_admin(request.user):
        return redirect('home')
    username     = request.POST.get('username', '').strip()
    password     = request.POST.get('password', '').strip()
    display_name = request.POST.get('display_name', '').strip()
    sport_slug   = request.POST.get('sport')
    sport = get_object_or_404(Sport, slug=sport_slug)

    if User.objects.filter(username=username).exists():
        user = User.objects.get(username=username)
    else:
        user = User.objects.create_user(username=username, password=password or 'intra2026')

    Sport.objects.filter(facilitator=user).update(facilitator=None)
    sport.facilitator = user
    sport.facilitator_display_name = display_name
    sport.save()

    for config in sport.category_configs.all():
        Category.objects.get_or_create(sport=sport, name=config.category_key)

    return redirect('admin_dashboard')


@login_required
@require_POST
def remove_facilitator(request, sport_slug):
    if not is_admin(request.user):
        return redirect('home')
    sport = get_object_or_404(Sport, slug=sport_slug)
    sport.facilitator = None
    sport.facilitator_display_name = ''
    sport.save()
    return redirect('admin_dashboard')


@login_required
@require_POST
def create_college(request):
    """Admin adds a new college."""
    if not is_admin(request.user):
        return redirect('home')
    code      = request.POST.get('code', '').strip().upper()
    full_name = request.POST.get('full_name', '').strip()
    short_name = request.POST.get('short_name', '').strip()
    logo      = request.FILES.get('logo')
    if not code or not full_name:
        return redirect('admin_dashboard')
    profile, created = CollegeProfile.objects.get_or_create(code=code)
    profile.full_name  = full_name
    profile.short_name = short_name
    if logo:
        profile.logo = logo
    profile.save()
    return redirect('admin_dashboard')


@login_required
@require_POST
def remove_college(request, code):
    """Admin removes a college profile."""
    if not is_admin(request.user):
        return redirect('home')
    CollegeProfile.objects.filter(code=code).delete()
    return redirect('admin_dashboard')


# ─── Facilitator ──────────────────────────────────────────────────────────────

@login_required
def facilitator_dashboard(request):
    if is_admin(request.user):
        return redirect('admin_dashboard')
    if not hasattr(request.user, 'facilitated_sport'):
        return redirect('home')
    sport = request.user.facilitated_sport
    categories = sport.categories.prefetch_related('participants', 'matches').all()
    return render(request, 'core/facilitator_dashboard.html', {
        'sport': sport, 'categories': categories, 'bracket_choices': BRACKET_CHOICES,
    })


@login_required
@require_POST
def setup_bracket(request, cat_id):
    category = get_object_or_404(Category, id=cat_id)
    if not is_facilitator_for(request.user, category.sport):
        return redirect('home')
    bracket_type = request.POST.get('bracket_type')
    team_count   = int(request.POST.get('team_count', 4))
    Match.objects.filter(category=category).delete()
    Participant.objects.filter(category=category).delete()
    category.bracket_type = bracket_type
    category.team_count   = team_count
    category.bracket_generated = False
    category.save()
    for i in range(team_count):
        Participant.objects.create(category=category, slot_label=f"Team {chr(65+i)}")
    generate_bracket(category)
    return redirect('facilitator_dashboard')


@login_required
@require_POST
def reset_scores(request, cat_id):
    category = get_object_or_404(Category, id=cat_id)
    if not is_facilitator_for(request.user, category.sport):
        return redirect('home')
    Match.objects.filter(category=category).update(
        score_a=0, score_b=0, status='scheduled', is_next_up=False
    )
    return redirect('facilitator_dashboard')


@login_required
@require_POST
def full_reset_bracket(request, cat_id):
    category = get_object_or_404(Category, id=cat_id)
    if not is_facilitator_for(request.user, category.sport):
        return redirect('home')
    Match.objects.filter(category=category).delete()
    Participant.objects.filter(category=category).delete()
    category.bracket_type = None
    category.team_count   = None
    category.bracket_generated = False
    category.save()
    return redirect('facilitator_dashboard')


@login_required
@require_POST
def assign_college(request, cat_id):
    category = get_object_or_404(Category, id=cat_id)
    if not is_facilitator_for(request.user, category.sport):
        return JsonResponse({'error': 'Not authorized'}, status=403)
    data = json.loads(request.body)
    participant = get_object_or_404(Participant, id=data['participant_id'], category=category)
    participant.college = data.get('college', '') or None
    participant.save()
    return JsonResponse({'success': True, 'display_name': participant.display_name(),
                         'slot_label': participant.slot_label})


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
        match.is_next_up = False
        match.save()
    return JsonResponse({
        'success': True,
        'score_a': match.score_a,
        'score_b': match.score_b,
        'status': match.status,
        'status_display': match.get_status_display(),
    })


@login_required
@require_POST
def update_match_details(request, match_id):
    """Facilitator sets scheduled time and venue."""
    match = get_object_or_404(Match, id=match_id)
    if not is_facilitator_for(request.user, match.category.sport):
        return JsonResponse({'error': 'Not authorized'}, status=403)
    data = json.loads(request.body)
    if 'venue' in data:
        match.venue = data['venue']
    if data.get('scheduled_time'):
        from django.utils.dateparse import parse_datetime
        dt = parse_datetime(data['scheduled_time'])
        if dt:
            match.scheduled_time = dt
    match.save()
    return JsonResponse({
        'success': True,
        'scheduled_time': match.scheduled_time.strftime('%b %d, %I:%M %p') if match.scheduled_time else '',
        'venue': match.venue,
    })


@login_required
@require_POST
def set_next_up(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    if not is_facilitator_for(request.user, match.category.sport):
        return JsonResponse({'error': 'Not authorized'}, status=403)
    data = json.loads(request.body)
    Match.objects.filter(category=match.category, is_next_up=True).update(is_next_up=False)
    if data.get('next_up', True):
        match.is_next_up = True
        match.save()
    return JsonResponse({'success': True})


# ─── Championship Awards ──────────────────────────────────────────────────────

@login_required
@require_POST
def save_award(request, cat_id):
    category = get_object_or_404(Category, id=cat_id)
    if not is_facilitator_for(request.user, category.sport):
        return JsonResponse({'error': 'Not authorized'}, status=403)
    data = json.loads(request.body)
    award_type  = data.get('award_type')
    player_name = data.get('player_name', '').strip()
    college     = data.get('college', '') or None
    note        = data.get('note', '').strip()
    if award_type not in ('mvp', 'potg'):
        return JsonResponse({'error': 'Invalid award type'}, status=400)
    award, _ = ChampionshipAward.objects.update_or_create(
        category=category, award_type=award_type,
        defaults={'player_name': player_name, 'college': college, 'note': note}
    )
    return JsonResponse({
        'success': True,
        'award_type': award.award_type,
        'player_name': award.player_name,
        'college': award.college or '',
        'note': award.note,
    })


# ─── Players ──────────────────────────────────────────────────────────────────

@login_required
@require_POST
def add_player(request, participant_id):
    participant = get_object_or_404(Participant, id=participant_id)
    if not is_facilitator_for(request.user, participant.category.sport):
        return JsonResponse({'error': 'Not authorized'}, status=403)
    data = json.loads(request.body)
    name = data.get('name', '').strip()
    if not name:
        return JsonResponse({'error': 'Name required'}, status=400)
    player = Player.objects.create(
        participant=participant, name=name,
        jersey_number=data.get('jersey_number', '').strip()
    )
    return JsonResponse({'success': True, 'id': player.id, 'name': player.name,
                         'jersey_number': player.jersey_number, 'status': player.status})


@login_required
@require_POST
def remove_player(request, player_id):
    player = get_object_or_404(Player, id=player_id)
    if not is_facilitator_for(request.user, player.participant.category.sport):
        return JsonResponse({'error': 'Not authorized'}, status=403)
    player.delete()
    return JsonResponse({'success': True})


@login_required
@require_POST
def update_player_status(request, player_id):
    player = get_object_or_404(Player, id=player_id)
    if not is_facilitator_for(request.user, player.participant.category.sport):
        return JsonResponse({'error': 'Not authorized'}, status=403)
    data = json.loads(request.body)
    status = data.get('status')
    if status in ['standby', 'playing', 'done']:
        player.status = status
        player.save()
    return JsonResponse({'success': True, 'status': player.status})


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
    ann = Announcement.objects.create(message=message, created_by=request.user)
    return JsonResponse({'success': True, 'id': ann.id, 'message': ann.message})


@login_required
@require_POST
def remove_announcement(request, ann_id):
    if not (is_admin(request.user) or hasattr(request.user, 'facilitated_sport')):
        return JsonResponse({'error': 'Not authorized'}, status=403)
    ann = get_object_or_404(Announcement, id=ann_id)
    ann.is_active = False
    ann.save()
    return JsonResponse({'success': True})