# SiteScout

Finds local businesses that have a **phone number but no website**, using free
OpenStreetMap data. Built for web design agencies and freelancers who want a
list of businesses that may need a website. Free: no account, API key, or
credit card needed.

## What it does
- Searches the cities you choose (defaults to the Salt Lake valley, Utah)
- Looks for trades, contractors, auto shops, salons, bakeries, vets and more
- Skips big chains and non-businesses (schools, charities, government)
- Saves `leads.csv` with name, phone, email, Facebook, type, address, city, and a
  Google link to double-check each lead

## How to run
1. Install Python from https://www.python.org/downloads/
2. Download `prospecting.py`
3. Open it in IDLE (comes with Python), then click Run > Run Module
4. Type a state and cities when asked, or press Enter for the defaults
5. Wait a few minutes. Open `leads.csv` when it says DONE

## Limits (please read)
- OpenStreetMap coverage of small businesses is incomplete, so some leads will
  turn out to have a website. **Click the Google link to check each lead before
  contacting anyone.** In a quick informal spot check, about 40% of the leads
  I looked at really had no website; your results will vary.
- The free servers can be slow or busy, so a few searches may time out. The
  tool retries them and saves after every city.
- No review counts or ratings (OpenStreetMap does not have them).
- If you contact businesses, follow do-not-call and anti-spam rules (TCPA,
  CAN-SPAM).

## Credits
- Business data: (c) OpenStreetMap contributors, https://www.openstreetmap.org/copyright
- Built with the help of Claude (Anthropic), directed and tested by me.
