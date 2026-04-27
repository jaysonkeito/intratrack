"""
Bracket generation engine for IntraTrack.
Handles Single Elimination, Double Elimination, Round Robin.
"""
import math
from .models import Match, Participant


def generate_bracket(category):
    """Entry point. Clears existing matches and regenerates."""
    Match.objects.filter(category=category).delete()
    n = category.team_count
    btype = category.bracket_type

    if btype == 'single_elimination':
        _gen_single_elim(category, n)
    elif btype == 'double_elimination':
        _gen_double_elim(category, n)
    elif btype == 'round_robin':
        _gen_round_robin(category, n)

    category.bracket_generated = True
    category.save()


def _get_participants(category):
    return list(category.participants.order_by('slot_label'))


def _gen_single_elim(category, n):
    """Standard single-elimination bracket with byes if n is not power of 2."""
    participants = _get_participants(category)
    rounds = math.ceil(math.log2(n)) if n > 1 else 1
    bracket_size = 2 ** rounds

    # Pad with None for byes
    slots = participants + [None] * (bracket_size - n)

    # Round 1 matches
    round1_matches = []
    match_num = 1
    for i in range(0, len(slots), 2):
        a, b = slots[i], slots[i + 1]
        m = Match.objects.create(
            category=category,
            participant_a=a,
            participant_b=b,
            round_number=1,
            match_number=match_num,
            bracket_slot=f'R1M{match_num}',
            status='scheduled' if (a and b) else 'finished',  # auto-advance bye
            score_a=1 if (a and not b) else 0,
            score_b=0,
        )
        round1_matches.append(m)
        match_num += 1

    # Subsequent rounds (TBD participants)
    prev_round = round1_matches
    for r in range(2, rounds + 1):
        current_round = []
        match_num = 1
        for i in range(0, len(prev_round), 2):
            m = Match.objects.create(
                category=category,
                participant_a=None,
                participant_b=None,
                round_number=r,
                match_number=match_num,
                bracket_slot=f'R{r}M{match_num}',
                status='scheduled',
            )
            current_round.append(m)
            match_num += 1
        prev_round = current_round


def _gen_double_elim(category, n):
    """
    Double elimination: winners bracket + losers bracket.
    Simplified: generate winners bracket normally, plus losers bracket shells.
    """
    _gen_single_elim(category, n)  # winners bracket
    # Losers bracket rounds = 2*(ceil(log2(n))-1)
    rounds = math.ceil(math.log2(n)) if n > 1 else 1
    lb_rounds = max(1, 2 * (rounds - 1))
    for r in range(1, lb_rounds + 1):
        matches_in_round = max(1, n // (2 ** (r // 2 + 1)))
        for mn in range(1, matches_in_round + 1):
            Match.objects.create(
                category=category,
                participant_a=None,
                participant_b=None,
                round_number=100 + r,   # 100+ = losers bracket
                match_number=mn,
                bracket_slot=f'LB_R{r}M{mn}',
                status='scheduled',
            )
    # Grand final shell
    Match.objects.create(
        category=category,
        participant_a=None,
        participant_b=None,
        round_number=200,
        match_number=1,
        bracket_slot='GF',
        status='scheduled',
    )


def _gen_round_robin(category, n):
    """
    Round-robin: every team plays every other team once.
    Uses circle method for scheduling.
    """
    participants = _get_participants(category)
    if n % 2 == 1:
        participants.append(None)  # bye

    total = len(participants)
    rounds = total - 1
    match_num_global = 1

    for r in range(rounds):
        fixed = participants[0]
        rotating = participants[1:]
        rotated = rotating[-r:] + rotating[:-r] if r > 0 else rotating

        pairing = [(fixed, rotated[0])] + [
            (rotated[i], rotated[-(i + 1)]) for i in range(1, total // 2)
        ]

        mn = 1
        for a, b in pairing:
            if a is None or b is None:
                continue  # skip bye
            Match.objects.create(
                category=category,
                participant_a=a,
                participant_b=b,
                round_number=r + 1,
                match_number=mn,
                bracket_slot=f'RR_R{r+1}M{mn}',
                status='scheduled',
            )
            mn += 1
            match_num_global += 1


def advance_winner(match):
    """
    After a match is finished in single/double elim, find the next match
    that this match's winner should feed into and assign them.
    """
    if match.status != 'finished':
        return
    if match.category.bracket_type == 'round_robin':
        return  # no advancement needed

    winner = match.winner_participant()
    if not winner:
        return

    # Find the next round match that has no participant_a or participant_b yet
    next_match_num = math.ceil(match.match_number / 2)
    next_match = Match.objects.filter(
        category=match.category,
        round_number=match.round_number + 1,
        match_number=next_match_num,
    ).first()

    if not next_match:
        return

    # Place winner in the correct slot
    if match.match_number % 2 == 1:
        next_match.participant_a = winner
    else:
        next_match.participant_b = winner
    next_match.save()
