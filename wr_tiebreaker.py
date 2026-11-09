"""
CCIW men's wrestling: regular-season championship from dual meets.

Standings: conference dual-meet winning percentage (teams set their own schedules, so
they wrestle different numbers of conference duals).
To be eligible for the title, a team must wrestle at least 7 conference opponents,
including all of the previous season's top 4 (set in sports.py).
There is no tiebreaker: eligible teams tied for first are co-champions.

games.csv for wrestling uses home_goals/away_goals for the TEAM SCORE of each dual.
"""
from collections import defaultdict
from fractions import Fraction

from cciw_tiebreaker import load_games, places

KIND = "wrestling"
HAS_AQ = False
GAME_WORD = ("dual", "duals")
RESULTS = ["H", "A"]
NOMINAL = {"H": (24, 12), "A": (12, 24)}
SCORES = {"H": [(24, 12)], "A": [(12, 24)]}   # the score never matters here
SAMPLES = 0
FINAL_LABEL = "Final records"
MIN_OPP = 7          # set from sports.py by title_page.py
PREV_TOP = []        # previous season's top 4, set from sports.py
INTRO = ("The eligible team with the best conference dual record is the CCIW regular-season champion. "
         "There is no tiebreaker, so eligible teams tied for first are co-champions.")
STAR = ""


def footer():
    top = f", including {_names(PREV_TOP)}" if PREV_TOP else ", including all of the previous season's top 4"
    return (f"Standings: conference dual-meet winning percentage. To be eligible for the regular-season title, a team "
            f"must wrestle at least {MIN_OPP} conference opponents{top}. There is no tiebreaker: eligible teams tied "
            f"for first are co-champions. Eligibility counts duals already wrestled plus those still on the schedule.")


def stats(games):
    s = defaultdict(lambda: {"w": 0, "l": 0, "t": 0, "pf": 0, "pa": 0})
    for h, a, hs, as_ in games:
        s[h]["pf"] += hs; s[h]["pa"] += as_
        s[a]["pf"] += as_; s[a]["pa"] += hs
        if hs > as_:
            s[h]["w"] += 1; s[a]["l"] += 1
        elif as_ > hs:
            s[a]["w"] += 1; s[h]["l"] += 1
        else:
            s[h]["t"] += 1; s[a]["t"] += 1
    return s


def pct(r):
    n = r["w"] + r["l"] + r["t"]
    return Fraction(2 * r["w"] + r["t"], 2 * n) if n else Fraction(0)


def opponents(schedule):
    """team -> set of conference opponents on its schedule (wrestled or still to come)."""
    opp = defaultdict(set)
    for g in schedule:
        h, a = g[0], g[1]
        opp[h].add(a)
        opp[a].add(h)
    return opp


def eligible(team, schedule):
    o = opponents(schedule)[team]
    return len(o) >= MIN_OPP and all(p in o for p in PREV_TOP if p != team)


def why_not(team, schedule):
    o = opponents(schedule)[team]
    reasons = []
    if len(o) < MIN_OPP:
        reasons.append(f"{len(o)} conference opponents on its schedule; {MIN_OPP} required")
    missing = [p for p in PREV_TOP if p != team and p not in o]
    if missing:
        reasons.append(f"doesn't wrestle {_names(missing)}")
    return "; ".join(reasons)


def rank(games, teams):
    s = stats(games)
    v = {t: pct(s[t]) for t in teams}
    return [tuple(sorted(t for t in teams if v[t] == x)) if sum(1 for t in teams if v[t] == x) > 1
            else next(t for t in teams if v[t] == x) for x in sorted(set(v.values()), reverse=True)]


def title(games, teams, schedule=None):
    """(co-champions, None) among eligible teams."""
    sched = schedule if schedule is not None else games
    s = stats(games)
    ok = [t for t in teams if eligible(t, sched)]
    if not ok:
        return (), None
    best = max(pct(s[t]) for t in ok)
    return tuple(sorted(t for t in ok if pct(s[t]) == best)), None


def record_text(team, games):
    s = stats(games)[team]
    return f"{s['w']}-{s['l']}" + (f"-{s['t']}" if s["t"] else "")


def final_line(team, played, left):
    s = stats(played)[team]
    w, l = s["w"], s["l"]
    if left == 0:
        return f"{record_text(team, played)} (season complete)"
    if left == 1:
        return f"{w}-{l + 1} with a loss, {w + 1}-{l} with a win"
    return f"between {w}-{l + left} and {w + left}-{l}"


def _names(g):
    g = list(g)
    return ", ".join(g[:-1]) + (" and " if len(g) > 1 else "") + g[-1] if g else ""


JS = r"""
const RES = [["A", a => a + " win"], ["H", h => h + " win"]];
const DEF = {H:[24,12], A:[12,24]};
const SCORE_CHOICES = [];
const UNRESOLVED = "Tied";
const POS_LABEL = "Pos";
function stats(games) {
  const s = {};
  const g = t => s[t] || (s[t] = {w:0, l:0, t:0});
  for (const [h, a, hs, as] of games) {
    const H = g(h), A = g(a);
    if (hs > as) { H.w++; A.l++; } else if (as > hs) { A.w++; H.l++; } else { H.t++; A.t++; }
  }
  return s;
}
const val = (s, t, k) => (s[t] ? s[t][k] : 0);
const pctOf = (s, t) => { const n = val(s,t,"w") + val(s,t,"l") + val(s,t,"t"); return n ? (2*val(s,t,"w") + val(s,t,"t")) / (2*n) : 0; };
const same = (x, y) => Math.abs(x - y) < 1e-9;
function rank(games, teams) {
  const s = stats(games);
  const vals = [];
  for (const t of teams) if (!vals.some(v => same(v, pctOf(s, t)))) vals.push(pctOf(s, t));
  vals.sort((x, y) => y - x);
  return vals.map(v => { const g = teams.filter(t => same(pctOf(s, t), v)).sort(); return g.length > 1 ? g : g[0]; });
}
function eligibleTeams() {
  const opp = {};
  for (const [h, a] of CFG.played.concat(CFG.remaining)) {
    (opp[h] = opp[h] || new Set()).add(a); (opp[a] = opp[a] || new Set()).add(h);
  }
  return CFG.teams.filter(t => opp[t] && opp[t].size >= CFG.min_opp && CFG.prev_top.every(p => p === t || opp[t].has(p)));
}
function STATUS(t, games) {
  const ok = eligibleTeams();
  if (!ok.includes(t)) return "<span class='tag outt'>Not eligible</span>";
  const s = stats(games);
  const best = Math.max(...ok.map(x => pctOf(s, x)));
  if (!same(pctOf(s, t), best)) return "";
  return ok.filter(x => same(pctOf(s, x), best)).length > 1 ? "<span class='tag'>Co-champion</span>" : "<span class='tag'>Champion</span>";
}
const COLS = ["W-L", "Pct."];
function cells(games, t) {
  const s = stats(games);
  const rec = `${val(s,t,"w")}-${val(s,t,"l")}` + (val(s,t,"t") ? `-${val(s,t,"t")}` : "");
  return [rec, `<b>${pctOf(s, t).toFixed(3).replace(/^0/, "")}</b>`];
}
"""


# ---------- clinching, worked out directly (works with any number of duals left) ----------
def _rec(games, team):
    s = stats(games)[team]
    return s["w"], s["l"], s["t"]


def _p(w, l, t):
    n = w + l + t
    return Fraction(2 * w + t, 2 * n) if n else Fraction(0)


def _bounds(team, played, remaining, forced):
    """(lowest, highest) final pct for `team`; `forced` maps a remaining dual -> winner already decided."""
    w, l, t = _rec(played, team)
    lo_w, lo_l, hi_w, hi_l = w, l, w, l
    for g in remaining:
        if team not in g:
            continue
        if g in forced:
            if forced[g] == team:
                lo_w += 1; hi_w += 1
            else:
                lo_l += 1; hi_l += 1
        else:
            lo_l += 1; hi_w += 1
    return _p(lo_w, lo_l, t), _p(hi_w, hi_l, t)


def clinch_watch(team, played, remaining, teams, order):
    """For `team` winning its remaining duals in date order (`order` = list of its remaining duals),
    return (share_at, outright_at): how many wins it needs (0 = already clinched, None = can't
    clinch on its own) to guarantee at least a share / the outright title."""
    sched = played + [(h, a, 0, 0) for h, a in remaining]
    rivals = [r for r in teams if r != team and eligible(r, sched)]
    share_at = outright_at = None
    for j in range(len(order) + 1):
        forced = {g: team for g in order[:j]}
        my_lo, _ = _bounds(team, played, remaining, forced)
        rmax = [_bounds(r, played, remaining, forced)[1] for r in rivals]
        if share_at is None and all(my_lo >= x for x in rmax):
            share_at = j
        if outright_at is None and all(my_lo > x for x in rmax):
            outright_at = j
    return share_at, outright_at


def can_still_win(team, played, remaining, teams):
    """False if some eligible rival is guaranteed to finish above `team` even if `team` wins out."""
    sched = played + [(h, a, 0, 0) for h, a in remaining]
    forced = {g: team for g in remaining if team in g}
    _, my_hi = _bounds(team, played, remaining, forced)
    for r in teams:
        if r != team and eligible(r, sched):
            r_lo, _ = _bounds(r, played, remaining, forced)
            if r_lo > my_hi:
                return False
    return True
