"""
Tools: ais_search_people, ais_get_person
"""
import json

from ais_mcp.parsers import parse_person, parse_people_list
from ais_mcp.session import get_session, BASE_URL

PEOPLE_URL = f"{BASE_URL}/auth/lide/index.pl"
SUGGEST_URL = f"{BASE_URL}/auth/system/uissuggest.pl"

SUBJECTS = [
    "21980", "21050", "21900", "21070", "21040",
    "21970", "21020", "21960", "21950", "21060",
    "21940", "21030", "21010",
]


def tool_search_people(
    query: str,
    students: bool = True,
    staff: bool = True,
    graduates: bool = False,
    external: bool = False,
    suggest: bool = True,
) -> dict:
    """
    Search AIS people directory.
    suggest=True uses the fast autocomplete endpoint (max 25 results).
    suggest=False does a full search (slower, no cap).
    """
    query = query.strip()
    if len(query) < 3:
        raise ValueError("Query must be at least 3 characters")

    sess = get_session()

    if suggest:
        data = [
            ("_suggestKey", query),
            ("upresneni_default", "-"),
            ("_suggestMaxItems", "50"),
        ]
        data += [("subjekt", s) for s in SUBJECTS]
        if students:
            data.append(("upresneni", "aktivni_a_preruseni"))
        if graduates:
            data.append(("upresneni", "absolventi"))
        if staff:
            data.append(("upresneni", "zamestnanci"))
        if external:
            data.append(("upresneni", "externiste"))
        data += [("vzorek", ""), ("_suggestHandler", "lide"), ("lang", "en")]

        resp = sess.post(SUGGEST_URL, data=data)
        payload = json.loads(resp.text or '{"data":[],"more":0}')
        results = []
        for row in payload.get("data", []):
            if len(row) < 2:
                continue
            person_id = str(row[1])
            results.append({
                "name": " ".join(str(row[0]).split()),
                "description": " ".join(str(row[3] if len(row) > 3 else "").split()),
                "url": f"{BASE_URL}/auth/lide/clovek.pl?id={person_id}&lang=en",
            })
        return {"results": results, "more": bool(payload.get("more")), "mode": "suggest"}
    else:
        data = [("vzorek", query), ("Search", "Search")]
        data += [("subjekt", s) for s in SUBJECTS]
        if students:
            data.append(("upresneni", "aktivni_a_preruseni"))
        if graduates:
            data.append(("upresneni", "absolventi"))
        if staff:
            data.append(("upresneni", "zamestnanci"))
        if external:
            data.append(("upresneni", "externiste"))

        resp = sess.post(PEOPLE_URL, data=data, allow_redirects=True)
        result = parse_people_list(resp.url, resp.text)
        return {**result, "mode": "full"}


def tool_get_person(id_or_url: str) -> dict:
    """
    Fetch full profile of a person.
    Pass either a numeric ID or a full is.stuba.sk URL.
    """
    sess = get_session()
    if id_or_url.startswith("http"):
        url = id_or_url
    else:
        url = f"{BASE_URL}/auth/lide/clovek.pl?id={id_or_url}&lang=en"
    resp = sess.get(url)
    return parse_person(resp.url, resp.text)
