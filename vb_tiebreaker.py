"""
CCIW volleyball tiebreakers.

Standings: conference match record (winning percentage).
Tiebreakers, in order:
  1. Match record within the conference (the standings themselves)
  2. Head-to-head record among the tied teams
  3. Winning percentage of sets in all conference matches
  4. Record vs. the team(s) above the tie, starting with the No. 1 seed and
     going down until the tie is broken
  5. Point differential in all conference matches
  6. Coin toss
With three or more teams tied, once one team rises above the others it is placed,
and the remaining tied teams start again at step 1.

Point differential needs the points of every set, which the cciw.org schedule
pages don't list reliably, so a tie that gets past step 4 is shown as
"point differential, then coin toss".

games.csv for volleyball uses home_goals/away_goals for SETS won (e.g. 3 and 1).
"""
from collections import defaultdict
from fractions import Fraction

from cciw_tiebreaker import load_games, places   # same file format and place logic

KIND = "volleyball"
GAME_WORD = ("match", "matches")
RESULTS = ["H", "A"]
NOMINAL = {"H": (3, 1), "A": (1, 3)}
SCORES = {"H": [(3, 0), (3, 1), (3, 2)], "A": [(0, 3), (1, 3), (2, 3)]}
EXACT_UP_TO = 4       # this many matches left or fewer: try every set score
SAMPLES = 8           # otherwise: extra random set scores tried per scenario
UNRESOLVED = "point differential, then coin toss"
FINAL_LABEL = "Final records"
DEP_NOTE = ("Tied on record and head-to-head, so the set scores decide it: set winning "
            "percentage, then record against the teams above, then point differential.")
FOOTER = ("Standings: conference match record. Tiebreakers: 1) head-to-head record among the tied teams; "
          "2) winning percentage of sets in all conference matches; 3) record against the team or teams "
          "above the tie, starting with the No. 1 seed; 4) point differential in all conference matches; "
          "5) coin toss. With three or more teams tied, once one team rises above the others, the remaining "
          "teams start again at step 1. Point differential isn't calculated here because set-by-set "
          "points aren't listed reliably on cciw.org.")


def stats(games, only=None):
    s = defaultdict(lambda: {"w": 0, "l": 0, "sw": 0, "sl": 0})
    for h, a, hs, as_ in games:
        if only is not None and not (h in only and a in only):
            continue
        s[h]["sw"] += hs; s[h]["sl"] += as_
        s[a]["sw"] += as_; s[a]["sl"] += hs
        if hs > as_:
            s[h]["w"] += 1; s[a]["l"] += 1
        else:
            s[a]["w"] += 1; s[h]["l"] += 1
    return s


def pct(w, l):
    return Fraction(w, w + l) if w + l else None


def _leader(group, values):
    """The one team with the best value, or None if no single team rises above the rest."""
    if any(values[t] is None for t in group):
        return None
    top = max(values.values())
    leaders = [t for t in group if values[t] == top]
    return leaders[0] if len(leaders) == 1 else None


def break_tie(group, games, above):
    """`above` = slots already placed above this group, best first. Criteria are applied until
    ONE team rises above the others; it is placed and the rest start again at step 1."""
    if len(group) == 1:
        return [group[0]]
    tied = set(group)
    h2h = stats(games, only=tied)
    full = stats(games)
    tests = [
        {t: pct(h2h[t]["w"], h2h[t]["l"]) for t in group},            # 2. head-to-head
        {t: pct(full[t]["sw"], full[t]["sl"]) for t in group},        # 3. set percentage
    ]
    for slot in above:                                                 # 4. vs teams above, No. 1 first
        opp = set(slot) if isinstance(slot, tuple) else {slot}
        rec = {t: [0, 0] for t in group}
        for h, a, hs, as_ in games:
            for t, o, won in ((h, a, hs > as_), (a, h, as_ > hs)):
                if t in tied and o in opp:
                    rec[t][0 if won else 1] += 1
        tests.append({t: pct(*rec[t]) for t in group})
    for values in tests:
        lead = _leader(group, values)
        if lead:
            return [lead] + break_tie([t for t in group if t != lead], games, above + [lead])
    return [tuple(sorted(group))]                                      # 5-6. point differential / coin toss


def rank(games, teams):
    s = stats(games)
    value = {t: pct(s[t]["w"], s[t]["l"]) or Fraction(0) for t in teams}
    slots = []
    for v in sorted(set(value.values()), reverse=True):
        slots += break_tie(sorted(t for t in teams if value[t] == v), games, list(slots))
    return slots


# ---- text helpers for the page ----
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


JS = r"""
const RES = [["A", a => a + " win"], ["H", h => h + " win"]];
const DEF = {H:[3,1], A:[1,3]};
const SCORE_CHOICES = [[3,0],[3,1],[3,2]];   // sets, winner first
const UNRESOLVED = "Point diff. / coin toss";
function stats(games, only) {
  const s = {};
  const g = t => s[t] || (s[t] = {w:0, l:0, sw:0, sl:0});
  for (const [h, a, hs, as] of games) {
    if (only && !(only.has(h) && only.has(a))) continue;
    const H = g(h), A = g(a);
    H.sw += hs; H.sl += as; A.sw += as; A.sl += hs;
    if (hs > as) { H.w++; A.l++; } else { A.w++; H.l++; }
  }
  return s;
}
const val = (s, t, k) => (s[t] ? s[t][k] : 0);
const pct = (w, l) => (w + l ? w / (w + l) : null);
const same = (x, y) => Math.abs(x - y) < 1e-9;
function leader(group, v) {
  if (group.some(t => v[t] === null)) return null;
  const top = Math.max(...group.map(t => v[t]));
  const leaders = group.filter(t => same(v[t], top));
  return leaders.length === 1 ? leaders[0] : null;
}
function breakTie(group, games, above) {
  if (group.length === 1) return [group[0]];
  const tied = new Set(group), h2h = stats(games, tied), full = stats(games);
  const tests = [
    Object.fromEntries(group.map(t => [t, pct(val(h2h,t,"w"), val(h2h,t,"l"))])),
    Object.fromEntries(group.map(t => [t, pct(val(full,t,"sw"), val(full,t,"sl"))])),
  ];
  for (const slot of above) {
    const opp = new Set(Array.isArray(slot) ? slot : [slot]);
    const rec = Object.fromEntries(group.map(t => [t, [0, 0]]));
    for (const [h, a, hs, as] of games) {
      if (tied.has(h) && opp.has(a)) rec[h][hs > as ? 0 : 1]++;
      if (tied.has(a) && opp.has(h)) rec[a][as > hs ? 0 : 1]++;
    }
    tests.push(Object.fromEntries(group.map(t => [t, pct(rec[t][0], rec[t][1])])));
  }
  for (const v of tests) {
    const lead = leader(group, v);
    if (lead) return [lead].concat(breakTie(group.filter(t => t !== lead), games, above.concat([lead])));
  }
  return [group.slice().sort()];
}
function rank(games, teams) {
  const s = stats(games);
  const v = Object.fromEntries(teams.map(t => [t, pct(val(s,t,"w"), val(s,t,"l")) || 0]));
  const distinct = [];
  for (const t of teams) if (!distinct.some(d => same(d, v[t]))) distinct.push(v[t]);
  distinct.sort((x, y) => y - x);
  let slots = [];
  for (const d of distinct) slots = slots.concat(breakTie(teams.filter(t => same(v[t], d)).sort(), games, slots.slice()));
  return slots;
}
const COLS = ["W-L", "Pct.", "Sets", "Set %"];
function cells(games, t) {
  const s = stats(games);
  const w = val(s,t,"w"), l = val(s,t,"l"), sw = val(s,t,"sw"), sl = val(s,t,"sl");
  const f = x => x === null ? "—" : x.toFixed(3).replace(/^0/, "");
  return [`${w}-${l}`, `<b>${f(pct(w, l))}</b>`, `${sw}-${sl}`, f(pct(sw, sl))];
}
"""
