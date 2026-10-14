import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yahoo_auth
from weekly_summary_tool import config as cfg
from weekly_summary_tool import scoreboard as sb
from weekly_summary_tool import digest as dg
from weekly_summary_tool import bench as bn
from weekly_summary_tool import challenges as ch

OUTPUT_DIR = './weekly_summary'


def generate_summary_for_league(yahoo_api, league, week, team_numbers):
    nickname = league['nickname']
    league_key = league['league_key']
    league_id = league['league_id']

    scoreboard_json = sb.fetch_scoreboard(yahoo_api, league_key, week)
    matchups = sb.parse_matchups(scoreboard_json)
    summary = sb.compute_league_summary(matchups)

    challenge_result = None
    challenge = ch.load_challenge(league_id, week)
    if challenge and matchups:
        try:
            challenge_result = ch.compute_challenge(yahoo_api, league_key, matchups, week, challenge)
        except Exception as e:
            print(f"Warning: could not compute Week {week} payout challenge for {nickname}: {e}")

    text = dg.format_digest(nickname, week, summary, team_numbers, challenge_result)

    print(text)
    print()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, f'week_{week}_summary_{league_id}.md')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(text)

    return text


def run_discovery(yahoo_api):
    try:
        existing = cfg.load_league_config()['leagues']
        discovered = cfg.discover_leagues(yahoo_api)
        selected = cfg.prompt_confirm_leagues(discovered, existing)
        if selected:
            cfg.save_league_config(selected)
        else:
            print("No leagues selected — config unchanged.")
    except Exception as e:
        print(f"League discovery failed: {e}")


def run_all_summaries(yahoo_api, week=None):
    league_config = cfg.load_league_config()
    leagues = league_config['leagues']
    if not leagues:
        print("No leagues configured yet. Run option A to discover and confirm leagues first.")
        return

    team_numbers = dg.load_team_numbers()
    all_texts = []
    for league in leagues:
        league_week = week if week is not None else sb.get_current_week(yahoo_api, league['league_key'])
        text = generate_summary_for_league(yahoo_api, league, league_week, team_numbers)
        all_texts.append(text)

    combined_week = week if week is not None else 'current'
    combined_path = os.path.join(OUTPUT_DIR, f'week_{combined_week}_summary_all.md')
    with open(combined_path, 'w', encoding='utf-8') as f:
        f.write("\n\n---\n\n".join(all_texts))
    print(f"Combined summary saved to {combined_path}")


def _select_leagues(leagues):
    """Prompt for a league number or 'all'. Returns a list of league dicts, or [] if invalid."""
    for i, league in enumerate(leagues, start=1):
        print(f"  {i}. {league['nickname']} ({league['league_key']})")
    choice = input("Select a league number (or 'all'): ").strip()
    if choice.lower() == 'all':
        return list(leagues)
    if not choice.isdigit() or not (1 <= int(choice) <= len(leagues)):
        print("Invalid selection.")
        return []
    return [leagues[int(choice) - 1]]


def generate_superlatives_for_league(yahoo_api, league, week, include_bench, team_numbers):
    scoreboard_json = sb.fetch_scoreboard(yahoo_api, league['league_key'], week)
    matchups = sb.parse_matchups(scoreboard_json)
    if not matchups:
        print(f"No scoreboard data available for Week {week} yet for {league['nickname']}.")
        return None

    extra = sb.compute_extra_superlatives(matchups)
    bench_result = bn.compute_bench_superlatives(yahoo_api, league['league_key'], matchups, week) if include_bench else None

    text = dg.format_superlatives(league['nickname'], week, extra, bench_result, team_numbers)
    print(text)
    print()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, f"week_{week}_superlatives_{league['league_id']}.md")
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(text)

    return text


def run_single_league_summary(yahoo_api):
    league_config = cfg.load_league_config()
    leagues = league_config['leagues']
    if not leagues:
        print("No leagues configured yet. Run option A to discover and confirm leagues first.")
        return

    selected = _select_leagues(leagues)
    if not selected:
        return

    week_input = input("Enter week number (blank for current week, per league): ").strip()
    week = int(week_input) if week_input else None

    team_numbers = dg.load_team_numbers()
    all_texts = []
    for league in selected:
        league_week = week if week is not None else sb.get_current_week(yahoo_api, league['league_key'])
        text = generate_summary_for_league(yahoo_api, league, league_week, team_numbers)
        all_texts.append(text)

    if len(selected) > 1:
        combined_week = week if week is not None else 'current'
        combined_path = os.path.join(OUTPUT_DIR, f'week_{combined_week}_summary_all.md')
        with open(combined_path, 'w', encoding='utf-8') as f:
            f.write("\n\n---\n\n".join(all_texts))
        print(f"Combined summary saved to {combined_path}")


def run_superlatives(yahoo_api):
    league_config = cfg.load_league_config()
    leagues = league_config['leagues']
    if not leagues:
        print("No leagues configured yet. Run option A to discover and confirm leagues first.")
        return

    selected = _select_leagues(leagues)
    if not selected:
        return

    week_input = input("Enter week number (blank for current week, per league): ").strip()
    week = int(week_input) if week_input else None

    include_bench = input("Include bench-points analysis? This makes extra API calls per team (y/N): ").strip().lower() == 'y'

    team_numbers = dg.load_team_numbers()
    all_texts = []
    for league in selected:
        league_week = week if week is not None else sb.get_current_week(yahoo_api, league['league_key'])
        text = generate_superlatives_for_league(yahoo_api, league, league_week, include_bench, team_numbers)
        if text:
            all_texts.append(text)

    if len(selected) > 1 and all_texts:
        combined_week = week if week is not None else 'current'
        combined_path = os.path.join(OUTPUT_DIR, f'week_{combined_week}_superlatives_all.md')
        with open(combined_path, 'w', encoding='utf-8') as f:
            f.write("\n\n---\n\n".join(all_texts))
        print(f"Combined superlatives saved to {combined_path}")


def menu(yahoo_api):
    choice = input("""
                    A: Discover/confirm leagues (update config)
                    B: Generate this week's summary for all configured leagues
                    C: Generate summary for a specific week/league
                    D: Generate superlatives for a specific week/league
                    Q: Quit

                    Please enter your choice: """).strip()

    if choice.lower() == 'a':
        run_discovery(yahoo_api)
        menu(yahoo_api)
    elif choice.lower() == 'b':
        run_all_summaries(yahoo_api)
        menu(yahoo_api)
    elif choice.lower() == 'c':
        run_single_league_summary(yahoo_api)
        menu(yahoo_api)
    elif choice.lower() == 'd':
        run_superlatives(yahoo_api)
        menu(yahoo_api)
    elif choice.lower() == 'q':
        sys.exit()
    else:
        print("You must only select either A, B, C, D, or Q")
        menu(yahoo_api)


def main():
    yahoo_api = yahoo_auth.load_yahoo_api()
    yahoo_api._login()
    menu(yahoo_api)


if __name__ == "__main__":
    main()
