"""
CCIW basketball tiebreakers (men's and women's), double round-robin.

Standings: conference record (winning percentage).
Tiebreakers, in order:
  1. Head-to-head record among the tied teams (composite record for 3+ teams)
  2. Record against the team(s) above the tie, starting with the highest-ranked team;
     if all tied teams have the same record against that team, go to the next team
  3. Record against the team(s) below the tie, going to the next place down, and so on
  4. Road record against all conference schools
  5. National Performance Index (NPI) at the end of the regular season
  6. Random action
With three or more teams tied, once a team rises above the others it is placed, and the
remaining tied teams start again at step 1.

NPI isn't on cciw.org. At the end of the regular season, type each team's NPI into npi.csv in the
sport's folder (team,npi) and the page will use it; until then a tie that gets past step 4 is
shown as "NPI, then random action".
"""
from collections import defaultdict
from fractions import Fraction

from cciw_tiebreaker import load_games, places

NPI = {}   # filled from the sport's npi.csv by make_page.py, if that file exists

KIND = "basketball"
GAME_WORD = ("game", "games")
RESULTS = ["H", "A"]
NOMINAL = {"H": (70, 60), "A": (60, 70)}
SCORES = {"H": [(70, 60)], "A": [(60, 70)]}   # the margin never matters to these tiebreakers
EXACT_UP_TO = 99
SAMPLES = 0
UNRESOLVED = "NPI, then random action"
FINAL_LABEL = "Final records"
DEP_NOTE = "Still tied after every criterion cciw.org can show, so NPI and then random action decide it."
FOOTER = ("Standings: conference record. Tiebreakers: 1) head-to-head record among the tied teams; 2) record against "
          "the team(s) above the tie, starting with the highest-ranked team; 3) record against the team(s) below the "
          "tie, then the next place down, and so on; 4) road record against all conference schools; 5) NPI at the "
          "end of the regular season; 6) random action. With three or more teams tied, once a team rises above the "
          "others, the remaining teams start again at step 1. NPI isn't calculated here because it isn't on cciw.org.")


def stats(games, only=None):
    s = defaultdict(lambda: {"w": 0, "l": 0, "rw": 0, "rl": 0})
    for h, a, hs, as_ in games:
        if only is not None and not (h in only and a in only):
            continue
        if hs > as_:
            s[h]["w"] += 1; s[a]["l"] += 1; s[a]["rl"] += 1
        else:
            s[a]["w"] += 1; s[h]["l"] += 1; s[a]["rw"] += 1
    return s


def pct(w, l):
    return Fraction(w, w + l) if w + l else None


def standings_groups(games, teams):
    s = stats(games)
    value = {t: pct(s[t]["w"], s[t]["l"]) or Fraction(0) for t in teams}
    return [sorted(t for t in teams if value[t] == v) for v in sorted(set(value.values()), reverse=True)]


def _vs(games, group, opp):
    rec = {t: [0, 0] for t in group}
    for h, a, hs, as_ in games:
        for t, o, won in ((h, a, hs > as_), (a, h, as_ > hs)):
            if t in rec and o in opp:
                rec[t][0 if won else 1] += 1
    return rec


def break_tie(group, games, above, below, trace=None):
    """above = slots placed above (best first); below = groups of teams below the tie (best first)."""
    if len(group) == 1:
        return [group[0]]
    tied = set(group)
    h2h = _vs(games, group, tied)
    tests = [("head-to-head", {t: pct(*h2h[t]) for t in group}, h2h)]
    for slot in above:
        opp = set(slot) if isinstance(slot, (tuple, list)) else {slot}
        rec = _vs(games, group, opp)
        tests.append((f"record against {' / '.join(sorted(opp))} (above the tie)", {t: pct(*rec[t]) for t in group}, rec))
    for slot in below:
        opp = set(slot)
        rec = _vs(games, group, opp)
        tests.append((f"record against {' / '.join(sorted(opp))} (below the tie)", {t: pct(*rec[t]) for t in group}, rec))
    full = stats(games)
    road = {t: [full[t]["rw"], full[t]["rl"]] for t in group}
    tests.append(("road record", {t: pct(*road[t]) for t in group}, road))
    if all(t in NPI for t in group):
        tests.append(("NPI", {t: NPI[t] for t in group}, {t: NPI[t] for t in group}))
    for label, values, recs in tests:
        lead = None
        if not any(v is None for v in values.values()):
            top = max(values.values())
            leaders = [t for t in group if values[t] == top]
            lead = leaders[0] if len(leaders) == 1 else None
        if lead is None:
            if trace is not None and label == "head-to-head":
                trace.append(("same", group, label, recs))
            continue
        if trace is not None:
            trace.append(("split", group, label, recs, lead))
        rest = [t for t in group if t != lead]
        return [lead] + break_tie(rest, games, list(above) + [lead], below, trace)   # rest restart at step 1
    if trace is not None:
        trace.append(("unresolved", group, UNRESOLVED, {}))
    return [tuple(sorted(group))]


def rank(games, teams, trace=None):
    groups = standings_groups(games, teams)
    slots = []
    for i, g in enumerate(groups):
        slots += break_tie(g, games, list(slots), groups[i + 1:], trace)
    return slots


def record_text(team, games):
    s = stats(games)[team]
    return f"{s['w']}-{s['l']}"


def final_line(team, played, left):
    s = stats(played)[team]
    w, l = s["w"], s["l"]
    if left == 0:
        return f"{w}-{l} (season complete)"
    if left == 1:
        return f"{w}-{l + 1} with a loss, {w + 1}-{l} with a win"
    return f"between {w}-{l + left} and {w + left}-{l}"


def explain(games, teams):
    """Plain-English account of how each tie in the standings was broken."""
    trace = []
    rank(games, teams, trace)
    out, seen, firsts = [], set(), {}

    def recs(r, group):
        return ", ".join(f"{t} {r[t]}" if not isinstance(r[t], list) else f"{t} {r[t][0]}-{r[t][1]}"
                         for t in sorted(group))

    for entry in trace:
        step, group, label, r = entry[:4]
        key = tuple(sorted(group))
        if key not in seen:
            seen.add(key)
            first = not any(set(group) < set(k) for k in seen if k != key)
            firsts[key] = first
            names = _names(sorted(group))
            intro = (f"{names} were tied at {record_text(group[0], games)}. " if first else
                     f"That left {names}, who start again at head-to-head. ")
        else:
            intro = ""
        if step == "same":
            out.append(intro + f"Head-to-head didn't separate them ({recs(r, group)}).")
        elif step == "split":
            lead = entry[4]
            spot = "the top spot" if firsts.get(key, True) else "the next spot"
            out.append(intro + f"{label[0].upper() + label[1:]}: {recs(r, group)}, so {lead} takes {spot}.")
        else:
            out.append(intro + f"They were also even against every other team and on the road, so {UNRESOLVED} "
                               f"decide it. (Add NPI values to npi.csv to settle this on the page.)")
    return out


def _names(group):
    g = list(group)
    return ", ".join(g[:-1]) + (" and " if len(g) > 1 else "") + g[-1]


JS = r"""
const RES = [["A", a => a + " win"], ["H", h => h + " win"]];
const DEF = {H:[70,60], A:[60,70]};
const SCORE_CHOICES = [];             // the score doesn't matter to any tiebreaker
const UNRESOLVED = "NPI / random action";
function stats(games) {
  const s = {};
  const g = t => s[t] || (s[t] = {w:0, l:0, rw:0, rl:0});
  for (const [h, a, hs, as] of games) {
    const H = g(h), A = g(a);
    if (hs > as) { H.w++; A.l++; A.rl++; } else { A.w++; H.l++; A.rw++; }
  }
  return s;
}
const val = (s, t, k) => (s[t] ? s[t][k] : 0);
const pct = (w, l) => (w + l ? w / (w + l) : null);
const same = (x, y) => Math.abs(x - y) < 1e-9;
function groupsBy(group, v) {
  const distinct = [];
  for (const t of group) if (!distinct.some(d => same(d, v[t]))) distinct.push(v[t]);
  distinct.sort((x, y) => y - x);
  return distinct.map(d => group.filter(t => same(v[t], d)));
}
function vs(games, group, opp) {
  const rec = Object.fromEntries(group.map(t => [t, [0, 0]]));
  for (const [h, a, hs, as] of games) {
    if (rec[h] && opp.has(a)) rec[h][hs > as ? 0 : 1]++;
    if (rec[a] && opp.has(h)) rec[a][as > hs ? 0 : 1]++;
  }
  return Object.fromEntries(group.map(t => [t, pct(rec[t][0], rec[t][1])]));
}
function breakTie(group, games, above, below) {
  if (group.length === 1) return [group[0]];
  const tests = [vs(games, group, new Set(group))];
  for (const slot of above) tests.push(vs(games, group, new Set(Array.isArray(slot) ? slot : [slot])));
  for (const slot of below) tests.push(vs(games, group, new Set(slot)));
  const s = stats(games);
  tests.push(Object.fromEntries(group.map(t => [t, pct(val(s,t,"rw"), val(s,t,"rl"))])));
  if (CFG.npi && group.every(t => t in CFG.npi)) tests.push(Object.fromEntries(group.map(t => [t, CFG.npi[t]])));
  for (const v of tests) {
    if (group.some(t => v[t] === null)) continue;
    const top = Math.max(...group.map(t => v[t]));
    const leaders = group.filter(t => same(v[t], top));
    if (leaders.length === 1) return [leaders[0]].concat(breakTie(group.filter(t => t !== leaders[0]), games, above.concat([leaders[0]]), below));
  }
  return [group.slice().sort()];
}
function rank(games, teams) {
  const s = stats(games);
  const v = Object.fromEntries(teams.map(t => [t, pct(val(s,t,"w"), val(s,t,"l")) || 0]));
  const groups = groupsBy(teams.slice().sort(), v);
  let slots = [];
  groups.forEach((g, i) => { slots = slots.concat(breakTie(g, games, slots.slice(), groups.slice(i + 1))); });
  return slots;
}
const COLS = ["W-L", "Pct.", "Road"];
function cells(games, t) {
  const s = stats(games);
  const w = val(s,t,"w"), l = val(s,t,"l"), p = pct(w, l);
  return [`${w}-${l}`, `<b>${p === null ? "—" : p.toFixed(3).replace(/^0/, "")}</b>`, `${val(s,t,"rw")}-${val(s,t,"rl")}`];
}
"""
