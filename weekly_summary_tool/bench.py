import yahoo_auth

BASE_URL = 'https://fantasysports.yahooapis.com/fantasy/v2'


def fetch_roster(yahoo_api, team_key, week):
    yahoo_api._login()
    url = f'{BASE_URL}/team/{team_key}/roster;week={week}'
    response = yahoo_auth.oauth.session.get(url, params={'format': 'json'})
    return response.json()


def _player_name_and_position(player_entry):
    meta_list = player_entry[0]
    extra = player_entry[1] if len(player_entry) > 1 else {}

    player_key = None
    name = None
    for item in meta_list:
        if not isinstance(item, dict):
            continue
        if 'player_key' in item:
            player_key = item['player_key']
        if 'name' in item:
            name = item['name'].get('full')

    position = None
    for item in extra.get('selected_position', []):
        if isinstance(item, dict) and 'position' in item:
            position = item['position']
            break

    return player_key, name, position


def get_bench_players(roster_json):
    """Returns [(player_key, name), ...] for players slotted at BN this week."""
    team = roster_json['fantasy_content']['team']
    players_container = team[1]['roster']['0']['players']

    bench = []
    for key, entry in players_container.items():
        if key == 'count':
            continue
        player_key, name, position = _player_name_and_position(entry['player'])
        if position == 'BN':
            bench.append((player_key, name))
    return bench


def get_lineup(roster_json):
    """Returns every rostered player as {player_key, name, slot, position}.

    slot is the selected roster slot (QB, RB, W/R/T, BN, ...); position is the player's
    primary position (QB, RB, WR, TE, K, DEF).
    """
    team = roster_json['fantasy_content']['team']
    players_container = team[1]['roster']['0']['players']

    lineup = []
    for key, entry in players_container.items():
        if key == 'count':
            continue
        player_key, name, slot = _player_name_and_position(entry['player'])
        position = None
        for item in entry['player'][0]:
            if isinstance(item, dict) and 'primary_position' in item:
                position = item['primary_position']
            elif isinstance(item, dict) and 'display_position' in item and position is None:
                position = item['display_position'].split(',')[0]
        lineup.append({'player_key': player_key, 'name': name, 'slot': slot, 'position': position})
    return lineup


def fetch_player_stats(yahoo_api, league_key, player_keys, week):
    """Returns {player_key: {'points': float, 'stats': {stat_id: float}}} for the given player_keys."""
    if not player_keys:
        return {}
    yahoo_api._login()
    result = {}
    # Yahoo caps player_keys at 25 per request.
    for i in range(0, len(player_keys), 25):
        keys_param = ','.join(player_keys[i:i + 25])
        url = f'{BASE_URL}/league/{league_key}/players;player_keys={keys_param}/stats;type=week;week={week}'
        response = yahoo_auth.oauth.session.get(url, params={'format': 'json'})
        data = response.json()

        players_container = data['fantasy_content']['league'][1]['players']
        for key, entry in players_container.items():
            if key == 'count':
                continue
            player = entry['player']
            meta_list = player[0]
            stats = player[1] if len(player) > 1 else {}
            player_key = next((item['player_key'] for item in meta_list if isinstance(item, dict) and 'player_key' in item), None)
            if not player_key:
                continue
            stat_values = {}
            for s in stats.get('player_stats', {}).get('stats', []):
                stat = s.get('stat', {})
                try:
                    stat_values[str(stat['stat_id'])] = float(stat.get('value') or 0)
                except (KeyError, ValueError):
                    continue
            result[player_key] = {
                'points': float(stats.get('player_points', {}).get('total', 0.0)),
                'stats': stat_values,
            }
    return result


def fetch_player_points(yahoo_api, league_key, player_keys, week):
    """Returns {player_key: points} for the given list of player_keys."""
    stats = fetch_player_stats(yahoo_api, league_key, player_keys, week)
    return {pk: s['points'] for pk, s in stats.items()}


def compute_team_bench_points(yahoo_api, league_key, team_key, week):
    """Returns (bench_total, [(name, points), ...]) for one team's bench that week."""
    roster_json = fetch_roster(yahoo_api, team_key, week)
    bench_players = get_bench_players(roster_json)
    player_keys = [pk for pk, _ in bench_players if pk]

    points_by_key = fetch_player_points(yahoo_api, league_key, player_keys, week)

    bench_detail = []
    total = 0.0
    for player_key, name in bench_players:
        pts = points_by_key.get(player_key, 0.0)
        bench_detail.append((name, pts))
        total += pts

    return round(total, 2), bench_detail


def compute_bench_superlatives(yahoo_api, league_key, matchups, week):
    """For every team in the given matchups, compute bench points left on the table."""
    teams = []
    for m in matchups:
        teams.append(m['team_a'])
        if m['team_b'] is not None:
            teams.append(m['team_b'])

    per_team = []
    for team in teams:
        bench_total, bench_detail = compute_team_bench_points(yahoo_api, league_key, team['team_key'], week)
        per_team.append({
            'team': team,
            'bench_points': bench_total,
            'bench_detail': bench_detail,
        })

    if not per_team:
        return {'most_wasted': None, 'least_wasted': None, 'per_team': []}

    most_wasted = max(per_team, key=lambda t: t['bench_points'])
    least_wasted = min(per_team, key=lambda t: t['bench_points'])

    return {
        'most_wasted': most_wasted,
        'least_wasted': least_wasted,
        'per_team': per_team,
    }
