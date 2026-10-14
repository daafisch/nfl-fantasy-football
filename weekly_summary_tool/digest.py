import datetime

TEAM_NUMBERS_PATH = './teams/team_numbers.txt'

_warned_missing_keys = set()


def load_team_numbers(path=TEAM_NUMBERS_PATH):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return eval(f.read())
    except FileNotFoundError:
        return {}


def resolve_team_name(team, team_numbers):
    key = team['team_key']
    if key in team_numbers:
        return team_numbers[key]
    if key not in _warned_missing_keys:
        print(f"Note: team_key {key} not found in teams/team_numbers.txt — using Yahoo team name instead.")
        _warned_missing_keys.add(key)
    return team['name'] or team['manager'] or key


def format_digest(league_nickname, week, summary, team_numbers, challenge_result=None):
    lines = [f"# Week {week} Summary — {league_nickname}", ""]

    if not summary['matchups']:
        lines.append(f"No scoreboard data available for Week {week} yet.")
        lines.append("")
        lines.append(f"_Generated {datetime.date.today().isoformat()} from Yahoo Fantasy Sports API_")
        return "\n".join(lines)

    lines.append("## Matchups")
    for m in summary['matchups']:
        name_a = resolve_team_name(m['team_a'], team_numbers)
        if m['bye']:
            lines.append(f"- {name_a} — BYE")
            continue
        name_b = resolve_team_name(m['team_b'], team_numbers)
        pts_a = m['team_a']['points']
        pts_b = m['team_b']['points']
        if m['winner'] == 'tie':
            lines.append(f"- {name_a} ({pts_a:.2f}) tied {name_b} ({pts_b:.2f})")
        elif m['winner'] == m['team_a']['team_key']:
            lines.append(f"- {name_a} ({pts_a:.2f}) def. {name_b} ({pts_b:.2f})")
        else:
            lines.append(f"- {name_b} ({pts_b:.2f}) def. {name_a} ({pts_a:.2f})")

    lines.append("")
    lines.append("## Highlights")

    hs = summary['highest_scorer']
    ls = summary['lowest_scorer']
    lines.append(f"- Highest score: {resolve_team_name(hs, team_numbers)} — {hs['points']:.2f}")
    lines.append(f"- Lowest score: {resolve_team_name(ls, team_numbers)} — {ls['points']:.2f}")

    cg = summary['closest_game']
    if cg:
        name_a = resolve_team_name(cg['team_a'], team_numbers)
        name_b = resolve_team_name(cg['team_b'], team_numbers)
        lines.append(f"- Closest game: {name_a} vs {name_b} (margin: {cg['margin']:.2f})")

    bo = summary['biggest_blowout']
    if bo:
        name_a = resolve_team_name(bo['team_a'], team_numbers)
        name_b = resolve_team_name(bo['team_b'], team_numbers)
        lines.append(f"- Biggest blowout: {name_a} vs {name_b} (margin: {bo['margin']:.2f})")

    if challenge_result:
        lines.append("")
        lines.extend(format_challenge(week, challenge_result, team_numbers))

    lines.append("")
    lines.append(f"_Generated {datetime.date.today().isoformat()} from Yahoo Fantasy Sports API_")
    return "\n".join(lines)


def format_challenge(week, result, team_numbers, show_top=3):
    challenge = result['challenge']
    lines = [f"## Weekly Payout — Week {week}: {challenge['name']}", f"_{challenge['rule']}_"]

    for w in result['winners']:
        lines.append(f"- **Winner: {resolve_team_name(w['team'], team_numbers)}** — {w['detail']}")
    if result['note']:
        lines.append(f"- {result['note']}")

    runners_up = [e for e in result['ranked'] if e not in result['winners']][:max(show_top - len(result['winners']), 0)]
    for e in runners_up:
        lines.append(f"  - Runner-up: {resolve_team_name(e['team'], team_numbers)} — {e['detail']}")
    return lines


def format_superlatives(league_nickname, week, extra, bench, team_numbers):
    lines = [f"# Week {week} Superlatives — {league_nickname}", ""]

    if extra.get('overachiever'):
        oa = extra['overachiever']
        diff = oa['points'] - oa['projected_points']
        lines.append(f"- Overachiever: {resolve_team_name(oa, team_numbers)} scored {oa['points']:.2f} vs. a {oa['projected_points']:.2f} projection (+{diff:.2f})")

    if extra.get('underachiever'):
        ua = extra['underachiever']
        diff = ua['points'] - ua['projected_points']
        lines.append(f"- Underachiever: {resolve_team_name(ua, team_numbers)} scored {ua['points']:.2f} vs. a {ua['projected_points']:.2f} projection ({diff:.2f})")

    if extra.get('lucky_win'):
        lw = extra['lucky_win']
        team = resolve_team_name(lw['team'], team_numbers)
        opp = resolve_team_name(lw['opponent'], team_numbers)
        lines.append(f"- Lucky win: {team} beat {opp} despite ranking {lw['league_rank']} of {lw['league_size']} in the league that week")

    if extra.get('unlucky_loss'):
        ul = extra['unlucky_loss']
        team = resolve_team_name(ul['team'], team_numbers)
        opp = resolve_team_name(ul['opponent'], team_numbers)
        lines.append(f"- Unlucky loss: {team} lost to {opp} despite ranking {ul['league_rank']} of {ul['league_size']} in the league that week")

    if bench and bench.get('most_wasted'):
        mw = bench['most_wasted']
        lines.append(f"- Bench regret: {resolve_team_name(mw['team'], team_numbers)} left {mw['bench_points']:.2f} points on the bench")

    if bench and bench.get('least_wasted'):
        lwaste = bench['least_wasted']
        lines.append(f"- Best lineup management: {resolve_team_name(lwaste['team'], team_numbers)} left only {lwaste['bench_points']:.2f} points on the bench")

    lines.append("")
    lines.append(f"_Generated {datetime.date.today().isoformat()} from Yahoo Fantasy Sports API_")
    return "\n".join(lines)
