"""
CCIW football: regular-season champion and automatic bid (AQ).

The team that finishes first in the conference standings wins the title. Teams tied for
first are co-champions, and these tiebreakers decide which one gets the AQ:
  1. Head-to-head competition among the tied teams
  2. Point differential vs. the tied teams
  3. Fewest defensive yards vs. the tied teams
  4. Random draw
In a multi-team tie, the criteria are used until one team rises above the others.

Defensive yards aren't on the cciw.org schedule pages, so a tie that gets past step 2
is shown as "defensive yards, then random draw".
games.csv for football uses home_goals/away_goals for POINTS scored.
"""
from collections import defaultdict
from fractions import Fraction

from cciw_tiebreaker import load_games, places

KIND = "football"
GAME_WORD = ("game", "games")
RESULTS = ["H", "A"]
NOMINAL = {"H": (28, 21), "A": (21, 28)}
SCORES = {"H": [(21, 20), (24, 17), (28, 14), (35, 10), (42, 7), (49, 0)],
          "A": [(20, 21), (17, 24), (14, 28), (10, 35), (7, 42), (0, 49)]}
EXACT_UP_TO = 0       # always sample scores (football margins are too varied to list)
SAMPLES = 6
UNRESOLVED = "defensive yards, then random draw"
FINAL_LABEL = "Final records"
FOOTER = ("The team that finishes first in the conference standings is the champion. Teams tied for first are "
          "co-champions, and the automatic bid (AQ) goes to the winner of the tiebreakers: 1) head-to-head among "
          "the tied teams; 2) point differential against the tied teams; 3) fewest defensive yards against the "
          "tied teams; 4) random draw. Defensive yards aren't calculated here because they aren't listed on "
          "cciw.org's schedule pages.")


def stats(games, only=None):
    s = defaultdict(lambda: {"w": 0, "l": 0, "pf": 0, "pa": 0})
    for h, a, hp, ap in games:
        if only is not None and not (h in only and a in only):
            continue
        s[h]["pf"] += hp; s[h]["pa"] += ap
        s[a]["pf"] += ap; s[a]["pa"] += hp
        if hp > ap:
            s[h]["w"] += 1; s[a]["l"] += 1
        elif ap > hp:
            s[a]["w"] += 1; s[h]["l"] += 1
    return s


def pct(w, l):
    return Fraction(w, w + l) if w + l else None


def break_tie(group, games):
    if len(group) == 1:
        return [group[0]]
    tied = set(group)
    h2h = stats(games, only=tied)
    tests = [{t: pct(h2h[t]["w"], h2h[t]["l"]) for t in group},          # 1. head-to-head
             {t: h2h[t]["pf"] - h2h[t]["pa"] for t in group}]            # 2. point differential vs tied teams
    for values in tests:          # until ONE team rises above the others; the rest start again
        if any(v is None for v in values.values()):
            continue
        top = max(values.values())
        leaders = [t for t in group if values[t] == top]
        if len(leaders) == 1:
            return [leaders[0]] + break_tie([t for t in group if t != leaders[0]], games)
    return [tuple(sorted(group))]                                         # 3-4. defensive yards / draw


def rank(games, teams):
    s = stats(games)
    value = {t: pct(s[t]["w"], s[t]["l"]) or Fraction(0) for t in teams}
    slots = []
    for v in sorted(set(value.values()), reverse=True):
        slots += break_tie(sorted(t for t in teams if value[t] == v), games)
    return slots


def title(games, teams):
    """(co-champions, AQ) where AQ is a team or a tuple of teams still tied after step 2."""
    s = stats(games)
    value = {t: pct(s[t]["w"], s[t]["l"]) or Fraction(0) for t in teams}
    best = max(value.values())
    champs = tuple(sorted(t for t in teams if value[t] == best))
    return champs, break_tie(list(champs), games)[0]


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
const DEF = {H:[28,21], A:[21,28]};
const SCORE_CHOICES = null;
const UNRESOLVED = "Defensive yards / draw";
const POS_LABEL = "Pos";
function stats(games, only) {
  const s = {};
  const g = t => s[t] || (s[t] = {w:0, l:0, pf:0, pa:0});
  for (const [h, a, hp, ap] of games) {
    if (only && !(only.has(h) && only.has(a))) continue;
    const H = g(h), A = g(a);
    H.pf += hp; H.pa += ap; A.pf += ap; A.pa += hp;
    if (hp > ap) { H.w++; A.l++; } else if (ap > hp) { A.w++; H.l++; }
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
function breakTie(group, games) {
  if (group.length === 1) return [group[0]];
  const h2h = stats(games, new Set(group));
  const tests = [Object.fromEntries(group.map(t => [t, pct(val(h2h,t,"w"), val(h2h,t,"l"))])),
                 Object.fromEntries(group.map(t => [t, val(h2h,t,"pf") - val(h2h,t,"pa")]))];
  for (const v of tests) {
    if (group.some(t => v[t] === null)) continue;
    const top = Math.max(...group.map(t => v[t]));
    const leaders = group.filter(t => same(v[t], top));
    if (leaders.length === 1) return [leaders[0]].concat(breakTie(group.filter(t => t !== leaders[0]), games));
  }
  return [group.slice().sort()];
}
function rank(games, teams) {
  const s = stats(games);
  const v = Object.fromEntries(teams.map(t => [t, pct(val(s,t,"w"), val(s,t,"l")) || 0]));
  let slots = [];
  for (const p of groupsBy(teams.slice().sort(), v)) slots = slots.concat(breakTie(p, games));
  return slots;
}
function STATUS(t, games) {
  const s = stats(games);
  const v = Object.fromEntries(CFG.teams.map(x => [x, pct(val(s,x,"w"), val(s,x,"l")) || 0]));
  const best = Math.max(...Object.values(v));
  const champs = CFG.teams.filter(x => same(v[x], best));
  if (!champs.includes(t)) return "";
  const aq = breakTie(champs.slice().sort(), games)[0];
  if (champs.length === 1) return "<span class='tag'>First · AQ</span>";
  if (Array.isArray(aq)) return aq.includes(t) ? "<span class='tag tie'>Tied for first · AQ on yards/draw</span>" : "<span class='tag'>Tied for first</span>";
  return aq === t ? "<span class='tag'>Tied for first · AQ</span>" : "<span class='tag'>Tied for first</span>";
}
const COLS = ["W-L", "Pct.", "PF", "PA"];
function cells(games, t) {
  const s = stats(games);
  const w = val(s,t,"w"), l = val(s,t,"l");
  const p = pct(w, l);
  return [`${w}-${l}`, `<b>${p === null ? "—" : p.toFixed(3).replace(/^0/, "")}</b>`, val(s,t,"pf"), val(s,t,"pa")];
}
"""
