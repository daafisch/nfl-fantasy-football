import json
import os
import datetime

import yahoo_auth

DISCOVERY_URL = 'https://fantasysports.yahooapis.com/fantasy/v2/users;use_login=1/games;game_codes=nfl/leagues'
DEFAULT_CONFIG_PATH = './Initial_Setup/weekly_leagues_config.json'


def discover_leagues(yahoo_api):
    """Fetch every NFL league the logged-in Yahoo account has ever been in.

    Returns a list of dicts: league_key, league_id, game_key, name, num_teams, season
    """
    yahoo_api._login()
    response = yahoo_auth.oauth.session.get(DISCOVERY_URL, params={'format': 'json'})
    data = response.json()

    leagues = []
    games = data['fantasy_content']['users']['0']['user'][1]['games']
    for game_idx in games:
        if game_idx == 'count':
            continue
        game = games[game_idx]['game']
        game_meta = game[0]
        game_key = game_meta['game_key']
        season = game_meta['season']
        if len(game) < 2 or 'leagues' not in game[1]:
            continue
        game_leagues = game[1]['leagues']
        for league_idx in game_leagues:
            if league_idx == 'count':
                continue
            league = game_leagues[league_idx]['league'][0]
            leagues.append({
                'league_key': league['league_key'],
                'league_id': league['league_id'],
                'game_key': game_key,
                'name': league['name'],
                'num_teams': league['num_teams'],
                'season': season,
            })
    return leagues


def current_season_leagues(discovered):
    """Narrow a full discovery result down to the most recent season found."""
    if not discovered:
        return []
    latest_season = max(int(l['season']) for l in discovered)
    return [l for l in discovered if int(l['season']) == latest_season]


def load_league_config(config_path=DEFAULT_CONFIG_PATH):
    if not os.path.exists(config_path):
        return {'leagues': []}
    with open(config_path, encoding='utf-8') as f:
        return json.load(f)


def prompt_confirm_leagues(discovered, existing):
    """Show discovered leagues (most recent season) and let the user pick which to track."""
    candidates = current_season_leagues(discovered)
    if not candidates:
        print("No leagues found for the current season.")
        return []

    existing_keys = {l['league_key'] for l in existing}
    season = candidates[0]['season']

    print(f"\nDiscovered leagues for the {season} NFL season:")
    for i, league in enumerate(candidates, start=1):
        tag = '[existing]' if league['league_key'] in existing_keys else '[NEW]'
        print(f"  {i}. {tag:10} {league['name']:25} ({league['league_key']}, {league['num_teams']} teams)")

    choice = input("\nEnter the numbers of leagues to include (comma-separated, or 'all'): ").strip()
    if choice.lower() == 'all':
        selected_indices = range(1, len(candidates) + 1)
    else:
        selected_indices = []
        for part in choice.split(','):
            part = part.strip()
            if part.isdigit():
                selected_indices.append(int(part))

    selected = []
    for idx in selected_indices:
        if idx < 1 or idx > len(candidates):
            continue
        league = candidates[idx - 1]
        if league['league_key'] not in existing_keys:
            nickname = input(f"Nickname for \"{league['name']}\" [{league['name']}]: ").strip()
            league['nickname'] = nickname if nickname else league['name']
        selected.append(league)

    return selected


def save_league_config(selected, config_path=DEFAULT_CONFIG_PATH):
    """Merge newly confirmed leagues into the config file. Additive-only, keyed by league_key."""
    config = load_league_config(config_path)
    existing_by_key = {l['league_key']: l for l in config['leagues']}

    added = 0
    for league in selected:
        if league['league_key'] in existing_by_key:
            continue
        existing_by_key[league['league_key']] = {
            'nickname': league.get('nickname', league['name']),
            'league_id': league['league_id'],
            'game_key': league['game_key'],
            'league_key': league['league_key'],
            'num_teams': league['num_teams'],
            'season': league['season'],
            'added_on': datetime.date.today().isoformat(),
        }
        added += 1

    config['leagues'] = list(existing_by_key.values())

    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"\nSaved {len(config['leagues'])} league(s) to {config_path} ({added} newly added).")
    return config
