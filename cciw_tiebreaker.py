"""
CCIW soccer tiebreakers (men's and women's).

Standings: 3 points for a win, 1 for a tie.
Tiebreakers, in order:
  1. Head-to-head among the tied teams (mini-table: 3 pts win, 1 tie)
  2. Goal differential in all conference matches, capped at 3 per match
  3. Fewest goals allowed in all conference matches
  4. Random action
For 3+ team ties: once a criterion separates teams, each remaining tied
group starts over at step 1. Random draws stay within their own group.

Can also be run on its own to print every scenario:
    python3 cciw_tiebreaker.py wsoc/games.csv
"""
import csv
import sys
from collections import defaultdict
from itertools import product

# ---------------- settings ----------------
WIN_PTS, DRAW_PTS = 3, 1
GD_CAP = 3            # max goal differential counted per match
GD_SCOPE = "all"      # "all"  = all conference matches (how rule b.ii is read here)
                      # "tied" = only matches among the tied teams
QUALIFIERS = 6
# ------------------------------------------

# ---- details the page builder uses ----
KIND = "soccer"
GAME_WORD = ("game", "games")
RESULTS = ["H", "D", "A"]
NOMINAL = {"H": (1, 0), "D": (1, 1), "A": (0, 1)}
SCORES = {   # every score tried for each result (0-0 up to 4-4)
    "H": [(x, y) for x in range(5) for y in range(5) if x > y],
    "D": [(x, x) for x in range(5)],
    "A": [(x, y) for x in range(5) for y in range(5) if x < y],
}
EXACT_UP_TO = 3       # this many games left or fewer: try every score above
SAMPLES = 4           # otherwise: extra random scores tried per scenario
UNRESOLVED = "random draw"
FINAL_LABEL = "Final points"
DEP_NOTE = ("Tied on points and head-to-head, so the exact scores decide it: goal differential "
            f"(capped at {GD_CAP} per match), then fewest goals allowed.")
FOOTER = (f"Standings: 3 points for a win, 1 for a tie. Tiebreakers: 1) head-to-head among the tied teams; "
          f"2) goal differential in all conference matches, capped at {GD_CAP} per match; 3) fewest goals "
          "allowed in conference matches; 4) random draw. With three or more teams tied, once a team "
          "separates, the remaining teams start again at step 1.")


def load_games(path):
    played, remaining = [], []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            h, a = r["home"].strip(), r["away"].strip()
            if str(r["home_goals"]).strip() == "":
                remaining.append((h, a))
            else:
                played.append((h, a, int(r["home_goals"]), int(r["away_goals"])))
    return played, remaining


def stats(games, only=None):
    """Points, capped goal differential and goals allowed.
    If `only` is a set of teams, count only games played between those teams."""
    s = defaultdict(lambda: {"pts": 0, "cgd": 0, "ga": 0, "w": 0, "l": 0, "d": 0})
    for h, a, hg, ag in games:
        if only is not None and not (h in only and a in only):
            continue
        d = max(-GD_CAP, min(GD_CAP, hg - ag))
        s[h]["cgd"] += d
        s[a]["cgd"] -= d
        s[h]["ga"] += ag
        s[a]["ga"] += hg
        if hg > ag:
            s[h]["pts"] += WIN_PTS; s[h]["w"] += 1; s[a]["l"] += 1
        elif hg < ag:
            s[a]["pts"] += WIN_PTS; s[a]["w"] += 1; s[h]["l"] += 1
        else:
            s[h]["pts"] += DRAW_PTS; s[a]["pts"] += DRAW_PTS; s[h]["d"] += 1; s[a]["d"] += 1
    return s


def criteria(group, games):
    tied = set(group)
    h2h = stats(games, only=tied)
    gd = stats(games, only=tied if GD_SCOPE == "tied" else None)
    full = stats(games)
    return [
        lambda t: h2h[t]["pts"],    # 1. head-to-head
        lambda t: gd[t]["cgd"],     # 2. capped goal differential
        lambda t: -full[t]["ga"],   # 3. fewest goals allowed (negated so higher = better)
    ]


def break_tie(group, games):
    """Order teams tied on points. Returns a list of slots: a team name,
    or a tuple of teams that only a random draw can separate."""
    if len(group) == 1:
        return [group[0]]
    for key in criteria(group, games):
        vals = {t: key(t) for t in group}
        if len(set(vals.values())) > 1:
            order = []
            for v in sorted(set(vals.values()), reverse=True):
                order += break_tie([t for t in group if vals[t] == v], games)  # restart at step 1
            return order
    return [tuple(sorted(group))]               # 4. random action


def rank(games, teams):
    s = stats(games)
    slots = []
    for p in sorted({s[t]["pts"] for t in teams}, reverse=True):
        slots += break_tie(sorted(t for t in teams if s[t]["pts"] == p), games)
    return slots


def places(slots):
    """team -> (best, worst) place. A random-draw group spans several places."""
    out, place = {}, 1
    for slot in slots:
        group = slot if isinstance(slot, tuple) else (slot,)
        for t in group:
            out[t] = (place, place + len(group) - 1)
        place += len(group)
    return out


# ---- text helpers for the page ----
def record_text(team, games):
    s = stats(games)[team]
    return f"{s['w']}-{s['l']}-{s['d']}"


def standing_value(team, games):
    return stats(games)[team]["pts"]


def final_line(team, played, left):
    base = standing_value(team, played)
    if left == 0:
        return f"{base} (season complete)"
    if left == 1:
        return f"{base} with a loss, {base + DRAW_PTS} with a tie, {base + WIN_PTS} with a win"
    return f"{base} to {base + WIN_PTS * left}"


# JavaScript version of the same rules, for the scenario builder on the page
JS = r"""
const RES = [["A", a => a + " win"], ["D", () => "Tie"], ["H", h => h + " win"]];
const DEF = {H:[1,0], D:[1,1], A:[0,1]};
const SCORE_CHOICES = null;          // free number boxes
const UNRESOLVED = "Random draw";
function stats(games, only) {
  const s = {};
  const g = t => s[t] || (s[t] = {pts:0, cgd:0, ga:0, w:0, l:0, d:0});
  for (const [h, a, hg, ag] of games) {
    if (only && !(only.has(h) && only.has(a))) continue;
    const H = g(h), A = g(a);
    const diff = Math.max(-CFG.cap, Math.min(CFG.cap, hg - ag));
    H.cgd += diff; A.cgd -= diff; H.ga += ag; A.ga += hg;
    if (hg > ag) { H.pts += 3; H.w++; A.l++; }
    else if (hg < ag) { A.pts += 3; A.w++; H.l++; }
    else { H.pts += 1; A.pts += 1; H.d++; A.d++; }
  }
  return s;
}
const val = (s, t, k) => (s[t] ? s[t][k] : 0);
function breakTie(group, games) {
  if (group.length === 1) return [group[0]];
  const tied = new Set(group);
  const h2h = stats(games, tied), gd = stats(games, CFG.scope === "tied" ? tied : null), full = stats(games);
  const keys = [t => val(h2h, t, "pts"), t => val(gd, t, "cgd"), t => -val(full, t, "ga")];
  for (const key of keys) {
    const v = Object.fromEntries(group.map(t => [t, key(t)]));
    const distinct = [...new Set(Object.values(v))].sort((x, y) => y - x);
    if (distinct.length > 1) {
      let out = [];
      for (const x of distinct) out = out.concat(breakTie(group.filter(t => v[t] === x), games));
      return out;
    }
  }
  return [group.slice().sort()];
}
function rank(games, teams) {
  const s = stats(games);
  const pts = [...new Set(teams.map(t => val(s, t, "pts")))].sort((x, y) => y - x);
  let slots = [];
  for (const p of pts) slots = slots.concat(breakTie(teams.filter(t => val(s, t, "pts") === p).sort(), games));
  return slots;
}
const COLS = ["W-L-T", "Pts", "Capped GD", "GA"];
function cells(games, t) {
  const s = stats(games);
  const gd = val(s, t, "cgd");
  return [`${val(s,t,"w")}-${val(s,t,"l")}-${val(s,t,"d")}`, `<b>${val(s,t,"pts")}</b>`, (gd > 0 ? "+" : "") + gd, val(s,t,"ga")];
}
"""


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "games.csv"
    played, remaining = load_games(path)
    teams = sorted({t for g in played for t in g[:2]} | {t for g in remaining for t in g})
    print(f"Teams: {len(teams)}   Played: {len(played)}   Unplayed: {len(remaining)}")
    print("Current order:")
    for t, (b, w) in sorted(places(rank(played, teams)).items(), key=lambda x: x[1]):
        print(f"  {b if b == w else f'{b}-{w}'}. {t}  ({record_text(t, played)}, {standing_value(t, played)} pts)")
    if len(remaining) > 8:
        print("Too many games left to list every scenario here; use the web page.")
        return
    for combo in product(RESULTS, repeat=len(remaining)):
        sim = [(h, a, *NOMINAL[r]) for (h, a), r in zip(remaining, combo)]
        order = places(rank(played + sim, teams))
        desc = "; ".join(f"{a} at {h}: {r}" for (h, a), r in zip(remaining, combo))
        print(desc, "->", ", ".join(t for t, _ in sorted(order.items(), key=lambda x: x[1])[:QUALIFIERS]))


if __name__ == "__main__":
    main()
