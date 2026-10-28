"""
CCIW tennis tiebreakers (seeding for the conference tournament).

Standings: conference match record.
Tiebreakers, in order:
  1. Conference record (the standings themselves)
  2. Head-to-head competition
  3. Record vs. teams above the tie in the standings; if still tied, go to the next
     place, and so on (read here as continuing down the standings, one place at a time)
  4. Number of individual matches won in matches between the tied teams
  5. Number of sets won in matches between the tied teams
  6. Number of games won in matches between the tied teams
  7. Coin flip
With three or more teams tied, once one team rises above the others it is placed, and
the remaining tied teams start again at step 1.

The team scores on cciw.org (e.g. W 4-3) are the individual matches won, so step 4 works.
Sets and games won aren't on the schedule pages, so a tie that gets past step 4 is shown
as "sets, games, then coin flip".
games.csv for tennis uses home_goals/away_goals for the TEAM SCORE (individual matches won).
"""
from collections import defaultdict
from fractions import Fraction

from cciw_tiebreaker import load_games, places

KIND = "tennis"
GAME_WORD = ("match", "matches")
RESULTS = ["H", "A"]
NOMINAL = {"H": (5, 2), "A": (2, 5)}
SCORES = {"H": [(4, 3), (5, 2), (6, 1), (7, 0)], "A": [(3, 4), (2, 5), (1, 6), (0, 7)]}
EXACT_UP_TO = 3
SAMPLES = 8
UNRESOLVED = "sets, games, then coin flip"
FINAL_LABEL = "Final records"
DEP_NOTE = ("Tied on record, head-to-head and record against the other teams, so individual matches won "
            "against each other decide it, then sets, games and a coin flip.")
FOOTER = ("Standings: conference match record. Tiebreakers: 1) head-to-head; 2) record against the teams above the "
          "tie in the standings, then the next place down, and so on; 3) individual matches won in matches between "
          "the tied teams; 4) sets won between the tied teams; 5) games won between the tied teams; 6) coin flip. "
          "With three or more teams tied, once one team rises above the others, the remaining teams start again at "
          "step 1. Sets and games won aren't calculated here because they aren't listed on cciw.org's schedule pages.")


def stats(games, only=None):
    s = defaultdict(lambda: {"w": 0, "l": 0, "mw": 0, "ml": 0})
    for h, a, hs, as_ in games:
        if only is not None and not (h in only and a in only):
            continue
        s[h]["mw"] += hs; s[h]["ml"] += as_
        s[a]["mw"] += as_; s[a]["ml"] += hs
        if hs > as_:
            s[h]["w"] += 1; s[a]["l"] += 1
        else:
            s[a]["w"] += 1; s[h]["l"] += 1
    return s


def pct(w, l):
    return Fraction(w, w + l) if w + l else None


def standings_groups(games, teams):
    s = stats(games)
    value = {t: pct(s[t]["w"], s[t]["l"]) or Fraction(0) for t in teams}
    return [sorted(t for t in teams if value[t] == v) for v in sorted(set(value.values()), reverse=True)]


def break_tie(group, games, above, below, trace=None):
    """above = slots placed above (best first); below = groups of teams below the tie (best first)."""
    if len(group) == 1:
        return [group[0]]
    tied = set(group)
    h2h = stats(games, only=tied)
    tests = [("head-to-head", {t: pct(h2h[t]["w"], h2h[t]["l"]) for t in group}, "rec")]
    for slot in list(above) + list(below):                     # 3. vs teams above, then next places down
        opp = set(slot) if isinstance(slot, (tuple, list)) else {slot}
        rec = {t: [0, 0] for t in group}
        for h, a, hs, as_ in games:
            for t, o, won in ((h, a, hs > as_), (a, h, as_ > hs)):
                if t in tied and o in opp:
                    rec[t][0 if won else 1] += 1
        tests.append((f"record vs. {' / '.join(sorted(opp))}", {t: pct(*rec[t]) for t in group}, "rec"))
    tests.append(("individual matches won against each other", {t: h2h[t]["mw"] for t in group}, "num"))
    for label, values, kind in tests:     # until ONE team rises above the others
        lead = None
        if not any(v is None for v in values.values()):
            top = max(values.values())
            leaders = [t for t in group if values[t] == top]
            lead = leaders[0] if len(leaders) == 1 else None
        if lead is None:
            if trace is not None and label in ("head-to-head", "individual matches won against each other"):
                trace.append(("same", group, label, values, kind))
            continue
        if trace is not None:
            trace.append(("split", group, label, values, kind, lead))
        rest = [t for t in group if t != lead]
        return [lead] + break_tie(rest, games, list(above) + [lead], below, trace)   # rest restart at step 1
    if trace is not None:
        trace.append(("unresolved", group, UNRESOLVED, {}, ""))
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
    s = stats(games)
    out, seen_groups, firsts = [], set(), {}

    def fmt(values, kind, group):
        if kind == "rec":
            return ", ".join(f"{t} {_rec(games, t, group)}" for t in sorted(group))
        return ", ".join(f"{t} {values[t]}" for t in sorted(group, key=lambda t: -values[t]))

    for entry in trace:
        step, group, label, values, kind = entry[:5]
        key = tuple(sorted(group))
        names = _names(sorted(group))
        if key not in seen_groups:
            seen_groups.add(key)
            first = not any(set(group) < set(k) for k in seen_groups if k != key)
            firsts[key] = first
            intro = (f"{names} were tied at {record_text(group[0], games)}. " if first else
                     f"That left {names}, who start again at head-to-head. ")
        else:
            intro = ""
        if step == "same":
            if label == "head-to-head":
                out.append(intro + f"Head-to-head didn't separate them ({fmt(values, kind, group)}).")
            else:
                out.append(intro + f"Individual matches won against each other were equal ({fmt(values, kind, group)}).")
        elif step == "split":
            lead = entry[5]
            spot = "the top spot" if firsts.get(key, True) else "the next spot"
            if label.startswith("record vs."):
                txt = f"{lead} had the best {label}, so {lead} takes {spot}."
            elif label == "head-to-head":
                txt = f"Head-to-head: {fmt(values, kind, group)}, so {lead} takes {spot}."
            else:
                txt = (f"Their records against every other team were the same, so {label} decided it "
                       f"({fmt(values, kind, group)}), and {lead} takes {spot}.")
            out.append(intro + txt)
        else:
            out.append(intro + f"Still tied, so {UNRESOLVED} decide it.")
    return out


def _names(group):
    g = list(group)
    return ", ".join(g[:-1]) + (" and " if len(g) > 1 else "") + g[-1]


def _rec(games, t, group):
    s = stats(games, only=set(group))[t]
    return f"{s['w']}-{s['l']}"


JS = r"""
const RES = [["A", a => a + " win"], ["H", h => h + " win"]];
const DEF = {H:[5,2], A:[2,5]};
const SCORE_CHOICES = [[4,3],[5,2],[6,1],[7,0]];   // team score, winner first
const UNRESOLVED = "Sets / games / coin flip";
function stats(games, only) {
  const s = {};
  const g = t => s[t] || (s[t] = {w:0, l:0, mw:0, ml:0});
  for (const [h, a, hs, as] of games) {
    if (only && !(only.has(h) && only.has(a))) continue;
    const H = g(h), A = g(a);
    H.mw += hs; H.ml += as; A.mw += as; A.ml += hs;
    if (hs > as) { H.w++; A.l++; } else { A.w++; H.l++; }
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
function breakTie(group, games, above, below) {
  if (group.length === 1) return [group[0]];
  const tied = new Set(group), h2h = stats(games, tied);
  const tests = [Object.fromEntries(group.map(t => [t, pct(val(h2h,t,"w"), val(h2h,t,"l"))]))];
  for (const slot of above.concat(below)) {
    const opp = new Set(Array.isArray(slot) ? slot : [slot]);
    const rec = Object.fromEntries(group.map(t => [t, [0, 0]]));
    for (const [h, a, hs, as] of games) {
      if (tied.has(h) && opp.has(a)) rec[h][hs > as ? 0 : 1]++;
      if (tied.has(a) && opp.has(h)) rec[a][as > hs ? 0 : 1]++;
    }
    tests.push(Object.fromEntries(group.map(t => [t, pct(rec[t][0], rec[t][1])])));
  }
  tests.push(Object.fromEntries(group.map(t => [t, val(h2h,t,"mw")])));
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
const COLS = ["W-L", "Pct.", "Ind. matches"];
function cells(games, t) {
  const s = stats(games);
  const w = val(s,t,"w"), l = val(s,t,"l"), p = pct(w, l);
  return [`${w}-${l}`, `<b>${p === null ? "—" : p.toFixed(3).replace(/^0/, "")}</b>`, `${val(s,t,"mw")}-${val(s,t,"ml")}`];
}
"""
