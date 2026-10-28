"""
The sports this project builds pages for.

To add next season's data, change "standings" to the number at the end of the new
standings page address (cciw.org/standings.aspx?standings=NNNN). Everything else
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
}

LOGO_URL = "https://dbukjj6eu5tsf.cloudfront.net/sidearm.sites/cciw.org/images/responsive_2021/main-color.svg"
