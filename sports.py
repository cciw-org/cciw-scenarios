"""
The sports this project builds pages for.

To add next season's data, change "standings" to the number at the end of the new
standings page address (cciw.org/standings.aspx?standings=NNNN). A "path=..." value
(like women's tennis) always points at the current season, so it never needs changing. Everything else
(teams, schedule pages) is read from that page automatically.
"""

SPORTS = {
    "msoc": {
        "name": "CCIW Men's Soccer",
        "standings": 1219,
        "kind": "soccer",            # which tiebreaker rules to use
        "folder": ".",               # page address: .../cciw-scenarios/
        "qualifiers": 6,
        "tournament": "CCIW Tournament",
    },
    "wsoc": {
        "name": "CCIW Women's Soccer",
        "standings": 1221,
        "kind": "soccer",
        "folder": "wsoc",            # page address: .../cciw-scenarios/wsoc/
        "qualifiers": 6,
        "tournament": "CCIW Tournament",
    },
    "volleyball": {
        "name": "CCIW Women's Volleyball",
        "standings": 1206,
        "kind": "volleyball",
        "folder": "volleyball",      # page address: .../cciw-scenarios/volleyball/
        "qualifiers": 6,
        "tournament": "CCIW Tournament",
    },
    "football": {
        "name": "CCIW Football",
        "standings": 1220,
        "kind": "football",          # regular-season title + automatic bid (AQ), no tournament
        "folder": "football",        # page address: .../cciw-scenarios/football/
        "qualifiers": 1,
        "tournament": "NCAA automatic bid",
    },
    "wten": {
        "name": "CCIW Women's Tennis",
        "standings": "path=wten",    # this kind of link always shows the current season
        "kind": "tennis",
        "folder": "wten",            # page address: .../cciw-scenarios/wten/
        "qualifiers": 6,
        "tournament": "CCIW Championships",
    },
    "mbb": {
        "name": "CCIW Men's Basketball",
        "standings": 1225,
        "kind": "basketball",
        "meetings": 2,               # double round-robin
        "folder": "mbb",             # page address: .../cciw-scenarios/mbb/
        "qualifiers": 6,
        "tournament": "CCIW Tournament",
    },
    "wbb": {
        "name": "CCIW Women's Basketball",
        "standings": 1226,
        "kind": "basketball",
        "meetings": 2,
        "folder": "wbb",             # page address: .../cciw-scenarios/wbb/
        "qualifiers": 6,
        "tournament": "CCIW Tournament",
    },
    "wrestling": {
        "name": "CCIW Men's Wrestling",
        "standings": "path=wrestling",   # always the current season
        "kind": "wrestling",             # regular-season title only; ties are co-champions
        "folder": "wrestling",           # page address: .../cciw-scenarios/wrestling/
        "qualifiers": 1,
        "tournament": "regular-season title",
        "conference_games_only": True,   # ignore tournaments and unmarked events on the schedules
        "min_opponents": 7,
        # Previous season's top 4 (all four must be on a team's schedule to be title-eligible).
        # Update this each year.
        "previous_top": ["North Central", "Millikin", "Elmhurst"],
    },
}

LOGO_URL = "https://dbukjj6eu5tsf.cloudfront.net/sidearm.sites/cciw.org/images/responsive_2021/main-color.svg"
