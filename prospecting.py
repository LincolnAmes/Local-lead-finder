import csv
import json
import os
import time
import urllib.parse
import urllib.request

# ------------------------------------------------------------
# Cities to search. Add or delete names if you want.
# ------------------------------------------------------------
CITIES = [
    "Holladay", "Murray", "Millcreek", "Cottonwood Heights", "Sandy",
    "Draper", "Midvale", "South Salt Lake", "Taylorsville", "West Jordan",
    "South Jordan", "Riverton", "Herriman", "West Valley City",
    "Salt Lake City",
]

OUTPUT_NAME = "utah_leads.csv"
VALLEY_BOX = "40.40,-112.20,40.95,-111.60"

SHOPS = ("car_repair|tyres|locksmith|laundry|dry_cleaning|hairdresser|beauty|"
         "massage|tattoo|pet_grooming|florist|bakery|photo|sewing|tailor")
AMENITIES = "car_wash|veterinary|childcare"
SKIP_OFFICES = ("government|diplomatic|ngo|political_party|religion|association|"
                "educational_institution|foundation|research|union|quango")

# Big chains are skipped.
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
]

SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]


def make_search(city):
    nosite = '[!"website"][!"contact:website"][!"url"]["name"]'
    return (
        "[out:json][timeout:120];\n"
        f'rel["name"="{city}"]["boundary"="administrative"]({VALLEY_BOX});\n'
        "map_to_area->.a;\n(\n"
        f'  nwr(area.a)["craft"]{nosite};\n'
        f'  nwr(area.a)["office"]["office"!~"^({SKIP_OFFICES})$"]{nosite};\n'
        f'  nwr(area.a)["shop"~"^({SHOPS})$"]{nosite};\n'
        f'  nwr(area.a)["amenity"~"^({AMENITIES})$"]{nosite};\n'
        ");\nout center tags;\n"
    )


def ask_server(query):
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    problem = None
    for url in SERVERS:
        try:
            req = urllib.request.Request(
                url, data=data, headers={"User-Agent": "utah-lead-finder/3.0"}
            )
            with urllib.request.urlopen(req, timeout=150) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as err:
            problem = err
            print("    Server busy, trying another...")
            time.sleep(4)
    raise RuntimeError(problem)


def is_chain(tags):
    if "brand" in tags or "brand:wikidata" in tags:
        return True
    name = tags.get("name", "").lower()
    return any(word in name for word in CHAINS)


def kind(tags):
    for key in ("craft", "shop", "office", "amenity"):
        if key in tags:
            return tags[key].replace("_", " ")
    return ""


def address(tags):
    street = " ".join(
        p for p in (tags.get("addr:housenumber"), tags.get("addr:street")) if p
    )
    parts = [street, tags.get("addr:city"), tags.get("addr:postcode")]
    return ", ".join(p for p in parts if p)


def get_rows(result, city):
    rows = []
    for el in result.get("elements", []):
        tags = el.get("tags", {})
        phone = tags.get("phone") or tags.get("contact:phone")
        if not phone or is_chain(tags):
            continue
        name = tags["name"]
        place = tags.get("addr:city") or city
        search = urllib.parse.quote_plus(f"{name} {place} Utah")
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


def main():
    leads, seen = [], set()

    for i, city in enumerate(CITIES, start=1):
        print(f"[{i}/{len(CITIES)}] Searching {city}...")
        try:
            result = ask_server(make_search(city))
        except Exception as err:
            print(f"    Skipped {city} ({err})")
            continue

        added = 0
        for row in get_rows(result, city):
            key = (row["name"].lower(), row["phone"])
            if key not in seen:
                seen.add(key)
                leads.append(row)
                added += 1
        print(f"    {added} leads")
        time.sleep(5)

    if not leads:
        print("No leads found. Wait a few minutes and run it again.")
        return

    # Leads with an email or Facebook page go first.
    leads.sort(key=lambda r: (not (r["email"] or r["facebook"]), r["city"], r["name"].lower()))

    folder = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(folder, OUTPUT_NAME)
    columns = ["name", "phone", "email", "facebook", "type", "address", "city", "check_on_google"]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(leads)

    print(f"\nDONE! {len(leads)} leads saved to:\n{path}")


main()
