import json
import os

import yahoo_auth

BASE_URL = 'https://fantasysports.yahooapis.com/fantasy/v2'


def get_current_week(yahoo_api, league_key):
    yahoo_api._login()
    url = f'{BASE_URL}/league/{league_key}'
    response = yahoo_auth.oauth.session.get(url, params={'format': 'json'})
    data = response.json()
    return int(data['fantasy_content']['league'][0]['current_week'])


def fetch_scoreboard(yahoo_api, league_key, week):
    yahoo_api._login()
    url = f'{BASE_URL}/league/{league_key}/scoreboard;week={week}'
    response = yahoo_auth.oauth.session.get(url, params={'format': 'json'})
    return response.json()


def dump_raw_scoreboard(yahoo_api, league_key, week, out_dir='./weekly_summary'):
    """Debug helper: save the raw scoreboard JSON for manual shape inspection."""
    data = fetch_scoreboard(yahoo_api, league_key, week)
    os.makedirs(out_dir, exist_ok=True)
    safe_key = league_key.replace('.', '_')
    out_path = os.path.join(out_dir, f'_raw_scoreboard_{safe_key}_wk{week}.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Raw scoreboard saved to {out_path}")
    return out_path


def _extract_team(team_entry):
    """team_entry == scoreboard_json[...]['teams'][idx]['team'], a [meta_list, stats_dict] pair."""
    meta_list = team_entry[0]
    stats = team_entry[1] if len(team_entry) > 1 else {}

    team_key = None
    name = None
    manager = None
    for item in meta_list:
        if not isinstance(item, dict):
            continue
        if 'team_key' in item:
            team_key = item['team_key']
        if 'name' in item:
            name = item['name']
        if 'managers' in item and item['managers']:
            manager = item['managers'][0]['manager'].get('nickname')

    points = float(stats.get('team_points', {}).get('total', 0.0))
    projected = float(stats.get('team_projected_points', {}).get('total', 0.0))

    return {
        'team_key': team_key,
        'name': name,
        'manager': manager,
        'points': points,
        'projected_points': projected,
    }


def parse_matchups(scoreboard_json):
    """Normalize a raw scoreboard response into a list of matchup dicts.

    Each matchup: {team_a, team_b, margin, winner, bye}
    team_a/team_b are dicts with team_key/name/manager/points, or team_b is None on a bye.
    """
    league = scoreboard_json['fantasy_content']['league']
    scoreboard = league[1]['scoreboard']
    matchups_container = scoreboard['0']['matchups']

    if matchups_container.get('count', 0) == 0:
        return []

    matchups = []
    for key, entry in matchups_container.items():
        if key == 'count':
            continue
        matchup = entry['matchup']
        teams_container = matchup['0']['teams']

        teams = []
        for tkey, tentry in teams_container.items():
            if tkey == 'count':
                continue
            teams.append(_extract_team(tentry['team']))

        if len(teams) == 2:
            team_a, team_b = teams[0], teams[1]
            margin = round(abs(team_a['points'] - team_b['points']), 2)
            if team_a['points'] > team_b['points']:
                winner = team_a['team_key']
            elif team_b['points'] > team_a['points']:
                winner = team_b['team_key']
            else:
                winner = 'tie'
            matchups.append({
                'team_a': team_a,
                'team_b': team_b,
                'margin': margin,
                'winner': winner,
                'bye': False,
            })
        elif len(teams) == 1:
            matchups.append({
                'team_a': teams[0],
                'team_b': None,
                'margin': None,
                'winner': None,
                'bye': True,
            })

    return matchups


def compute_league_summary(matchups):
    """Aggregate highest/lowest scorer and closest/biggest-margin matchups."""
    if not matchups:
        return {
            'matchups': [],
            'highest_scorer': None,
            'lowest_scorer': None,
            'closest_game': None,
            'biggest_blowout': None,
        }

    all_teams = []
    for m in matchups:
        all_teams.append(m['team_a'])
        if m['team_b'] is not None:
            all_teams.append(m['team_b'])

    highest_scorer = max(all_teams, key=lambda t: t['points'])
    lowest_scorer = min(all_teams, key=lambda t: t['points'])

    decided_matchups = [m for m in matchups if not m['bye']]
    closest_game = min(decided_matchups, key=lambda m: m['margin']) if decided_matchups else None
    biggest_blowout = max(decided_matchups, key=lambda m: m['margin']) if decided_matchups else None

    return {
        'matchups': matchups,
        'highest_scorer': highest_scorer,
        'lowest_scorer': lowest_scorer,
        'closest_game': closest_game,
        'biggest_blowout': biggest_blowout,
    }


def compute_extra_superlatives(matchups):
    """Overachiever/underachiever vs. projection, and lucky win / unlucky loss.

    Lucky win = won the matchup despite scoring lower than most of the league that week.
    Unlucky loss = lost the matchup despite scoring higher than most of the league that week.
    """
    decided_matchups = [m for m in matchups if not m['bye'] and m['winner'] != 'tie']
    if not decided_matchups:
        return {
            'overachiever': None,
            'underachiever': None,
            'lucky_win': None,
            'unlucky_loss': None,
        }

    all_teams = []
    for m in matchups:
        all_teams.append(m['team_a'])
        if m['team_b'] is not None:
            all_teams.append(m['team_b'])

    overachiever = max(all_teams, key=lambda t: t['points'] - t['projected_points'])
    underachiever = min(all_teams, key=lambda t: t['points'] - t['projected_points'])

    ranked = sorted(all_teams, key=lambda t: t['points'], reverse=True)
    rank_by_key = {t['team_key']: i for i, t in enumerate(ranked)}

    def winner_team(m):
        return m['team_a'] if m['winner'] == m['team_a']['team_key'] else m['team_b']

    def loser_team(m):
        return m['team_b'] if m['winner'] == m['team_a']['team_key'] else m['team_a']

    lucky_win_matchup = max(decided_matchups, key=lambda m: rank_by_key[winner_team(m)['team_key']])
    unlucky_loss_matchup = min(decided_matchups, key=lambda m: rank_by_key[loser_team(m)['team_key']])

    return {
        'overachiever': overachiever,
        'underachiever': underachiever,
        'lucky_win': {
            'team': winner_team(lucky_win_matchup),
            'opponent': loser_team(lucky_win_matchup),
            'league_rank': rank_by_key[winner_team(lucky_win_matchup)['team_key']] + 1,
            'league_size': len(all_teams),
        },
        'unlucky_loss': {
            'team': loser_team(unlucky_loss_matchup),
            'opponent': winner_team(unlucky_loss_matchup),
            'league_rank': rank_by_key[loser_team(unlucky_loss_matchup)['team_key']] + 1,
            'league_size': len(all_teams),
        },
    }
