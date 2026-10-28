"""
Scrapes CCIW conference results into each sport's games.csv.
Install first:  pip3 install pandas lxml requests
Run:            python3 scrape_cciw.py          (all sports)
                python3 scrape_cciw.py wsoc     (one sport)

Teams and schedule pages are read from the standings page listed in sports.py.
A result missing from one team's schedule page is taken from the opponent's page.
At the end, the records it worked out are checked against the official standings.
"""
import csv
import os
import re
import sys
import time
from io import StringIO

import pandas as pd
import requests
from lxml import html as lxml_html

from sports import SPORTS

BASE = "https://cciw.org"
HEADERS = {   # look like a normal web browser; the site sends scripts an empty page otherwise
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
session = requests.Session()
session.headers.update(HEADERS)


def fetch(url):
    """Download a page, retrying if the site sends back nothing."""
    r = None
    for attempt in range(4):
        r = session.get(url, timeout=30)
        if r.status_code == 200 and "<table" in r.text.lower():
            return r.text
        time.sleep(2 + attempt * 3)
    raise RuntimeError(f"Could not read {url} (status {r.status_code}, {len(r.text)} characters)")


def find_col(table, word):
    for c in table.columns:
        if word.lower() in str(c).lower():
            return c
    return None


def read_standings(sid):
    html = fetch(f"{BASE}/standings.aspx?standings={sid}")
    doc = lxml_html.fromstring(html)
    teams = {}
    for a in doc.xpath('//a[contains(@href, "schedule.aspx?schedule=")]'):
        name = a.text_content().strip().strip("*#").strip()
        m = re.search(r"schedule=(\d+)", a.get("href", ""))
        if name and m:
            teams[name] = int(m.group(1))
    official = {}
    try:
        table = pd.read_html(StringIO(html), match="Conf")[0]
        conf_col = find_col(table, "Conf")
        for _, row in table.iterrows():
            row_text = " ".join(str(v) for v in row.values)
            for name in teams:
                if name in row_text:
                    official[name] = str(row[conf_col]).strip()
    except Exception:
        pass   # the check at the end is skipped if the table can't be read
    return teams, official


def match_team(text, teams):
    best = None
    for name in teams:
        if name.lower() in text.lower() and (best is None or len(name) > len(best)):
            best = name
    return best


def scrape(key):
    cfg = SPORTS[key]
    print(f"\n{cfg['name']}")
    teams, official = read_standings(cfg["standings"])
    if len(teams) < 4:
        raise RuntimeError("Couldn't find the teams on the standings page")
    games = {}   # each pair of teams meets once in the conference regular season
    marked_pairs = set()
    for team, sid in teams.items():
        print(f"  Reading {team}...")
        html = fetch(f"{BASE}/schedule.aspx?schedule={sid}")
        table = pd.read_html(StringIO(html), match="Opponent")[0]
        opp_col, res_col, date_col = find_col(table, "Opponent"), find_col(table, "Result"), find_col(table, "Date")
        is_conf = table.apply(lambda row: any(str(v).strip() == "*" for v in row), axis=1)
        # conference games first; then unmarked games against conference teams, in case the site
        # forgot the * (they only count if that pair has no marked game)
        rows = [(r, True) for _, r in table[is_conf].iterrows()] + [(r, False) for _, r in table[~is_conf].iterrows()]
        for row, marked in rows:
            opp_text = str(row[opp_col])
            opp = match_team(opp_text, teams)
            if opp is None or opp == team:
                if marked:
                    print(f"    Couldn't match opponent '{opp_text}' - skipped")
                continue
            away = opp_text.strip().lower().startswith("at ")
            home, visitor = (opp, team) if away else (team, opp)
            m = re.match(r"\s*[WLT]\s+(\d+)\s*-\s*(\d+)", str(row[res_col]))
            if m:
                us, them = int(m.group(1)), int(m.group(2))     # listed with this team's score first
                hs, vs = (them, us) if away else (us, them)
            else:
                hs = vs = ""                                     # not played yet (or not posted)
            k = frozenset((home, visitor))
            old = games.get(k)
            if not marked and k in marked_pairs:
                continue
            if marked:
                marked_pairs.add(k)
            elif old is None:
                print(f"    Counting {visitor} at {home} as a conference game (not marked * on {team}'s page)")
            if old is None or (old["hs"] == "" and hs != ""):
                games[k] = {"date": str(row[date_col]).strip(), "home": home, "away": visitor, "hs": hs, "vs": vs}
        time.sleep(1.5)   # be gentle with the website

    # scores typed in by hand (fixes.csv) fill in results the site hasn't posted
    fixes = os.path.join(cfg["folder"], "fixes.csv")
    if os.path.exists(fixes):
        with open(fixes, newline="") as f:
            for r in csv.DictReader(f):
                h, a = r["home"].strip(), r["away"].strip()
                g = games.get(frozenset((h, a)))
                if g and g["hs"] == "" and str(r["home_goals"]).strip() != "":
                    hg, ag = int(r["home_goals"]), int(r["away_goals"])
                    g["hs"], g["vs"] = (hg, ag) if g["home"] == h else (ag, hg)
                    print(f"  Used fixes.csv for {a} at {h}")

    # check against the official standings
    problems = []
    for name, rec in official.items():
        w = l = d = 0
        for g in games.values():
            if g["hs"] == "" or name not in (g["home"], g["away"]):
                continue
            us, them = (g["hs"], g["vs"]) if name == g["home"] else (g["vs"], g["hs"])
            w += us > them; l += us < them; d += us == them
        want = [int(x) for x in re.findall(r"\d+", rec)] + [0, 0, 0]
        if (w, l, d) != tuple(want[:3]):
            problems.append(f"{name}: standings say {rec}, schedule pages give {w}-{l}" + (f"-{d}" if d else ""))

    path = os.path.join(cfg["folder"], "games.csv")
    os.makedirs(cfg["folder"], exist_ok=True)
    with open(path, "w", newline="") as f:
        w_ = csv.writer(f)
        w_.writerow(["date", "home", "away", "home_goals", "away_goals"])
        for g in sorted(games.values(), key=lambda g: (pd.to_datetime(g["date"], errors="coerce"), g["home"])):
            w_.writerow([g["date"], g["home"], g["away"], g["hs"], g["vs"]])
    print(f"  {len(games)} conference {'matches' if cfg['kind'] == 'volleyball' else 'games'} saved to {path}")
    if problems:
        print("  WARNING - some results aren't posted on the schedule pages yet:")
        for p in problems:
            print("   ", p)
        print(f"  Add the missing scores to {fixes}, or wait for the site to post them.")


if __name__ == "__main__":
    failed = []
    for key in (sys.argv[1:] or SPORTS):
        try:
            scrape(key)
        except Exception as e:
            print(f"  FAILED: {e}  (keeping the old games.csv)")
            failed.append(key)
    if failed:
        print("\nCould not update:", ", ".join(failed))
