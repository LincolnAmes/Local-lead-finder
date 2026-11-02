# Local Lead Finder
# Finds local businesses that have a phone number but NO website, using free
# OpenStreetMap data. Saves the results to a CSV file you can open in Excel.
# No account, API key, or credit card needed.
# Data (c) OpenStreetMap contributors - https://www.openstreetmap.org/copyright

import csv
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime

# ------------------------------------------------------------
# SETTINGS (safe to edit)
# ------------------------------------------------------------
DEFAULT_STATE = "Utah"
DEFAULT_CITIES = [
    "Holladay", "Murray", "Millcreek", "Cottonwood Heights", "Sandy",
    "Draper", "Midvale", "South Salt Lake", "Taylorsville", "West Jordan",
    "South Jordan", "Riverton", "Herriman", "West Valley City",
    "Salt Lake City",
]

OUTPUT_NAME = "leads.csv"

SHOPS = ("car_repair|tyres|locksmith|laundry|dry_cleaning|hairdresser|beauty|"
         "massage|tattoo|pet_grooming|florist|bakery|photo|sewing|tailor")
AMENITIES = "car_wash|veterinary|childcare"
SKIP_OFFICES = ("government|diplomatic|ngo|political_party|religion|association|"
                "educational_institution|foundation|research|union|quango|"
                "charity|employment_agency")

# Big chains and non-business names are skipped.
CHAINS = [
    "jiffy lube", "valvoline", "midas", "meineke", "firestone", "goodyear",
    "discount tire", "les schwab", "mavis", "take 5", "great clips",
    "sport clips", "supercuts", "fantastic sams", "massage envy",
    "european wax", "mr. rooter", "roto-rooter", "servpro", "stanley steemer",
    "merry maids", "molly maid", "home depot", "lowe's", "walmart", "costco",
    "target", "ups store", "fedex", "state farm", "allstate",
    "farmers insurance", "h&r block", "planet fitness", "pep boys",
    "autozone", "o'reilly", "napa auto", "enterprise", "chase bank",
    "wells fargo", "zions bank", "america first", "usps", "post office",
    "kneaders", "hand & stone", "hand and stone", "rocky's tire", "fix auto",
    "land rover", "diamond rental", "starbucks", "mcdonald", "subway",
    "7-eleven", "walgreens", "cvs", "ulta", "sally beauty", "regis",
    "ace hardware", "napa ", "big o tires", "tire pros", "maaco", "caliber",
]
NOT_BUSINESSES = [
    "elementary", "high school", "middle school", "church of", "city of",
    "county", "university", "hospital", "library", "school district",
]

SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
USER_AGENT = "local-lead-finder/4.0 (open source hobby project)"
NO_SITE = '[!"website"][!"contact:website"][!"url"]["name"]'
GROUPS = ["trades", "offices", "shops"]


# ------------------------------------------------------------
# TALKING TO THE FREE SERVERS
# ------------------------------------------------------------
def fetch(url, data=None, timeout=60):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def geocode(city, state):
    """Find the rough map box for a city."""
    q = urllib.parse.urlencode(
        {"q": f"{city}, {state}", "format": "json", "limit": 1}
    )
    try:
        found = fetch("https://nominatim.openstreetmap.org/search?" + q, timeout=20)
    except Exception:
        found = None
    time.sleep(1.5)
    if not found:
        return None
    south, north, west, east = [float(x) for x in found[0]["boundingbox"]]
    pad = 0.02
    return (south - pad, west - pad, north + pad, east + pad)


def make_search(city, box, group, box_only=False):
    south, west, north, east = box
    bbox = f"{south:.5f},{west:.5f},{north:.5f},{east:.5f}"
    city = city.replace('"', "")
    if box_only:
        header, where = "", f"({bbox})"
    else:
        header = (f'rel["name"~"^{city}$",i]["boundary"="administrative"]({bbox});\n'
                  "map_to_area->.a;\n")
        where = "(area.a)"

    if group == "trades":
        filters = [f'["craft"]{NO_SITE}']
    elif group == "offices":
        filters = [f'["office"]["office"!~"^({SKIP_OFFICES})$"]{NO_SITE}']
    else:
        filters = [f'["shop"~"^({SHOPS})$"]{NO_SITE}',
                   f'["amenity"~"^({AMENITIES})$"]{NO_SITE}']

    body = "\n".join(f"  nwr{where}{f};" for f in filters)
    return f"[out:json][timeout:30];\n{header}(\n{body}\n);\nout center tags;\n"


def run_search(query, tries=1):
    """Try each server. Gives up quickly. Returns a list, or None if it failed."""
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    for attempt in range(tries):
        for url in SERVERS:
            try:
                return fetch(url, data=data, timeout=40).get("elements", [])
            except Exception:
                time.sleep(2)
        if attempt < tries - 1:
            time.sleep(6)
    return None


# ------------------------------------------------------------
# CLEANING UP THE RESULTS
# ------------------------------------------------------------
def should_skip(tags):
    if "brand" in tags or "brand:wikidata" in tags:
        return True
    if tags.get("office") in SKIP_OFFICES.split("|"):
        return True
    name = tags.get("name", "").lower()
    return any(w in name for w in CHAINS) or any(w in name for w in NOT_BUSINESSES)


def kind(tags):
    for key in ("craft", "shop", "office", "amenity"):
        if key in tags:
            value = tags[key].replace("_", " ")
            return "business" if value == "yes" else value
    return ""


def address(tags):
    street = " ".join(
        p for p in (tags.get("addr:housenumber"), tags.get("addr:street")) if p
    )
    parts = [street, tags.get("addr:city"), tags.get("addr:postcode")]
    return ", ".join(p for p in parts if p)


def get_rows(elements, city, state):
    rows = []
    for el in elements:
        tags = el.get("tags", {})
        phone = tags.get("phone") or tags.get("contact:phone")
        if not phone or "name" not in tags or should_skip(tags):
            continue
        name = tags["name"]
        place = tags.get("addr:city") or city
        search = urllib.parse.quote_plus(f"{name} {place} {state}")
        rows.append({
            "name": name,
            "phone": phone,
            "email": tags.get("email") or tags.get("contact:email") or "",
            "facebook": tags.get("contact:facebook") or tags.get("facebook") or "",
            "type": kind(tags),
            "address": address(tags),
            "city": place,
            "check_on_google": f"https://www.google.com/search?q={search}",
        })
    return rows


def save_csv(leads):
    """Saves the file. Called after every city so nothing is lost."""
    leads.sort(key=lambda r: (not (r["email"] or r["facebook"]),
                              r["city"], r["name"].lower()))
    folder = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(folder, OUTPUT_NAME)
    columns = ["name", "phone", "email", "facebook", "type",
               "address", "city", "check_on_google"]
    try:
        f = open(path, "w", newline="", encoding="utf-8-sig")
    except PermissionError:
        stamp = datetime.now().strftime("%H%M%S")
        path = os.path.join(folder, f"leads_{stamp}.csv")
        print(f"    (leads.csv is open in Excel, saving to {os.path.basename(path)} instead)")
        f = open(path, "w", newline="", encoding="utf-8-sig")
    with f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(leads)
    return path


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------
def main():
    print("=" * 60)
    print(" LOCAL LEAD FINDER - businesses with a phone but no website")
    print("=" * 60)

    state = input(f"State or region (press Enter for {DEFAULT_STATE}): ").strip()
    raw = input("Cities, separated by commas (press Enter for the Salt Lake valley): ").strip()

    if raw:
        cities = [c.strip() for c in raw.split(",") if c.strip()]
        state = state or DEFAULT_STATE
    elif state and state.lower() != DEFAULT_STATE.lower():
        print("Please run it again and type at least one city for that state.")
        return
    else:
        cities, state = DEFAULT_CITIES, DEFAULT_STATE

    print(f"\nSearching {len(cities)} cities. This takes a few minutes.")
    print("Do not close this window. The file saves as it goes.\n")

    leads, seen, retry_list, path = [], set(), [], None

    def add(elements, city):
        added = 0
        for row in get_rows(elements, city, state):
            key = (row["name"].lower(), row["phone"])
            if key not in seen:
                seen.add(key)
                leads.append(row)
                added += 1
        return added

    for i, city in enumerate(cities, start=1):
        print(f"[{i}/{len(cities)}] {city}...")
        box = geocode(city, state)
        if not box:
            print("    Could not find this city on the map. Skipped.")
            continue

        found_any, added = False, 0
        for group in GROUPS:
            elements = run_search(make_search(city, box, group))
            if elements is None:
                print(f"    {group}: server busy, will retry later")
                retry_list.append((city, box, group))
            else:
                print(f"    {group}: done")
                found_any = found_any or bool(elements)
                added += add(elements, city)
            time.sleep(3)

        if not found_any and not any(c == city for c, _, _ in retry_list):
            print("    City outline not found, searching the map area instead...")
            for group in GROUPS:
                elements = run_search(make_search(city, box, group, box_only=True))
                if elements:
                    added += add(elements, city)
                time.sleep(3)

        print(f"    {added} new leads")
        if leads:
            path = save_csv(leads)

    if retry_list:
        print(f"\nRetrying {len(retry_list)} searches that were busy...")
        time.sleep(20)
        for city, box, group in retry_list:
            elements = run_search(make_search(city, box, group), tries=3)
            if elements:
                print(f"    {city}: {add(elements, city)} more leads")
            time.sleep(5)
        if leads:
            path = save_csv(leads)

    if not leads:
        print("\nNo leads found. Wait a few minutes and run it again.")
        return

    print("\n" + "=" * 60)
    print(f" DONE! {len(leads)} leads saved to:\n {path}")
    print(" Click the check_on_google link for each lead before calling.")
    print(" Data (c) OpenStreetMap contributors.")
    print("=" * 60)


main()
