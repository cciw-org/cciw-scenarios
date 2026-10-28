"""
Builds the page for a sport decided by the regular-season title (football):
who can win or share the championship, and who gets the automatic bid (AQ).
Called by make_page.py.
"""
import csv
import html
import json
import os
import random
from collections import defaultdict, Counter
from datetime import datetime
from itertools import product, combinations

import fb_tiebreaker as E
from sports import SPORTS, LOGO_URL

esc = html.escape
NUM = ["No", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
       "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen"]
MAX_LEFT = 14     # more games left than this: skip the scenarios (too many)

# status of one team in one outcome, best first
ORDER = ["outright", "aq", "aqdep", "share", "none"]
LABEL = {"outright": "Outright champion + AQ", "aq": "Co-champion + AQ",
         "aqdep": "Co-champion; AQ on defensive yards/draw", "share": "Co-champion, no AQ",
         "none": "No title"}
SHORT = {"outright": "Outright title + AQ", "aq": "Co-champion + AQ", "aqdep": "Co-champion, AQ undecided*",
         "share": "Co-champion, no AQ", "none": "No title"}


def word(n, cap=True):
    w = NUM[n] if n < len(NUM) else str(n)
    return w if cap else w.lower()


def status(outcome, t):
    champs, aq = outcome
    if t not in champs:
        return "none"
    if len(champs) == 1:
        return "outright"
    if isinstance(aq, tuple):
        return "aqdep" if t in aq else "share"
    return "aq" if aq == t else "share"


def build_title(key):
    from make_page import PAGE   # same page design as the other sports
    cfg = SPORTS[key]
    folder = cfg["folder"]
    games_file = os.path.join(folder, "games.csv")
    played, remaining = E.load_games(games_file)
    teams = sorted({t for g in played for t in g[:2]} | {t for g in remaining for t in g})
    n = len(remaining)

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
        when = day(dates.get(g))
        return f"{g[1]} at {g[0]}" + (f" ({when})" if when else "")

    def phrase(g, r):
        h, a = g
        return f"{h} beats {a}" if r == "H" else f"{a} beats {h}"

    # ---------- every scenario ----------
    rng = random.Random(0)
    by_pattern = defaultdict(set)
    if n <= MAX_LEFT:
        for pattern in product(E.RESULTS, repeat=n):
            variants = [tuple(E.NOMINAL[r] for r in pattern),
                        tuple(E.SCORES[r][0] for r in pattern), tuple(E.SCORES[r][-1] for r in pattern)]
            variants += [tuple(rng.choice(E.SCORES[r]) for r in pattern) for _ in range(E.SAMPLES)]
            for combo in variants:
                sim = [(h, a, x, y) for (h, a), (x, y) in zip(remaining, combo)]
                by_pattern[pattern].add(E.title(played + sim, teams))
    known = bool(by_pattern)

    best = {t: min((ORDER.index(status(o, t)) for outs in by_pattern.values() for o in outs), default=4) for t in teams}
    worst = {t: max((ORDER.index(status(o, t)) for outs in by_pattern.values() for o in outs), default=4) for t in teams}
    contenders = [t for t in teams if best[t] < 4]
    current_order = [t for slot in E.rank(played, teams) for t in (slot if isinstance(slot, tuple) else (slot,))]
    contenders.sort(key=current_order.index)
    out_teams = [t for t in current_order if best[t] == 4]
    clinched = [t for t in contenders if worst[t] < 4]
    alive = [t for t in contenders if t not in clinched]

    def chips(ts, kind, empty, note=None):
        if not ts:
            return f"<p class='none'>{empty}</p>"
        return "".join(f"<span class='chip {kind}'>{esc(t)}{esc(note(t)) if note else ''}</span>" for t in ts)

    def clinch_note(t):
        return " (outright title + AQ)" if worst[t] == 0 else " (at least a share)"

    # ---------- the title race ----------
    def cell_outcome(outs):
        """Text for a grid cell: who wins the title and the AQ."""
        parts = []
        for champs, aq in sorted(outs, key=lambda o: (len(o[0]), o[0])):
            if len(champs) == 1:
                parts.append(f"{champs[0]} (outright)")
            else:
                aqt = " or ".join(aq) + " on defensive yards/draw*" if isinstance(aq, tuple) else aq
                parts.append(f"Co-champions: {', '.join(champs)} · AQ: {aqt}")
        return " / ".join(dict.fromkeys(parts))

    def deciding(statfn, idx):
        """Smallest set (up to 2) of games in idx whose results decide statfn(pattern)."""
        pats = list(by_pattern)
        for size in range(0, 3):
            for S in combinations(idx, size):
                seen, ok = {}, True
                for p in pats:
                    proj = tuple(p[i] for i in S)
                    if seen.setdefault(proj, statfn(p)) != statfn(p):
                        ok = False
                        break
                if ok:
                    return S, seen
        return None, None

    sections = ""
    if not known:
        sections = (f"<div class='panel'><p class='lead'>Title scenarios appear once {MAX_LEFT} or fewer conference "
                    f"games remain ({n} left now).</p></div>")
    elif n == 0:
        sections = ""
    else:
        names = ", ".join(contenders[:-1]) + (" and " if len(contenders) > 1 else "") + contenders[-1]
        lead = (f"{names} can still win the title outright." if len(contenders) == 1 else
                f"{names} can still win at least a share of the title.")
        recs = ". ".join(f"{esc(t)}: {E.final_line(t, played, sum(t in g for g in remaining))}" for t in contenders)
        S, seen = deciding(lambda p: frozenset(by_pattern[p]), list(range(n)))
        if S is not None and len(S) <= 2 and S:
            dg = [remaining[i] for i in S]
            sub = (f"{word(len(dg))} game{'s' if len(dg) > 1 else ''} decide{'s' if len(dg) == 1 else ''} it: "
                   + " and ".join(esc(game_name(g)) for g in dg) + ".")
            if len(dg) == 2:
                head = f"<tr><th>{esc(dg[0][1])} at {esc(dg[0][0])}</th>" + "".join(
                    f"<th class='r'>{esc(phrase(dg[1], r).split(' beats ')[0])} wins</th>" for r in E.RESULTS) + "</tr>"
                body = "".join(
                    f"<tr><td class='rowh'>{esc(phrase(dg[0], r1).split(' beats ')[0])} wins</td>" +
                    "".join(f"<td class='r'>{esc(cell_outcome(seen[(r1, r2)]))}</td>" for r2 in E.RESULTS) + "</tr>"
                    for r1 in E.RESULTS)
                grid = (f"<p class='colnote'>Columns: {esc(dg[1][1])} at {esc(dg[1][0])}</p>"
                        f"<div class='tw'><table class='grid'>{head}{body}</table></div>")
            else:
                body = "".join(f"<tr><td class='rowh'>{esc(phrase(dg[0], r))}</td><td class='r'>"
                               f"{esc(cell_outcome(seen[(r,)]))}</td></tr>" for r in E.RESULTS)
                grid = f"<div class='tw'><table class='grid'><tr><th>Result</th><th class='r'>Title</th></tr>{body}</table></div>"
        else:
            sub = ("Too many games affect the title race for one table, so here is what each team needs. "
                   "Percentages show how often each thing happens across all the ways the other games can go, "
                   "counting each one equally.")
            grid = team_table(contenders, remaining, by_pattern, game_name, phrase, n)
        star = ("<p class='small'>* Still tied after head-to-head and point differential against the tied teams, "
                "so defensive yards (then a random draw) decide the AQ.</p>") if "*" in grid else ""
        sections = f"""
<h2>The title race</h2>
<div class="panel">
  <p class="lead">{esc(lead)}</p>
  <p class="small">{sub}</p>
  <p class="small"><b>{E.FINAL_LABEL}.</b> {recs}.</p>
  {grid}{star}
</div>"""
        if n > 0:
            sections += (f"<p class='small' style='margin-top:12px'>Each scenario is checked with a sample of possible "
                         f"scores, so a rare point-differential tiebreak could still differ.</p>")

    # ---------- intro ----------
    thru = ""
    if played_dates:
        last = max(played_dates)
        thru = f"Standings through the games of {last.strftime('%A')}, {day(last, False)}, {last.year}. "
    rem_dates = sorted(d for d in dates.values() if d)
    if n == 0:
        rem = "The regular season is complete. "
    else:
        span = f", {day(rem_dates[0], False)}" + (f" to {day(rem_dates[-1], False)}" if rem_dates and rem_dates[-1] != rem_dates[0] else "") if rem_dates else ""
        rem = f"{word(n)} conference game{'s' if n != 1 else ''} remain{'s' if n == 1 else ''}{span}. "
    intro = (f"{thru}{rem}The team that finishes first is the CCIW champion and earns the conference's automatic "
             f"bid (AQ) to the NCAA playoffs. Teams tied for first are co-champions, and the tiebreakers decide the AQ.")

    data = {"teams": teams, "played": played, "remaining": remaining, "q": 1}
    logo = f'<img class="logo" src="{esc(LOGO_URL)}" alt="CCIW logo">' if LOGO_URL else ""
    page = PAGE.format(
        title=esc(cfg["name"]) + " Title Race", logo=logo, sport=esc(cfg["name"]), intro=esc(intro),
        clinched=chips(clinched, "in", "No team has clinched a share yet.", clinch_note),
        alive=chips(alive, "alive", "The title is decided."),
        eliminated=chips(out_teams, "out", "No team is out of the title race yet."),
        sections=sections, footer=esc(E.FOOTER), engine=E.JS, data=json.dumps(data), gword="game", gwords="games",
        c1="Clinched", c2="Still in the title race", c3="Out of the title race", heading="Title Race",
    )
    os.makedirs(folder, exist_ok=True)
    out = os.path.join(folder, "index.html")
    with open(out, "w") as f:
        f.write(page)
    print(f"{cfg['name']}: {out} written ({n} games left)")


def team_table(contenders, remaining, by_pattern, game_name, phrase, n):
    rows, ncols = [], 1
    for t in contenders:
        own = [i for i, g in enumerate(remaining) if t in g]
        others = [i for i in range(n) if i not in own]
        cats = defaultdict(list)
        for p in by_pattern:
            cats[sum((p[i] == "H") == (remaining[i][0] == t) for i in own)].append(p)
        cells = []
        for c in sorted(cats, reverse=True):
            ps = cats[c]
            st = {p: frozenset(status(o, t) for o in by_pattern[p]) for p in ps}
            lab = f"Goes {c}-{len(own) - c}" if len(own) > 1 else ("Win" if c else "Loss") if own else "Season complete"
            vals = set(st.values())
            if len(vals) == 1:
                v = next(iter(vals))
                text = " or ".join(SHORT[x] for x in ORDER if x in v)
                cls = "in" if "none" not in v else "out" if v == {"none"} else "help"
            else:
                text, cls = condition(ps, st, others, remaining, phrase), "help"
            cells.append((lab, text, cls))
        rows.append((t, own, cells))
        ncols = max(ncols, len(cells))
    html_rows = ""
    for t, own, cells in rows:
        own_txt = "; ".join(esc(game_name(remaining[i])) for i in own) or "Season complete"
        html_rows += (f"<tr><td class='rowh'>{esc(t)}<div class='gl'>{own_txt}</div></td>" +
                      "".join(f"<td><span class='ol'>{esc(l)}</span><span class='st {c}'>{esc(x)}</span></td>"
                              for l, x, c in cells) + "<td></td>" * (ncols - len(cells)) + "</tr>")
    head = "<tr><th>Team</th>" + "".join("<th>Own results</th>" if i == 0 else "<th></th>" for i in range(ncols)) + "</tr>"
    return (f"<p class='small'><b>What each team needs</b>, by its own results.</p>"
            f"<div class='tw'><table class='teams'>{head}{html_rows}</table></div>")


def condition(ps, st, others, remaining, phrase):
    def label(v):
        return " or ".join(SHORT[x] for x in ORDER if x in v)

    def desc(S, projs):
        if len(S) == 1:
            return " or ".join(phrase(remaining[S[0]], p[0]) for p in projs)
        parts = []
        for r1 in E.RESULTS:
            rs = [p[1] for p in projs if p[0] == r1]
            if not rs:
                continue
            g1, g2 = remaining[S[0]], remaining[S[1]]
            parts.append(phrase(g1, r1) if len(rs) == 2 else f"{phrase(g1, r1)} and {phrase(g2, rs[0])}")
        return "; or ".join(parts)

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
            groups = defaultdict(list)
            for proj, v in seen.items():
                groups[v].append(proj)
            ordered = sorted(groups, key=lambda v: min(ORDER.index(x) for x in v))
            text = "; ".join(f"{label(v)} if {desc(list(S), groups[v])}" for v in ordered[:-1])
            return text + f"; otherwise {label(ordered[-1]).lower() if ordered[-1] == frozenset({'none'}) else label(ordered[-1])}"
    m = len(ps)

    def share(k):
        if k == 0:
            return "never"
        if k == m:
            return "always"
        return f"{min(99, max(1, round(100 * k / m)))}%"

    title_k = sum(1 for p in ps if "none" not in st[p])
    aq_k = sum(1 for p in ps if st[p] <= {"outright", "aq"})
    out_k = sum(1 for p in ps if st[p] == {"outright"})
    parts = [f"Title share {share(title_k)}", f"AQ {share(aq_k)}"]
    if out_k != aq_k:
        parts.append(f"outright {share(out_k)}")
    return " · ".join(parts)
