import json
import os

import yahoo_auth
from weekly_summary_tool import bench as bn
from weekly_summary_tool import scoreboard as sb

BASE_URL = 'https://fantasysports.yahooapis.com/fantasy/v2'
DEFAULT_CHALLENGES_PATH = './Initial_Setup/weekly_challenges.json'

NON_STARTER_SLOTS = {'BN', 'IR', 'IR+', 'NA'}
FLEX_SLOT = 'W/R/T'

# Fallbacks if the league settings lookup fails (Yahoo's standard NFL stat IDs).
DEFAULT_STAT_IDS = {'pass_yds': '4', 'rec_yds': '12'}
STAT_NAMES = {
    'pass_yds': ('Pass Yds', 'Passing Yards'),
    'rec_yds': ('Rec Yds', 'Receiving Yards'),
}

PLAYER_TYPES = {
    'top_starter', 'bench_total', 'top_flex', 'top_rb', 'top_pass_yds',
    'top_wr_te_rec_yds', 'top_starter_on_loser',
}


def load_challenge(league_id, week, path=DEFAULT_CHALLENGES_PATH):
    """Returns the challenge dict (name, rule, type) for this league/week, or None."""
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as f:
        schedule = json.load(f)
    return schedule.get(str(league_id), {}).get(str(week))


def fetch_stat_ids(yahoo_api, league_key):
    """Look up the stat IDs for passing/receiving yards from the league's settings."""
    ids = dict(DEFAULT_STAT_IDS)
    try:
        yahoo_api._login()
        url = f'{BASE_URL}/league/{league_key}/settings'
        response = yahoo_auth.oauth.session.get(url, params={'format': 'json'})
        settings = response.json()['fantasy_content']['league'][1]['settings'][0]
        for s in settings['stat_categories']['stats']:
            stat = s['stat']
            for key, names in STAT_NAMES.items():
                if stat.get('display_name') in names or stat.get('name') in names:
                    ids[key] = str(stat['stat_id'])
    except Exception as e:
        print(f"Could not read stat categories ({e}); using default stat IDs {ids}.")
    return ids


def _all_teams(matchups):
    teams = []
    for m in matchups:
        teams.append(m['team_a'])
        if m['team_b'] is not None:
            teams.append(m['team_b'])
    return teams


def _winner_loser(m):
    """Returns (winner, loser) team dicts, or None for byes and ties."""
    if m['bye'] or m['winner'] == 'tie':
        return None
    if m['winner'] == m['team_a']['team_key']:
        return m['team_a'], m['team_b']
    return m['team_b'], m['team_a']


def _losers_by_team_key(matchups):
    keys = set()
    for m in matchups:
        wl = _winner_loser(m)
        if wl:
            keys.add(wl[1]['team_key'])
    return keys


def _fetch_lineups(yahoo_api, league_key, matchups, week):
    """Returns [(team, [player dicts with points/stats])] for every team in the matchups."""
    lineups = []
    for team in _all_teams(matchups):
        roster_json = bn.fetch_roster(yahoo_api, team['team_key'], week)
        lineup = bn.get_lineup(roster_json)
        stats = bn.fetch_player_stats(yahoo_api, league_key, [p['player_key'] for p in lineup if p['player_key']], week)
        for p in lineup:
            s = stats.get(p['player_key'], {})
            p['points'] = s.get('points', 0.0)
            p['stats'] = s.get('stats', {})
        lineups.append((team, lineup))
    return lineups


def _player_entries(lineups, predicate, value_fn, unit='pts'):
    entries = []
    for team, lineup in lineups:
        for p in lineup:
            if predicate(team, p):
                value = value_fn(p)
                entries.append({
                    'team': team,
                    'value': value,
                    'detail': f"{p['name']} ({p['slot']}) — {value:.2f} {unit}" if unit == 'pts'
                              else f"{p['name']} ({p['slot']}) — {value:.0f} {unit}",
                })
    return entries


def season_average(yahoo_api, league_key, through_week):
    """Average team score across every team-week from week 1 through through_week."""
    scores = []
    for wk in range(1, through_week + 1):
        matchups = sb.parse_matchups(sb.fetch_scoreboard(yahoo_api, league_key, wk))
        scores.extend(t['points'] for t in _all_teams(matchups))
    return round(sum(scores) / len(scores), 2) if scores else None


def _resolve_target(yahoo_api, league_key, week, challenge):
    """A challenge 'target' is either a number or 'season_avg' (average of all prior weeks)."""
    target = challenge.get('target', 100.0)
    if target == 'season_avg':
        avg = season_average(yahoo_api, league_key, week - 1)
        if avg is None:
            raise ValueError("No prior weeks to average for the target score.")
        return avg
    return float(target)


def _is_starter(p):
    return p['slot'] not in NON_STARTER_SLOTS


def compute_challenge(yahoo_api, league_key, matchups, week, challenge):
    """Rank every candidate for this week's challenge.

    Returns {'challenge': challenge, 'ranked': [{team, value, detail}, ...] best-first,
    'winners': [...entries tied for first], 'note': str or None}.
    """
    ctype = challenge['type']
    ranked = []
    lower_is_better = False
    fallback_note = None

    if ctype in PLAYER_TYPES:
        lineups = _fetch_lineups(yahoo_api, league_key, matchups, week)

    if ctype == 'top_starter':
        ranked = _player_entries(lineups, lambda t, p: _is_starter(p), lambda p: p['points'])
    elif ctype == 'top_flex':
        ranked = _player_entries(lineups, lambda t, p: p['slot'] == FLEX_SLOT, lambda p: p['points'])
    elif ctype == 'top_rb':
        ranked = _player_entries(lineups, lambda t, p: _is_starter(p) and p['position'] == 'RB', lambda p: p['points'])
    elif ctype == 'top_pass_yds':
        stat_id = fetch_stat_ids(yahoo_api, league_key)['pass_yds']
        ranked = _player_entries(lineups, lambda t, p: _is_starter(p) and p['position'] == 'QB',
                                 lambda p: p['stats'].get(stat_id, 0.0), unit='pass yds')
    elif ctype == 'top_wr_te_rec_yds':
        stat_id = fetch_stat_ids(yahoo_api, league_key)['rec_yds']
        ranked = _player_entries(lineups, lambda t, p: _is_starter(p) and p['position'] in ('WR', 'TE'),
                                 lambda p: p['stats'].get(stat_id, 0.0), unit='rec yds')
    elif ctype == 'top_starter_on_loser':
        losers = _losers_by_team_key(matchups)
        ranked = _player_entries(lineups, lambda t, p: _is_starter(p) and t['team_key'] in losers, lambda p: p['points'])
    elif ctype == 'bench_total':
        for team, lineup in lineups:
            total = round(sum(p['points'] for p in lineup if p['slot'] == 'BN'), 2)
            ranked.append({'team': team, 'value': total, 'detail': f"{total:.2f} bench pts"})

    elif ctype == 'closest_loss':
        lower_is_better = True
        for m in matchups:
            wl = _winner_loser(m)
            if wl:
                ranked.append({'team': wl[1], 'value': m['margin'],
                               'detail': f"lost {wl[1]['points']:.2f}–{wl[0]['points']:.2f} (margin {m['margin']:.2f})"})
    elif ctype == 'largest_win':
        for m in matchups:
            wl = _winner_loser(m)
            if wl:
                ranked.append({'team': wl[0], 'value': m['margin'],
                               'detail': f"won {wl[0]['points']:.2f}–{wl[1]['points']:.2f} (margin {m['margin']:.2f})"})
    elif ctype == 'high_score_loser':
        for m in matchups:
            wl = _winner_loser(m)
            if wl:
                ranked.append({'team': wl[1], 'value': wl[1]['points'], 'detail': f"{wl[1]['points']:.2f} pts in a loss"})
    elif ctype == 'barnburner':
        for m in matchups:
            wl = _winner_loser(m)
            if wl:
                combined = round(wl[0]['points'] + wl[1]['points'], 2)
                ranked.append({'team': wl[0], 'value': combined,
                               'detail': f"won {wl[0]['points']:.2f}–{wl[1]['points']:.2f} ({combined:.2f} combined)"})
    elif ctype == 'low_score_winner':
        lower_is_better = True
        for m in matchups:
            wl = _winner_loser(m)
            if wl:
                ranked.append({'team': wl[0], 'value': wl[0]['points'], 'detail': f"won with {wl[0]['points']:.2f} pts"})
    elif ctype == 'closest_to_target_under':
        target = _resolve_target(yahoo_api, league_key, week, challenge)
        teams = _all_teams(matchups)
        under = [t for t in teams if t['points'] <= target]
        if under:
            for t in under:
                ranked.append({'team': t, 'value': t['points'],
                               'detail': f"{t['points']:.2f} pts ({target - t['points']:.2f} under the {target:.2f} target)"})
        else:
            # Nobody stayed under: the team that went over by the least wins, so there's always a winner.
            lower_is_better = True
            for t in teams:
                ranked.append({'team': t, 'value': t['points'],
                               'detail': f"{t['points']:.2f} pts ({t['points'] - target:.2f} over the {target:.2f} target)"})
            fallback_note = f"Every team went over the {target:.2f} target — closest over wins."
    elif ctype == 'high_score':
        for t in _all_teams(matchups):
            ranked.append({'team': t, 'value': t['points'], 'detail': f"{t['points']:.2f} pts"})
    else:
        raise ValueError(f"Unknown challenge type: {ctype}")

    ranked.sort(key=lambda e: e['value'], reverse=not lower_is_better)

    winners = []
    note = None
    if ranked:
        best = ranked[0]['value']
        winners = [e for e in ranked if round(e['value'], 2) == round(best, 2)]
        if len(winners) > 1:
            note = "Tie — split between co-winners."
        if fallback_note:
            note = f"{fallback_note} {note}" if note else fallback_note
    else:
        note = "No eligible entries found."

    return {'challenge': challenge, 'ranked': ranked, 'winners': winners, 'note': note}
