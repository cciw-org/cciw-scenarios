"""
Builds the playoff scenarios page for each sport in sports.py.
Run:  python3 make_page.py            (all sports)
      python3 make_page.py wsoc       (one sport)
Each page is written to that sport's folder as index.html.
"""
import csv
import html
import json
import os
import random
import sys
from collections import defaultdict, Counter
from datetime import datetime
from itertools import product, combinations

import cciw_tiebreaker
import tennis_tiebreaker
import vb_tiebreaker
from sports import SPORTS, LOGO_URL

ENGINES = {"soccer": cciw_tiebreaker, "volleyball": vb_tiebreaker, "tennis": tennis_tiebreaker}
SCENARIOS_UP_TO = {"soccer": 10, "volleyball": 13, "tennis": 13}   # more left than this: skip scenarios
NUM = ["No", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
       "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen"]
esc = html.escape


def word(n, cap=True):
    w = NUM[n] if n < len(NUM) else str(n)
    return w if cap else w.lower()


def build(key):
    cfg = SPORTS[key]
    E = ENGINES[cfg["kind"]]
    Q = cfg["qualifiers"]
    folder = cfg["folder"]
    games_file = os.path.join(folder, "games.csv")
    played, remaining = E.load_games(games_file)
    teams = sorted({t for g in played for t in g[:2]} | {t for g in remaining for t in g})
    n = len(remaining)
    g1, gN = E.GAME_WORD

    # ---------- dates ----------
    dates, played_dates = {}, []
    with open(games_file, newline="") as f:
        for r in csv.DictReader(f):
            try:
                d = datetime.strptime(r["date"].strip()[:10].strip(), "%m/%d/%Y")
            except ValueError:
                d = None
            if str(r["home_goals"]).strip() == "":
                dates[(r["home"].strip(), r["away"].strip())] = d
            elif d:
                played_dates.append(d)

    def day(d, weekday=True):
        if not d:
            return ""
        s = f"{d.strftime('%b')}. {d.day}" if d.month != 5 else f"May {d.day}"
        return (d.strftime("%a") + "., " + s) if weekday else s

    def game_name(g):
        h, a = g
        when = day(dates.get(g))
        return f"{a} at {h}" + (f" ({when})" if when else "")

    def outcome_label(g, r):
        h, a = g
        return {"H": f"{h} wins", "D": "Tie", "A": f"{a} wins"}[r]

    # ---------- run every scenario ----------
    rng = random.Random(0)
    by_pattern = defaultdict(set)
    overall = defaultdict(lambda: [99, 0])
    if n <= SCENARIOS_UP_TO[cfg["kind"]]:
        for pattern in product(E.RESULTS, repeat=n):
            if n <= E.EXACT_UP_TO:
                variants = product(*[E.SCORES[r] for r in pattern])
            else:
                variants = [tuple(E.NOMINAL[r] for r in pattern),
                            tuple(E.SCORES[r][0] for r in pattern),
                            tuple(E.SCORES[r][-1] for r in pattern)]
                variants += [tuple(rng.choice(E.SCORES[r]) for r in pattern) for _ in range(E.SAMPLES)]
            for combo in variants:
                sim = [(h, a, x, y) for (h, a), (x, y) in zip(remaining, combo)]
                pl = E.places(E.rank(played + sim, teams))
                by_pattern[pattern].add(tuple(sorted(pl.items())))
                for t, (b, w) in pl.items():
                    overall[t][0] = min(overall[t][0], b)
                    overall[t][1] = max(overall[t][1], w)
    known = bool(overall)

    # ---------- clinched / alive / eliminated ----------
    current = E.places(E.rank(played, teams))
    order_now = sorted(teams, key=lambda t: current[t])
    if known:
        clinched = [t for t in order_now if overall[t][1] <= Q]
        eliminated = [t for t in order_now if overall[t][0] > Q]
        alive = [t for t in order_now if t not in clinched and t not in eliminated]
    else:
        clinched, eliminated, alive = [], [], order_now

    def chips(ts, kind, empty):
        if not ts:
            return f"<p class='none'>{empty}</p>"
        return "".join(f"<span class='chip {kind}'>{esc(t)}</span>" for t in ts)

    # ---------- contested blocks of places ----------
    blocks = []
    if known:
        for b, w in sorted((overall[t][0], overall[t][1]) for t in teams if overall[t][0] != overall[t][1]):
            if blocks and b <= blocks[-1][1]:
                blocks[-1][1] = max(blocks[-1][1], w)
            else:
                blocks.append([b, w])
        blocks = [(b, w) for b, w in blocks if b <= Q]

    def cell_for(outs, lo, hi, berth, ts=()):
        """What a grid cell says for a set of possible outcomes. Returns (content, depends_on_scores)."""
        if berth:
            maybe = sorted({t for pl in outs for t, (b, w) in pl if t in ts and w > Q})
            sure = sorted(t for t in maybe if all(dict(pl)[t][0] > Q for pl in outs))
            if sure == maybe:
                return " & ".join(sure) or "Nobody", False
            return " or ".join(maybe) + "*", True
        lines = []
        for p in range(lo, hi + 1):
            lines.append((p, sorted({t for pl in outs for t, (b, w) in pl if b <= p <= w})))
        return tuple((p, tuple(w)) for p, w in lines), any(len(w) > 1 for _, w in lines)

    def deciding_games(lo, hi, berth, involved_idx, ts):
        """Smallest set of games whose results alone decide this block (up to 4)."""
        patterns = list(by_pattern)
        cells = {p: cell_for(by_pattern[p], lo, hi, berth, ts)[0] for p in patterns}
        for size in range(0, min(4, len(involved_idx)) + 1):
            for S in combinations(involved_idx, size):
                seen = {}
                ok = True
                for p in patterns:
                    proj = tuple(p[i] for i in S)
                    if proj in seen and seen[proj] != cells[p]:
                        ok = False
                        break
                    seen.setdefault(proj, cells[p])
                if ok:
                    groups = defaultdict(set)
                    for p in patterns:
                        groups[tuple(p[i] for i in S)] |= by_pattern[p]
                    return S, groups
        return None, None

    def render(content):
        if isinstance(content, str):
            return esc(content)
        return "".join(
            f"<div><span class='pl'>{p}</span>{esc(' or '.join(who))}{'*' if len(who) > 1 else ''}</div>"
            for p, who in content)


    # ---------- team-by-team "what each team needs" table ----------
    def status_of(outs, t):
        if all(dict(pl)[t][1] <= Q for pl in outs):
            return "in"
        if all(dict(pl)[t][0] > Q for pl in outs):
            return "out"
        return "dep"

    def phrase(g, r):
        h, a = g
        return {"H": f"{h} beats {a}", "A": f"{a} beats {h}", "D": f"{a} and {h} tie"}[r]

    def not_phrase(g, r):
        h, a = g
        return {"H": f"{h} doesn't beat {a}", "A": f"{a} doesn't beat {h}", "D": f"{a} and {h} don't tie"}[r]

    def one_of(g, rs):
        rs = [r for r in E.RESULTS if r in rs]
        if len(rs) == len(E.RESULTS) - 1 and len(E.RESULTS) == 3:
            return not_phrase(g, [r for r in E.RESULTS if r not in rs][0])
        return " or ".join(phrase(g, r) for r in rs)

    def describe(S, projs):
        """Readable text for a set of result combinations of the games S."""
        if not S:
            return ""
        if len(S) == 1:
            return one_of(remaining[S[0]], {p[0] for p in projs})
        parts = []
        for r1 in E.RESULTS:
            rs = {p[1] for p in projs if p[0] == r1}
            if not rs:
                continue
            g1_, g2_ = remaining[S[0]], remaining[S[1]]
            if len(rs) == len(E.RESULTS):
                parts.append(phrase(g1_, r1))
            else:
                parts.append(f"{phrase(g1_, r1)} and {one_of(g2_, rs)}")
        return "; or ".join(parts)

    def condition(ps, st, others):
        for size in (1, 2):
            for S in combinations(others, size):
                seen, ok = {}, True
                for p in ps:
                    proj = tuple(p[i] for i in S)
                    if seen.setdefault(proj, st[p]) != st[p]:
                        ok = False
                        break
                if not ok:
                    continue
                ins = [k for k, v in seen.items() if v == "in"]
                outs = [k for k, v in seen.items() if v == "out"]
                deps = [k for k, v in seen.items() if v == "dep"]
                if not deps and outs and len(outs) < len(ins):
                    text = "In unless " + describe(list(S), outs)
                elif ins:
                    text = "In if " + describe(list(S), ins)
                else:
                    text = "Out"
                if deps:
                    text += (". " if ins else "; ") + "Tiebreak on scores if " + describe(list(S), deps)
                return text, "help"
        k = sum(1 for p in ps if st[p] == "in")
        d = sum(1 for p in ps if st[p] == "dep")
        m = len(ps)
        if k == 0:
            return (f"Out unless a tiebreak on exact scores goes its way "
                    f"(possible in {d} of {m} result combinations)"), "help"
        extra = f"; tiebreak on exact scores in {d} more" if d else ""
        return f"Needs help: in for {k} of {m} possible result combinations{extra}", "help"

    def team_table(alive_ts):
        rows, ncols = [], 1
        for t in alive_ts:
            own = [i for i, g in enumerate(remaining) if t in g]

            def cat(p):
                if cfg["kind"] == "soccer":
                    return sum(3 if (p[i] == "H") == (remaining[i][0] == t) and p[i] != "D" else
                               1 if p[i] == "D" else 0 for i in own)
                return sum((p[i] == "H") == (remaining[i][0] == t) for i in own)

            def cat_label(c):
                k = len(own)
                if k == 0:
                    return "Season complete"
                if cfg["kind"] == "soccer":
                    return {3: "Win", 1: "Tie", 0: "Loss"}[c] if k == 1 else f"{c} more pts"
                return "Win" if (k == 1 and c == 1) else "Loss" if (k == 1) else f"Goes {c}-{k - c}"

            cats = defaultdict(list)
            for p in by_pattern:
                cats[cat(p)].append(p)
            cells = []
            for c in sorted(cats, reverse=True):
                ps = cats[c]
                st = {p: status_of(by_pattern[p], t) for p in ps}
                vals = set(st.values())
                if vals == {"in"}:
                    text, cls = "In", "in"
                elif vals == {"out"}:
                    text, cls = "Out", "out"
                else:
                    text, cls = condition(ps, st, [i for i in range(n) if i not in own])
                cells.append((cat_label(c), text, cls))
            rows.append((t, own, cells))
            ncols = max(ncols, len(cells))
        html_rows = ""
        for t, own, cells in rows:
            own_txt = "; ".join(esc(game_name(remaining[i])) for i in own) or "Season complete"
            html_rows += (f"<tr><td class='rowh'>{esc(t)}<div class='gl'>{own_txt}</div></td>" +
                          "".join(f"<td><span class='ol'>{esc(lbl)}</span><span class='st {cls}'>{esc(txt)}</span></td>"
                                  for lbl, txt, cls in cells) +
                          "<td></td>" * (ncols - len(cells)) + "</tr>")
        head = "<tr><th>Team</th>" + "".join(f"<th>Own results</th>" if i == 0 else "<th></th>" for i in range(ncols)) + "</tr>"
        return f"<div class='tw'><table class='teams'>{head}{html_rows}</table></div>"

    def block_section(lo, hi):
        berth = lo <= Q < hi
        ts = sorted({t for t in teams if overall[t][0] >= lo and overall[t][0] <= hi}, key=lambda t: current[t])
        names = ", ".join(ts[:-1]) + (" and " if len(ts) > 1 else "") + ts[-1]
        if berth:
            ts = [t for t in ts if t in alive] or ts
            names = ", ".join(ts[:-1]) + (" and " if len(ts) > 1 else "") + ts[-1]
            spots = Q - len(clinched)
            title = "The last spot" if spots == 1 else f"The last {word(spots, False)} spots"
            lead = (f"{names} are competing for {spots} playoff spot{'s' if spots > 1 else ''}. "
                    f"{word(len(ts) - spots)} of them will miss the {cfg['tournament']}.")
        else:
            title = (f"The race for No. 1" + (f" (seeds 1 to {hi})" if hi > 1 else "")) if lo == 1 else \
                    (f"No. {lo} seed" if hi == lo else f"Seeds No. {lo} to No. {hi}")
            lead = f"{names} will finish somewhere from No. {lo} to No. {hi}."
        involved_idx = [i for i, g in enumerate(remaining) if g[0] in ts or g[1] in ts]
        pts = ". ".join(f"{esc(t)}: {E.final_line(t, played, sum(t in g for g in remaining))}" for t in ts)

        S, groups = deciding_games(lo, hi, berth, list(range(n)), ts)
        too_many = S is not None and len(S) not in (0, 1, 2) and len(groups) > 12
        if S is None or too_many:
            if berth:
                alive_ts = [t for t in ts if t in alive]
                sub = (f"Too many {gN} affect this race for one table, so here is what each team needs. Counts treat every combination of results as equally likely. "
                       f"&ldquo;In&rdquo; and &ldquo;Out&rdquo; are guaranteed whatever else happens.")
                grid = (f"<p class='small'><b>What each team needs</b>, by its own results.</p>" + team_table(alive_ts))
            else:
                sub = (f"Too many {gN} affect this race to show in a table. "
                       f"Use the scenario builder below to try any combination.")
                grid = ""
            foot, star = "", ""
        else:
            dg = [remaining[i] for i in S]
            if not dg:
                sub = f"The remaining {gN} can't change who finishes where, except through exact scores."
            else:
                cnt = word(len(dg))
                sub = (f"{cnt} {g1 if len(dg) == 1 else gN} decide{'s' if len(dg) == 1 else ''} it: "
                       + " and ".join(esc(game_name(g)) for g in dg) + ".")
            cells = {proj: cell_for(outs, lo, hi, berth, ts) for proj, outs in groups.items()}
            any_dep = any(dep for _, dep in cells.values())
            keys = sorted(cells, key=lambda p: [E.RESULTS.index(x) for x in p])
            if len(dg) == 2:
                (h1, a1), (h2, a2) = dg
                head = (f"<tr><th>{esc(a1)} at {esc(h1)}</th>" +
                        "".join(f"<th class='r'>{esc(outcome_label(dg[1], r))}</th>" for r in E.RESULTS) + "</tr>")
                body = "".join(
                    f"<tr><td class='rowh'>{esc(outcome_label(dg[0], r1))}</td>" +
                    "".join(f"<td class='r'>{render(cells[(r1, r2)][0])}</td>" for r2 in E.RESULTS) + "</tr>"
                    for r1 in E.RESULTS)
                grid = (f"<p class='colnote'>Columns: {esc(a2)} at {esc(h2)}</p>"
                        f"<div class='tw'><table class='grid'>{head}{body}</table></div>")
            else:
                head = ("<tr>" + "".join(f"<th>{esc(a)} at {esc(h)}</th>" for h, a in dg) +
                        f"<th class='r'>{'Misses the playoffs' if berth else 'Order'}</th></tr>")
                body = "".join(
                    "<tr>" + "".join(f"<td>{esc(outcome_label(g, r))}</td>" for g, r in zip(dg, k)) +
                    f"<td class='r'>{render(cells[k][0])}</td></tr>" for k in keys)
                grid = f"<div class='tw'><table class='grid'>{head}{body}</table></div>"
            total = len(keys)
            counts, depcount = Counter(), 0
            for k in keys:
                content, dep = cells[k]
                if berth:
                    if dep:
                        depcount += 1
                    else:
                        for t in ts:
                            if t not in content.split(" & "):
                                counts[t] += 1
                else:
                    first = content[0][1]
                    if len(first) == 1:
                        counts[first[0]] += 1
                    else:
                        depcount += 1
            if berth:
                tally = ", ".join(f"{esc(t)} makes it in {counts[t]} of {total}" for t in ts)
            else:
                tally = ", ".join(f"{esc(t)} in {counts[t]}" for t in ts if counts[t])
                tally = f"No. {lo} goes to {tally}" if tally else ""
            if depcount:
                tally += f"{', ' if tally else ''}and it depends on the exact scores in {depcount}"
            foot = (f"<p class='small'>Counting each combination of these results equally, {tally}.</p>"
                    if tally and total > 1 else "")
            star = f"<p class='small'>* {esc(E.DEP_NOTE)}</p>" if any_dep else ""
        label = "Who misses the playoffs" if berth else "Final order"
        return f"""
<h2>{esc(title)}</h2>
<div class="panel">
  <p class="lead">{esc(lead)}</p>
  <p class="small">{sub}</p>
  <p class="small"><b>{E.FINAL_LABEL}.</b> {pts}.</p>
  {f'<p class="small"><b>{label}</b>, by result of each {g1}.</p>' if grid and 'teams' not in grid else ''}
  {grid}{star}{foot}
</div>"""

    sections = "".join(block_section(lo, hi) for lo, hi in blocks)
    if known and not blocks and n > 0:
        sections = "<h2>Seeding</h2><div class='panel'><p class='lead'>Every playoff seed is already decided.</p></div>"
    if n > SCENARIOS_UP_TO[cfg["kind"]]:
        sections = (f"<div class='panel'><p class='lead'>Clinching scenarios appear once "
                    f"{SCENARIOS_UP_TO[cfg['kind']]} or fewer conference {gN} remain ({n} left now).</p></div>")
    elif n > E.EXACT_UP_TO and known:
        sections += (f"<p class='small' style='margin-top:12px'>With {n} {gN} left, each scenario is checked with a "
                     f"sample of possible scores, so a rare score-based tiebreak could still differ.</p>")

    if n == 0:   # season over: final seeds and how any ties were broken
        final = E.places(E.rank(played, teams))
        seeds = sorted((b, w, t) for t, (b, w) in final.items() if b <= Q)
        items = "".join(f"<li><span class='seed'>{b if b == w else f'{b}–{w}'}</span>{esc(t)} "
                        f"<span class='rec'>({E.record_text(t, played)})</span></li>" for b, w, t in seeds)
        expl = E.explain(played, teams) if hasattr(E, "explain") else []
        ties = ("<p class='small'><b>How the ties were broken</b></p><ul class='why'>" +
                "".join(f"<li>{esc(x)}</li>" for x in expl) + "</ul>") if expl else ""
        sections = (f"<h2>Final seeds</h2><div class='panel'><p class='lead'>The regular season is complete. "
                    f"These {word(len(seeds), False)} teams qualify for the {esc(cfg['tournament'])}.</p>"
                    f"<ol class='final'>{items}</ol>{ties}</div>")

    # ---------- intro ----------
    thru = ""
    if played_dates:
        last = max(played_dates)
        thru = f"Standings through the {gN} of {last.strftime('%A')}, {day(last, False)}, {last.year}. "
    rem_dates = sorted(d for d in dates.values() if d)
    if n == 0:
        rem = "The regular season is complete. "
    else:
        span = ""
        if rem_dates:
            span = f", {day(rem_dates[0], False)}" + \
                   (f" to {day(rem_dates[-1], False)}" if rem_dates[-1] != rem_dates[0] else "")
        rem = f"{word(n)} conference {g1 if n == 1 else gN} remain{'s' if n == 1 else ''}{span}. "
    intro = f"{thru}{rem}The top {word(Q, False)} of {len(teams)} teams qualify for the {cfg['tournament']}."

    data = {"teams": teams, "played": played, "remaining": remaining, "q": Q}
    if cfg["kind"] == "soccer":
        data |= {"cap": cciw_tiebreaker.GD_CAP, "scope": cciw_tiebreaker.GD_SCOPE}
    logo = f'<img class="logo" src="{esc(LOGO_URL)}" alt="CCIW logo">' if LOGO_URL else ""

    page = PAGE.format(
        title=esc(cfg["name"]) + " Playoff Scenarios", logo=logo, sport=esc(cfg["name"]), intro=esc(intro),
        clinched=chips(clinched, "in", "No team has clinched yet."),
        alive=chips(alive, "alive", "All playoff spots are decided."),
        eliminated=chips(eliminated, "out", "No team is eliminated yet."),
        sections=sections, footer=esc(E.FOOTER), engine=E.JS, data=json.dumps(data), gword=g1, gwords=gN,
        c1="Clinched", c2="Still alive", c3="Eliminated", heading="Playoff Scenarios",
    )
    out = os.path.join(folder, "index.html")
    with open(out, "w") as f:
        f.write(page)
    print(f"{cfg['name']}: {out} written ({n} {gN} left)")


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700&family=Barlow+Condensed:wght@600;700;800&display=swap" rel="stylesheet">
<style>
:root {{
  --bg:#f3f5f8; --card:#ffffff; --ink:#172033; --muted:#5b6475; --line:#dce2eb; --head:#e8eef6;
  --accent:#1d4f91; --in:#1d4f91; --alive:#8a5a00; --out:#a3302c; --sub:#38445a;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.5 Barlow, -apple-system, "Segoe UI", Arial, sans-serif; }}
.page {{ max-width:1120px; margin:0 auto; padding:28px 16px 40px; }}
.top {{ display:flex; align-items:center; gap:18px; margin-bottom:14px; }}
.top h1 {{ margin:0; }}
.logo {{ height:96px; width:auto; flex:none; }}
@media (max-width:600px) {{ .logo {{ height:64px; }} }}
.eyebrow {{ font:700 13px/1 "Barlow Condensed", sans-serif; letter-spacing:.12em; text-transform:uppercase; color:var(--accent); margin:0 0 10px; }}
h1 {{ font:800 clamp(40px,7vw,58px)/1 "Barlow Condensed", sans-serif; margin:0 0 14px; letter-spacing:-.01em; }}
.intro {{ color:var(--muted); max-width:580px; margin:0 0 26px; }}
.status {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:14px; margin-bottom:36px; }}
.card, .panel {{ background:var(--card); border:1px solid var(--line); border-radius:6px; }}
.card {{ padding:16px 16px 18px; }}
.card h3 {{ font:700 18px/1 "Barlow Condensed", sans-serif; text-transform:uppercase; letter-spacing:.02em; margin:4px 0 14px; color:var(--sub); }}
.chip {{ display:inline-block; font-weight:600; font-size:13px; padding:3px 10px; margin:0 6px 6px 0; border-radius:999px; border:1px solid; }}
.chip.in {{ color:var(--in); border-color:var(--in); }}
.chip.alive {{ color:var(--alive); border-color:#b98a2c; }}
.chip.out {{ color:var(--out); border-color:var(--out); }}
.none {{ color:var(--muted); font-size:14px; margin:0; }}
h2 {{ font:700 26px/1.1 "Barlow Condensed", sans-serif; margin:34px 0 14px; }}
.panel {{ padding:18px 16px; }}
.lead {{ font-weight:600; margin:0 0 8px; }}
.small {{ font-size:14px; color:var(--muted); margin:0 0 10px; }}
.small b {{ color:var(--sub); }}
.colnote {{ font-size:12px; color:var(--muted); margin:0 0 6px; }}
.tw {{ overflow-x:auto; border:1px solid var(--line); border-radius:6px; margin:4px 0 14px; }}
table {{ width:100%; border-collapse:collapse; }}
th {{ background:var(--head); font:700 13px/1.2 "Barlow Condensed", sans-serif; letter-spacing:.06em; text-transform:uppercase;
      color:var(--sub); text-align:left; padding:10px 10px; white-space:nowrap; }}
td {{ border-top:1px solid var(--line); padding:9px 10px; vertical-align:top; }}
.r {{ text-align:right; }}
td.rowh {{ font-weight:600; white-space:nowrap; }}
.grid td.r div {{ white-space:nowrap; }}
.pl {{ display:inline-block; min-width:18px; color:var(--muted); font-weight:600; margin-right:4px; }}
.games {{ display:grid; gap:10px; margin-bottom:16px; }}
.game {{ display:flex; flex-wrap:wrap; align-items:center; gap:8px 12px; padding:10px 12px; border:1px solid var(--line); border-radius:6px; }}
.game .name {{ font-weight:600; min-width:220px; flex:1; }}
.game .when {{ font-weight:400; color:var(--muted); font-size:13px; }}
.seg {{ display:inline-flex; border:1px solid var(--line); border-radius:6px; overflow:hidden; }}
.seg button {{ font:600 13px Barlow, sans-serif; border:0; background:#fff; color:var(--ink); padding:7px 11px; cursor:pointer; border-left:1px solid var(--line); }}
.seg button:first-child {{ border-left:0; }}
.seg button.on {{ background:var(--accent); color:#fff; }}
.score {{ display:inline-flex; align-items:center; gap:4px; font-size:13px; color:var(--muted); }}
.score input, .score select {{ padding:5px; font:inherit; color:var(--ink); border:1px solid var(--line); border-radius:4px; background:#fff; }}
.score input {{ width:44px; text-align:center; }}
.stand td.num, .stand th.num {{ text-align:center; }}
.stand tr.cut td {{ border-bottom:2px solid var(--accent); }}
.tag {{ font-size:12px; font-weight:600; color:var(--accent); white-space:nowrap; }}
.tag.outt {{ color:var(--out); }}
.tag.tie {{ color:var(--alive); }}
.reset {{ font:600 13px Barlow, sans-serif; background:none; border:1px solid var(--line); border-radius:6px; padding:6px 12px; cursor:pointer; color:var(--ink); }}
table.teams td {{ vertical-align:top; }}
.gl {{ font-weight:400; font-size:12px; color:var(--muted); white-space:normal; max-width:220px; }}
.ol {{ display:block; font:700 12px/1.2 "Barlow Condensed", sans-serif; letter-spacing:.06em; text-transform:uppercase; color:var(--muted); margin-bottom:2px; }}
.st {{ font-size:14px; }}
.st.in {{ color:var(--in); font-weight:700; }}
.st.out {{ color:var(--out); font-weight:700; }}
.st.help {{ color:var(--ink); }}
ol.final {{ list-style:none; padding:0; margin:0 0 14px; display:grid; grid-template-columns:repeat(auto-fill,minmax(230px,1fr)); gap:6px 16px; }}
ol.final li {{ font-weight:600; }}
.seed {{ display:inline-block; min-width:30px; color:var(--accent); font-weight:700; }}
.rec {{ font-weight:400; color:var(--muted); font-size:14px; }}
ul.why {{ margin:0; padding-left:18px; color:var(--ink); font-size:14px; }}
ul.why li {{ margin-bottom:6px; }}
.foot {{ font-size:13px; color:var(--muted); margin-top:26px; }}
@media (max-width:600px) {{ .game .name {{ min-width:100%; }} }}
</style></head><body><div class="page">
<div class="top">{logo}<div>
<p class="eyebrow">{sport}</p>
<h1>{heading}</h1></div></div>
<p class="intro">{intro}</p>

<div class="status">
  <div class="card"><h3>{c1}</h3>{clinched}</div>
  <div class="card"><h3>{c2}</h3>{alive}</div>
  <div class="card"><h3>{c3}</h3>{eliminated}</div>
</div>

{sections}

<h2>Scenario builder</h2>
<div class="panel">
  <p class="small">Pick a result for any remaining {gword} and adjust the score if you like. The standings update with every tiebreaker applied.</p>
  <div class="games" id="games"></div>
  <div class="tw"><table class="stand" id="stand"></table></div>
  <button class="reset" id="reset">Reset</button>
</div>

<p class="foot">{footer} Updated automatically from cciw.org results.</p>
</div>

<script>
const CFG = {data};
{engine}
let picks = {{}};
function drawGames() {{
  const box = document.getElementById("games");
  box.innerHTML = "";
  CFG.remaining.forEach(([h, a], i) => {{
    const p = picks[i];
    const div = document.createElement("div");
    div.className = "game";
    const opts = [["", () => "Not played"]].concat(RES);
    let score = "";
    if (p && SCORE_CHOICES) {{
      const win = p.r === "H" ? h : a;
      const cur = p.r === "H" ? [p.hg, p.ag] : [p.ag, p.hg];
      score = `<span class="score">${{win}} wins <select data-i="${{i}}">` +
        SCORE_CHOICES.map(c => `<option value="${{c}}" ${{c[0] === cur[0] && c[1] === cur[1] ? "selected" : ""}}>${{c[0]}}-${{c[1]}}</option>`).join("") +
        `</select></span>`;
    }} else if (p) {{
      score = `<span class="score">${{a}} <input data-i="${{i}}" data-side="a" type="number" min="0" value="${{p.ag}}"> –
               <input data-i="${{i}}" data-side="h" type="number" min="0" value="${{p.hg}}"> ${{h}}</span>`;
    }}
    div.innerHTML = `<span class="name">${{a}} at ${{h}}</span>
      <span class="seg">${{opts.map(([k, l]) => `<button data-i="${{i}}" data-k="${{k}}" class="${{(p ? p.r : "") === k ? "on" : ""}}">${{l(k === "H" ? h : a)}}</button>`).join("")}}</span>${{score}}`;
    box.appendChild(div);
  }});
  box.querySelectorAll("button").forEach(b => b.onclick = () => {{
    const i = +b.dataset.i, k = b.dataset.k;
    if (!k) delete picks[i]; else picks[i] = {{r:k, hg:DEF[k][0], ag:DEF[k][1]}};
    drawGames(); drawTable();
  }});
  box.querySelectorAll("select").forEach(sel => sel.onchange = () => {{
    const p = picks[+sel.dataset.i], [w, l] = sel.value.split(",").map(Number);
    if (p.r === "H") {{ p.hg = w; p.ag = l; }} else {{ p.ag = w; p.hg = l; }}
    drawTable();
  }});
  box.querySelectorAll("input").forEach(inp => inp.oninput = () => {{
    const p = picks[+inp.dataset.i];
    const v = Math.max(0, parseInt(inp.value || "0", 10));
    if (inp.dataset.side === "h") p.hg = v; else p.ag = v;
    p.r = p.hg > p.ag ? "H" : p.hg < p.ag ? "A" : "D";
    drawTable();
    inp.closest(".game").querySelectorAll("button").forEach(b => b.classList.toggle("on", b.dataset.k === p.r));
  }});
}}
function drawTable() {{
  const sim = CFG.remaining.map(([h, a], i) => picks[i] ? [h, a, picks[i].hg, picks[i].ag] : null).filter(Boolean);
  const games = CFG.played.concat(sim);
  let place = 1, rows = "";
  for (const slot of rank(games, CFG.teams)) {{
    const group = Array.isArray(slot) ? slot : [slot];
    const label = group.length > 1 ? `${{place}}–${{place + group.length - 1}}` : `${{place}}`;
    group.forEach(t => {{
      const last = place + group.length - 1;
      const st = (typeof STATUS === "function") ? STATUS(t, games, group) : place > CFG.q ? "<span class='tag outt'>Out</span>"
               : group.length > 1 ? `<span class='tag tie'>${{UNRESOLVED}}</span>`
               : "<span class='tag'>In</span>";
      const cut = last === CFG.q && t === group[group.length - 1];
      rows += `<tr class="${{cut ? "cut" : ""}}"><td class="num">${{label}}</td><td><b>${{t}}</b></td>` +
        cells(games, t).map(c => `<td class="num">${{c}}</td>`).join("") + `<td>${{st}}</td></tr>`;
    }});
    place += group.length;
  }}
  document.getElementById("stand").innerHTML =
    `<tr><th class="num">${{typeof POS_LABEL === "string" ? POS_LABEL : "Seed"}}</th><th>Team</th>` + COLS.map(c => `<th class="num">${{c}}</th>`).join("") + `<th></th></tr>` + rows;
}}
document.getElementById("reset").onclick = () => {{ picks = {{}}; drawGames(); drawTable(); }};
if (!CFG.remaining.length) document.getElementById("games").innerHTML = "<p class='small'>All {gwords} have been played.</p>";
else drawGames();
drawTable();
</script>
</body></html>
"""

if __name__ == "__main__":
    from title_page import build_title
    for key in (sys.argv[1:] or SPORTS):
        if SPORTS[key]["kind"] == "football":
            build_title(key)
        else:
            build(key)
