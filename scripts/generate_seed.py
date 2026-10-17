#!/usr/bin/env python3
"""Procedural mock-post generator for Pulse (stdlib only, deterministic).

Writes:
  seed/raw/<topic>.jsonl        RawPost per line (see CONTRACT.md)
  seed/raw/<topic>.truth.jsonl  {id, sentiment, narrative, region_id, ocr} ground truth for mock_enrich.py

Usage: python scripts/generate_seed.py [--seed 42] [--now 2026-10-17T12:00:00Z] [--scale 1.0]
"""
import argparse
import hashlib
import json
import math
import random
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = ROOT / "seed"
DAYS = 30

# --------------------------------------------------------------------------------------
# Region flavour: author_loc variants, language, reddit community
# --------------------------------------------------------------------------------------
REGION_META = {
    "ireland": (["Dublin", "dublin 🇮🇪", "Cork, Ireland", "Galway", "Ireland", "Limerick", "Co. Meath", "Éire ☘️", "Dublin 8"], "en", "r/ireland"),
    "united-kingdom": (["London", "London, UK", "Manchester", "Leeds", "Bristol 🇬🇧", "Glasgow", "UK", "south london innit", "Birmingham"], "en", "r/unitedkingdom"),
    "netherlands": (["Amsterdam", "Zeewolde", "Nederland 🇳🇱", "Groningen", "Utrecht", "Flevoland", "NL"], "nl", "r/thenetherlands"),
    "germany": (["Berlin", "München", "Hamburg", "Frankfurt am Main", "Köln", "Germany 🇩🇪", "Leipzig"], "de", "r/de"),
    "paris": (["Paris", "Paris 11e", "Paris, France", "paname", "Île-de-France", "Montreuil"], "fr", "r/paris"),
    "sweden": (["Luleå", "Stockholm", "Sverige 🇸🇪", "Boden", "Norrbotten", "Umeå", "Sundsvall"], "sv", "r/sweden"),
    "madrid": (["Madrid", "Madrid, España", "MAD"], "es", "r/spain"),
    "warsaw": (["Warszawa", "Warsaw", "Poland"], "pl", "r/poland"),
    "istanbul": (["İstanbul", "Istanbul", "Kadıköy"], "tr", "r/Turkey"),
    "virginia-us": (["Ashburn, VA", "Loudoun County", "NoVA", "Northern Virginia", "Manassas VA", "Leesburg", "Prince William County, VA"], "en", "r/nova"),
    "new-york": (["NYC", "Brooklyn, NY", "New York", "Manhattan", "Queens 🗽", "nyc"], "en", "r/nyc"),
    "chicago": (["Chicago", "Chicago, IL", "chiraq lol", "Evanston"], "en", "r/chicago"),
    "texas-us": (["Austin, TX", "Abilene TX", "Dallas", "Houston", "Texas 🤠", "San Antonio", "ERCOT land"], "en", "r/texas"),
    "arizona-us": (["Phoenix, AZ", "Mesa", "Chandler AZ", "Tucson", "Arizona ☀️", "Goodyear, AZ"], "en", "r/arizona"),
    "los-angeles": (["Los Angeles", "LA", "Santa Monica", "Venice Beach", "Silver Lake, LA", "SoCal", "DTLA"], "en", "r/LosAngeles"),
    "toronto": (["Toronto", "Toronto, ON", "the 6ix", "Scarborough"], "en", "r/toronto"),
    "vancouver": (["Vancouver", "Vancouver BC", "East Van"], "en", "r/vancouver"),
    "mexico-city": (["CDMX", "Ciudad de México", "Mexico City", "Coyoacán"], "es", "r/mexico"),
    "bogota": (["Bogotá", "Bogota, Colombia"], "es", "r/Colombia"),
    "sao-paulo": (["São Paulo", "Sampa", "SP, Brasil 🇧🇷", "Sao Paulo"], "pt", "r/brasil"),
    "buenos-aires": (["Buenos Aires", "CABA", "BsAs"], "es", "r/argentina"),
    "santiago": (["Santiago", "Santiago de Chile", "Quilicura", "Cerrillos", "Chile 🇨🇱", "Stgo"], "es", "r/chile"),
    "lagos": (["Lagos", "Lagos, Nigeria", "Lekki", "Ikeja"], "en", "r/Nigeria"),
    "nairobi": (["Nairobi", "Nairobi, Kenya", "Westlands"], "en", "r/Kenya"),
    "cairo": (["Cairo", "القاهرة", "Giza"], "ar", "r/Egypt"),
    "cape-town": (["Cape Town", "Cape Town, SA", "Kaapstad"], "en", "r/southafrica"),
    "dubai": (["Dubai", "Dubai, UAE", "DXB"], "en", "r/dubai"),
    "mumbai": (["Mumbai", "Bombay", "Andheri, Mumbai", "Navi Mumbai"], "en", "r/mumbai"),
    "delhi": (["Delhi", "New Delhi", "Gurgaon", "Noida"], "en", "r/delhi"),
    "hyderabad": (["Hyderabad", "Hyd", "HITEC City", "Gachibowli, Hyderabad", "Telangana", "Secunderabad"], "en", "r/hyderabad"),
    "bangalore": (["Bangalore", "Bengaluru", "BLR", "Koramangala", "Whitefield, Bengaluru", "Electronic City"], "en", "r/bangalore"),
    "bangkok": (["Bangkok", "กรุงเทพ", "BKK", "Sukhumvit", "Bangkok, Thailand 🇹🇭"], "th", "r/Thailand"),
    "kuala-lumpur": (["Kuala Lumpur", "KL", "Petaling Jaya"], "ms", "r/malaysia"),
    "johor": (["Johor Bahru", "JB", "Kulai, Johor", "Johor", "Iskandar Puteri", "Sedenak"], "ms", "r/malaysia"),
    "singapore": (["Singapore", "SG", "Tampines", "Jurong West", "Punggol", "sg 🇸🇬", "Woodlands"], "en", "r/singapore"),
    "jakarta": (["Jakarta", "Jakarta Selatan", "JKT", "Bekasi", "Depok", "Indonesia 🇮🇩", "Tangerang"], "id", "r/indonesia"),
    "ho-chi-minh-city": (["Ho Chi Minh City", "Saigon", "Sài Gòn", "HCMC", "Quận 1", "Thủ Đức", "Vietnam 🇻🇳"], "vi", "r/VietNam"),
    "manila": (["Manila", "Quezon City", "Makati", "Metro Manila", "Pasig", "BGC", "Philippines 🇵🇭"], "tl", "r/Philippines"),
    "shanghai": (["Shanghai", "上海", "Pudong"], "zh", None),
    "taipei": (["Taipei", "台北", "Taipei, Taiwan"], "zh", "r/taiwan"),
    "seoul": (["Seoul", "서울", "Gangnam", "Seoul, Korea", "Mapo-gu", "Hongdae"], "ko", "r/korea"),
    "tokyo": (["Tokyo", "東京", "Shibuya", "Tokyo, Japan", "Setagaya", "Minato-ku"], "ja", "r/japanlife"),
    "sydney": (["Sydney", "Sydney, NSW", "Bondi", "Parramatta", "Sydney 🇦🇺", "Inner West"], "en", "r/sydney"),
    "auckland": (["Auckland", "Tāmaki Makaurau", "Auckland NZ"], "en", "r/newzealand"),
}
LANG_NAMES = {"nl": "Dutch", "de": "German", "fr": "French", "sv": "Swedish", "es": "Spanish", "pl": "Polish",
              "tr": "Turkish", "pt": "Portuguese", "ar": "Arabic", "th": "Thai", "ms": "Malay", "id": "Indonesian",
              "vi": "Vietnamese", "tl": "Tagalog", "zh": "Chinese", "ko": "Korean", "ja": "Japanese"}

TOPIC_SUBS = {
    "ai-datacenters": ["r/datacenter", "r/technology", "r/energy", "r/sysadmin"],
    "electric-scooters": ["r/ElectricScooters", "r/ebikes", "r/urbanplanning", "r/motorcycles"],
    "four-day-week": ["r/antiwork", "r/careerguidance", "r/WorkReform", "r/Economics"],
}

SOURCES = ["bluesky", "reddit", "youtube", "tiktok", "mastodon", "news"]
SOURCE_W = {
    "ai-datacenters": [22, 28, 9, 8, 13, 20],
    "electric-scooters": [12, 20, 16, 32, 6, 14],
    "four-day-week": [24, 30, 10, 14, 10, 12],
}

# --------------------------------------------------------------------------------------
# Narratives.  Each narrative: (label, sentiment_mean, weight, [templates], [(media_type, description, ocr|None)])
# Templates support inline alternation: {a|b|c}.
# --------------------------------------------------------------------------------------
N = lambda label, s, w, texts, media=(): {"label": label, "s": s, "w": w, "texts": texts, "media": list(media)}

STORIES = {
    "ai-datacenters": {
        "ireland": {"vol": 150, "nar": [
            N("Grid strain & blackout fears", -0.75, 5, [
                "Data centres now use {over a fifth|21%|more than 20%} of Ireland's electricity and EirGrid is {warning about winter|talking about amber alerts again}. Why are we still approving these?",
                "Another {hyperscale|AI} data centre planned for {West Dublin|Ennis|Athlone}. Meanwhile my {gran's|mam's} electricity bill is {€380|€410|through the roof}. Make it make sense.",
                "EirGrid amber alert {again|tonight}. Hard to be told to {turn off the immersion|not use the dryer} while server farms hum away 24/7.",
                "We are {literally|genuinely} building homes we can't connect to the grid because the capacity went to data centres. {Unreal.|Madness.|Shameful.}",
                "If the lights go out this winter it'll be because of {the data centres|AI server farms}, not because people boiled a kettle. {#datacentres|#EirGrid|#Ireland}",
                "Ireland is {basically|essentially} a giant battery for Big Tech now. {Grid is maxed|No spare capacity} and they want more.",
            ], [
                ("image", "Photo of a protest outside Leinster House; a woman holds a hand-painted cardboard sign reading 'HOMES NOT SERVER FARMS'.", "HOMES NOT SERVER FARMS"),
                ("image", "Screenshot of an EirGrid app showing an amber system alert with a red banner and a demand chart near its peak.", "AMBER ALERT - System margin tight"),
                ("image", "Meme: the 'This is fine' dog in a burning room labelled 'Irish grid' while a server rack labelled 'new data centre' sits next to him.", "IRISH GRID / NEW DATA CENTRE / this is fine"),
                ("video", "Drone video over a large grey windowless warehouse complex with rows of rooftop cooling units on the outskirts of Dublin at dusk.", None),
            ]),
            N("Rising energy bills", -0.6, 3, [
                "Energy bills up again and {nobody|no politician} will say the word 'data centre' out loud. {Grand so.|Typical.}",
                "Paying {€300+|more than ever} a month for electricity in a {two-bed|small flat} and we're told it's 'market conditions'. It's the data centres.",
                "My {landlord|neighbour} said the bills are up because of 'demand'. Yeah, demand from {Big Tech|AI training runs}.",
            ], [
                ("image", "Photo of a paper electricity bill on a kitchen table with the total circled in red marker: €412.67.", "Amount due €412.67"),
            ]),
            N("Jobs & investment", 0.2, 1, [
                "Hot take: the data centres {bring construction jobs|pay a lot of tax} and we just need to build more grid. Not the villain everyone thinks.",
                "The {FDI|investment} is real, the jobs are real, the problem is {we never built the grid|planning}. Don't blame the tenants.",
            ]),
        ]},
        "virginia-us": {"vol": 110, "nar": [
            N("Noise & quality of life", -0.55, 4, [
                "The hum from the {Ashburn|Loudoun|Prince William} data centers never stops. {It's 2am and I can hear it through closed windows.|Our kids can't sleep.}",
                "Bought our house {in 2015|ten years ago} next to woods. Now it's {a wall of data centers|six windowless boxes} and a constant low drone.",
                "Data Center Alley keeps growing and {nobody asked the neighbors|the county board just rubber-stamps it}. {#NoVA|#DataCenterAlley}",
                "Measured {62 dB|58 decibels} in my backyard at night. That's the data center next door. {Fun!|Great.}",
            ], [
                ("video", "Phone video at night from a suburban backyard; a constant low humming noise and floodlit grey data center buildings visible behind a fence.", None),
                ("image", "Yard sign on a suburban lawn reading 'STOP THE DIGITAL GATEWAY' in red and white.", "STOP THE DIGITAL GATEWAY"),
            ]),
            N("Power bills & transmission lines", -0.45, 3, [
                "Dominion wants {us|ratepayers} to pay for new transmission lines {for the data centers|so Big Tech can expand}. Hard no.",
                "My {electric bill|Dominion bill} is up {18%|$40 a month} and it's because of all these data centers. {Why are residents subsidizing this?|Unreal.}",
                "New {500kV|high-voltage} lines going through {our neighborhood|the battlefield area} to feed data centers. {Unbelievable.|Ridiculous.}",
            ], [
                ("image", "Map graphic from a local news story showing proposed high-voltage transmission line routes cutting across Loudoun and Prince William counties.", "Proposed 500kV routes"),
            ]),
            N("Tax revenue upside", 0.35, 1, [
                "Loudoun's data center tax revenue {pays for our schools|keeps property taxes low}. People forget that.",
                "Say what you want but the {tax base|revenue} from data centers is why {our county budget looks great|we got the new rec center}.",
            ]),
        ]},
        "arizona-us": {"vol": 80, "nar": [
            N("Water use in drought", -0.6, 5, [
                "We're in a {megadrought|historic drought} and {Phoenix|Mesa|Goodyear} is approving data centers that use {millions of gallons|a small town's worth} of water. {Make it make sense.|Wild.}",
                "Colorado River cuts AND more data centers? {Arizona can't have both.|Pick one.}",
                "My {HOA|city} tells me to xeriscape my yard while {server farms evaporate millions of gallons|data centers drink the aquifer}. {Sure.|Okay.}",
                "Every 'AI is the future' post should come with {the water bill|a gallons-per-query number}. Arizona is paying it.",
            ], [
                ("image", "Photo of Lake Mead with a pale 'bathtub ring' on canyon walls far above the low waterline.", None),
                ("image", "Protest sign at a Mesa city council meeting reading 'OUR WATER IS NOT FOR AI'.", "OUR WATER IS NOT FOR AI"),
            ]),
            N("Heat & grid load", -0.35, 2, [
                "{118°F|115 degrees} today and APS is asking us to conserve while {the new data center campus|those server farms} runs full blast.",
                "Summer peak demand plus data centers = {rolling blackouts waiting to happen|a disaster}. {#Phoenix|#AZ}",
            ]),
            N("Economic growth", 0.3, 1, [
                "Data centers are {bringing real jobs|a huge investment} to the West Valley. Water concerns are overblown if they use {closed-loop cooling|reclaimed water}.",
            ]),
        ]},
        "texas-us": {"vol": 90, "nar": [
            N("Jobs & economic boom", 0.45, 3, [
                "Abilene's {AI campus|data center build} brought {thousands of construction jobs|a lot of money} to town. {Diner's never been this busy.|Good for us.}",
                "Texas is {the place|winning} for AI infrastructure. {Cheap land, cheap power, let's go.|Business friendly as always.}",
                "My {cousin|brother} got hired as an electrician on the {data center|Stargate} site at {$45/hr|great pay}. {Not complaining.|Huge for the family.}",
            ], [
                ("image", "Aerial photo of a huge construction site in flat West Texas scrubland with cranes and steel frames of long buildings.", None),
            ]),
            N("ERCOT grid worries", -0.5, 3, [
                "{Remember Uri?|Remember February 2021?} ERCOT can't handle a cold snap and we're adding {gigawatts|massive loads} of data centers. {Cool cool cool.|What could go wrong.}",
                "ERCOT says data center demand could {double|add 30 GW} by 2030. I just want my {AC|heat} to work.",
                "Every summer ERCOT asks us to conserve. Now {crypto mines|data centers} get paid to switch off and we foot the bill.",
            ], [
                ("image", "Screenshot of the ERCOT grid conditions dashboard with a yellow 'Conservation appeal' banner.", "CONSERVATION APPEAL"),
            ]),
            N("Neutral / wait-and-see", 0.0, 1, [
                "Honestly don't know how to feel about all the data centers going up {around Austin|in DFW}. Jobs good, grid scary.",
            ]),
        ]},
        "netherlands": {"vol": 70, "nar": [
            N("Farmland & landscape loss", -0.55, 4, [
                "(translated from Dutch) Farmers are being bought out for nitrogen rules, and then {hyperscale data centres|giant server halls} get built on the same land. {Absurd.|Unbelievable.}",
                "Zeewolde all over again. {Hectares of farmland|Good agricultural land} turned into a {grey box|data warehouse} for {Meta|Big Tech}.",
                "(translated from Dutch) The Netherlands is too small for {hyperscalers|these mega data centres}. We need the land for housing and farming.",
                "{Wieringermeer|Flevoland|North Holland} used to be {tulip fields|farmland}. Now it's data centres as far as you can see.",
            ], [
                ("image", "Wide photo of flat Dutch polder fields with a row of enormous grey data center buildings on the horizon under an overcast sky.", None),
                ("image", "Tractor at a farmers' protest with an upside-down Dutch flag and a banner reading 'GEEN DATACENTERS OP BOERENLAND' (no data centres on farmland).", "GEEN DATACENTERS OP BOERENLAND"),
            ]),
            N("Grid congestion", -0.4, 2, [
                "(translated from Dutch) Small businesses wait {years|7 years} for a grid connection while data centres got theirs first. {Netcongestie|Grid congestion} is a scandal.",
                "Our {bakery|startup} can't get a heavier grid connection until {2029|2030} because of grid congestion. Thanks, data centres.",
            ]),
            N("Green power use", 0.25, 1, [
                "To be fair the new data centres here run on {offshore wind|green power contracts} and sell waste heat to {greenhouses|district heating}.",
            ]),
        ]},
        "sweden": {"vol": 60, "nar": [
            N("Clean hydro & jobs in the north", 0.55, 5, [
                "(translated from Swedish) Luleå is booming thanks to the data centres. {Clean hydropower, cold climate, good jobs.|Fossil-free power and new jobs.}",
                "Northern Sweden is {the perfect place|ideal} for AI datacenters: {100% hydro|renewable power} and free cooling {nine months a year|most of the year}.",
                "My {hometown|kommun} in Norrbotten was shrinking for decades. Now {the data centre|new investment} is bringing young people back.",
                "Waste heat from the {server halls|data centre} heats {our district|thousands of homes} in winter. {Smart.|This is how it should be done.}",
            ], [
                ("image", "Photo of a long low data center beside a river in snowy northern Sweden with a hydroelectric dam in the background.", None),
                ("video", "Short news clip interview with a young technician in a hi-vis jacket inside a bright server hall in Luleå, subtitled in English.", None),
            ]),
            N("Rising electricity prices in south", -0.3, 1, [
                "(translated from Swedish) Nice for Norrbotten but in {Skåne|the south} we pay {five times more|much more} for electricity. Who benefits?",
            ]),
        ]},
        "hyderabad": {"vol": 75, "nar": [
            N("IT jobs & investment", 0.6, 5, [
                "Hyderabad is becoming {India's data center capital|the AI infra hub of India}! {Huge investments announced|Another hyperscaler campus} in {Chandanvelly|Mekaguda}. 🚀",
                "Got placed as a {DC operations engineer|network engineer} at the new {AI data centre|campus} near Hyd. Proud moment for my family 🙏",
                "Telangana's data centre policy is {working|paying off}. {Thousands of jobs|Huge employment} for our youth.",
                "Hyderabad > Bangalore for {infra|AI data centres}. {Land, power, govt support all there.|Fight me.}",
            ], [
                ("image", "Photo of a ribbon-cutting ceremony at a new data center campus in Hyderabad with officials in front of a large banner.", "Inauguration - Hyperscale Data Centre Campus, Telangana"),
                ("video", "YouTube vlog of a young engineer touring a new data centre campus, pointing at generators and cooling towers, with upbeat music.", None),
            ]),
            N("Water & power concerns", -0.35, 1, [
                "Data centres are fine but {Hyderabad summers|our water table} can't take more {water-hungry cooling|load}. Plan properly.",
            ]),
        ]},
        "johor": {"vol": 55, "nar": [
            N("Investment boom", 0.5, 5, [
                "Johor is now {Southeast Asia's data centre hotspot|the region's AI hub}. {Kulai|Sedenak} land prices {up 3x|rocketing} 🔥",
                "(translated from Malay) The data centres in Johor are bringing {good jobs|high-paying jobs} for locals. Proud of JB!",
                "Billions in {investment|FDI} flowing into Johor data centres. {Singapore's loss is our gain.|JB finally getting its moment.}",
            ], [
                ("image", "Photo of a construction billboard in Johor showing a rendering of a modern data center park with palm trees.", "SEDENAK TECH PARK - Data Centre Hub"),
            ]),
            N("Water & power strain", -0.4, 1, [
                "(translated from Malay) Johor already has {water disruptions|water rationing}, now data centres want {millions of litres|more water}. Hope the government is careful.",
            ]),
        ]},
        "santiago": {"vol": 55, "nar": [
            N("Water scarcity", -0.6, 5, [
                "(translated from Spanish) {14 years of drought|A mega-drought} and they want to build data centres that consume {millions of litres|our water} in {Cerrillos|Quilicura}. No way.",
                "Santiago doesn't have water to spare for {Google|Big Tech}'s servers. {#AguaParaChile|#SinAguaNoHayVida}",
                "(translated from Spanish) The communities of {Quilicura|Cerrillos} are fighting {the data centre|another server farm} over the aquifer. Total support.",
            ], [
                ("image", "Protest in a Santiago street with a banner reading 'EL AGUA NO ES PARA SERVIDORES' (water is not for servers).", "EL AGUA NO ES PARA SERVIDORES"),
                ("image", "Photo of a nearly dry riverbed with cracked earth on the outskirts of Santiago.", None),
            ]),
            N("Digital hub ambitions", 0.3, 1, [
                "Chile could be {Latin America's digital hub|a cloud leader} if we use {air cooling|solar from the north}. Done right it's good.",
            ]),
        ]},
    },
    "electric-scooters": {
        "jakarta": {"vol": 150, "nar": [
            N("Cheap commuting & savings", 0.7, 5, [
                "(translated from Indonesian) Switched to an electric motorbike and I'm saving {Rp 600k|half my fuel money} a month. Best decision! 🛵⚡",
                "Electric scooter + {battery swap|SPKLU} = no more fuel queues in Jakarta. {Love it.|Never going back.}",
                "(translated from Indonesian) With the {government subsidy|Rp 7 juta subsidy} the e-motor is cheaper than a {Beat|petrol scooter}. Everyone in my kampung is switching.",
                "Jakarta traffic is still Jakarta traffic but at least {my commute is silent now|I'm not breathing petrol fumes}. E-scooter gang 🔋",
                "My {ojol|Gojek} driver says his electric bike {pays for itself|saves him so much} in a few months. Respect.",
            ], [
                ("video", "TikTok video of a rider on an electric motor scooter weaving through dense Jakarta traffic, captioned with a battery emoji and laughing reactions.", None),
                ("image", "Photo of a roadside battery-swap cabinet with glowing green slots and riders queuing on scooters.", "SWAP 2 MENIT"),
                ("image", "Meme comparing a sweaty man at a petrol station queue versus a relaxed man on an electric scooter, captioned 'Bensin vs Listrik'.", "Bensin vs Listrik"),
            ]),
            N("Cleaner air", 0.6, 2, [
                "(translated from Indonesian) Jakarta air is {so bad|AQI 180 today}. If everyone rode electric we could breathe again.",
                "Imagine Jakarta with {quiet|clean} streets. Electric scooters are {how we get there|a start}. 💚",
            ]),
            N("Charging & battery doubts", -0.2, 1, [
                "Range anxiety is real when {it floods|you're stuck in macet} for 2 hours. Need more swap stations in {Bekasi|Depok}.",
            ]),
        ]},
        "ho-chi-minh-city": {"vol": 140, "nar": [
            N("Affordable & convenient", 0.7, 5, [
                "(translated from Vietnamese) My VinFast {Evo|Feliz} costs almost nothing to charge. Saigon roads were made for e-scooters 🛵",
                "Saigon is going electric {fast|so fast}. Half my friends {switched this year|ride electric now}. ⚡🇻🇳",
                "(translated from Vietnamese) Electric scooter = no more {petrol price stress|queues at the pump}. Super happy.",
                "Grab {drivers|riders} on electric bikes are everywhere in District 1 now. {Quiet, clean, love it.|The future is here.}",
            ], [
                ("video", "Short video of a stream of scooters at a Saigon intersection, many of them electric, filmed from a café balcony.", None),
                ("image", "Photo of a smiling woman with a new electric scooter outside a showroom holding a bouquet, with a 'congratulations' banner.", "CHÚC MỪNG"),
            ]),
            N("Government push / green city", 0.55, 2, [
                "(translated from Vietnamese) The city plan to {electrify motorbike taxis|phase out petrol bikes} is great for the air.",
            ]),
            N("Charging in apartments", -0.3, 1, [
                "(translated from Vietnamese) Some {chung cư|apartment buildings} banned charging in the basement after fires elsewhere. Where do we charge?",
            ]),
        ]},
        "bangkok": {"vol": 90, "nar": [
            N("Cheaper rides & delivery", 0.45, 4, [
                "(translated from Thai) Grab and LINE MAN riders on electric bikes {save a lot|earn more} because charging is cheap.",
                "E-scooters in Bangkok {make sense|are great} for short trips but {the heat|the floods} is the real test. So far so good 👍",
                "Bangkok's {win motorcycle taxis|motosai} going electric is {the best news|so good}. Quieter sois finally.",
            ], [
                ("image", "Photo of an orange-vested motorcycle taxi driver on a new electric scooter at a soi entrance in Bangkok.", None),
            ]),
            N("Traffic & safety concerns", -0.3, 1, [
                "Delivery riders on e-scooters {on the footpath|going the wrong way} again. {Pedestrians have no space.|Dangerous.}",
            ]),
        ]},
        "manila": {"vol": 90, "nar": [
            N("E-bike convenience", 0.4, 3, [
                "E-bikes are {a lifesaver|so practical} for {Manila traffic|the daily commute}. No need for gas, {less stress|saves money}.",
                "(translated from Tagalog) Bought an e-bike for {my sari-sari store deliveries|my commute}. Good investment!",
            ]),
            N("Road bans & safety", -0.35, 2, [
                "MMDA banning e-bikes on {major roads|EDSA} is {confusing|annoying}. Where are we supposed to ride?",
                "E-trikes on {the highway|national roads} are dangerous. {Someone will get hurt.|Need proper regulation.}",
            ], [
                ("image", "Photo of an MMDA traffic enforcer stopping an e-trike on a busy Metro Manila road.", "BAWAL E-BIKE SA MAJOR ROADS"),
            ]),
        ]},
        "singapore": {"vol": 110, "nar": [
            N("Battery fire safety", -0.7, 4, [
                "Another {PMD|e-bike} battery fire in an HDB flat. {Seriously scary.|When will this stop?} 🔥",
                "My {block|neighbour} had a fire from a {non-certified|modified} e-scooter battery. Whole corridor black with soot.",
                "These {lithium batteries|PMD batteries} are ticking time bombs. Ban them from {HDB flats|homes} already.",
                "SCDF says {most|majority of} fires involving PMDs are from {non-UL2272 devices|charging overnight}. Please don't charge while sleeping.",
            ], [
                ("video", "Viral phone video from an HDB corridor showing thick black smoke pouring out of a unit after an e-scooter battery fire, with residents shouting.", None),
                ("image", "Photo of a charred, melted e-scooter frame on an HDB corridor floor with soot on the walls.", None),
                ("image", "SCDF safety poster reading 'DON'T CHARGE YOUR PMD OVERNIGHT' with an icon of a battery and flames.", "DON'T CHARGE YOUR PMD OVERNIGHT"),
            ]),
            N("Footpath conflicts", -0.4, 2, [
                "Still {see|got nearly hit by} e-scooters on footpaths even after the ban. {Enforcement where?|LTA pls.}",
                "Food delivery riders on {PABs|e-bikes} speeding through void decks. {Dangerous for old folks.|Someone will kena.}",
            ]),
            N("Useful for delivery workers", 0.3, 1, [
                "Let's not forget {delivery riders|gig workers} depend on these for their livelihood. Regulate, don't ban.",
            ]),
        ]},
        "paris": {"vol": 85, "nar": [
            N("Rental clutter & sidewalk chaos", -0.55, 5, [
                "(translated from French) Even after the trottinette ban there are {e-bikes|rental scooters} {everywhere on the sidewalks|dumped in front of my door}. Enough.",
                "Paris voted to ban rental e-scooters and {honestly|frankly} the sidewalks are {so much better|finally walkable}. Good riddance.",
                "(translated from French) A {trottinette|scooter} nearly ran over my {daughter|grandmother} on {Rue de Rivoli|the sidewalk}. These things are dangerous.",
                "{Two|Three} scooters {in the Seine|in the canal} again this morning. Paris {deserves better|is tired}.",
            ], [
                ("image", "Photo of a pile of tipped-over rental e-scooters and bikes blocking a narrow Paris sidewalk next to a café.", None),
                ("image", "Photo of an electric scooter half-submerged in the Canal Saint-Martin.", None),
                ("image", "Meme of the Eiffel Tower with a rental scooter lodged on top, captioned 'They finally parked it somewhere'.", "They finally parked it somewhere"),
            ]),
            N("Personal scooter freedom", 0.3, 1, [
                "(translated from French) I use my own {trottinette|e-scooter} to get to work, it's {faster than the Métro|perfect}. Don't punish everyone for rental chaos.",
            ]),
        ]},
        "los-angeles": {"vol": 90, "nar": [
            N("Fun & practical for short trips", 0.45, 4, [
                "E-scooters in {Santa Monica|Venice} are {honestly the best way|so much fun} to get around. Beats parking.",
                "Took a {Bird|Lime} from {DTLA|the Expo line} to work, {15 min|easy}. LA needs more of this, less cars.",
                "Got an e-scooter for my {commute|last mile} and I'm {loving it|never sitting in traffic again}. ☀️🛴",
            ], [
                ("video", "Instagram reel of a rider cruising on an e-scooter along the Venice Beach boardwalk at sunset with palm trees.", None),
            ]),
            N("Sidewalk clutter & injuries", -0.35, 2, [
                "{Scooters|Birds} blocking {the sidewalk|my wheelchair ramp} again. LA needs real rules.",
                "ER {nurse|doc} here: {so many|way too many} scooter injuries every weekend. {Wear a helmet.|Please.}",
            ]),
        ]},
    },
    "four-day-week": {
        "united-kingdom": {"vol": 150, "nar": [
            N("Wellbeing & productivity win", 0.7, 5, [
                "Six months into a four-day week at {my company|our agency} and {nobody wants to go back|productivity is actually up}. {Fridays off are life changing.|Best policy ever.}",
                "The UK 4-day-week {trial|pilot} results are in: {less burnout|happier staff}, same output. {Every company should do this.|Why aren't we all doing this?}",
                "Three-day weekends {every week|every week!!} have fixed my mental health more than {anything|years of therapy}. #4DayWeek",
                "My {council|NHS trust|firm} is trialling a 4 day week and staff {sickness has dropped|retention is way up}. {Brilliant.|Get in.}",
            ], [
                ("image", "Smiling office team photo holding a banner reading '4 DAY WEEK - 1 YEAR ON' in a London office.", "4 DAY WEEK - 1 YEAR ON"),
                ("image", "Meme of a man relaxing in a garden chair with tea on a Friday, captioned 'Me at 10am on a Friday under the 4-day week'.", "Me at 10am on a Friday under the 4-day week"),
            ]),
            N("Recruitment & retention edge", 0.5, 2, [
                "We put '4-day week' in our job ads and {applications tripled|got 4x more applicants}. Small business owner, highly recommend.",
            ]),
            N("Doesn't work for all sectors", -0.3, 1, [
                "Lovely for office workers but {retail|care workers|nurses} can't just stop on a Friday. {Who covers?|Not realistic for us.}",
            ]),
        ]},
        "germany": {"vol": 100, "nar": [
            N("Pilot success & work-life balance", 0.55, 4, [
                "(translated from German) Our company took part in the {4-day week pilot|Vier-Tage-Woche study} and {most firms are keeping it|it was a success}. Great!",
                "German {pilot|study} shows the 4-day week {reduces stress|improves health} without hurting output. {Sehr gut.|Love it.}",
                "(translated from German) With the {skills shortage|Fachkräftemangel}, a four-day week is the only way to attract {young people|talent}.",
            ], [
                ("image", "Chart from a German news article showing employee stress falling and productivity flat across pilot companies.", "Vier-Tage-Woche: Stress -, Produktivität ="),
            ]),
            N("Economic competitiveness worries", -0.35, 2, [
                "(translated from German) With {the economy in recession|weak growth} we can't afford to work less. {Industry warns.|Unrealistic.}",
            ]),
        ]},
        "new-york": {"vol": 100, "nar": [
            N("Burnout relief", 0.5, 4, [
                "My {startup|team} in NYC went to a 4-day week and {I finally have a life|burnout is way down}. {Not going back.|10/10.}",
                "4-day week {is the only perk|matters more than} that would make me {switch jobs|leave finance} at this point.",
                "{NYC|Manhattan} rents are insane but a 4-day week {makes it bearable|lets me actually enjoy the city}. #4DayWorkWeek",
            ], [
                ("video", "TikTok 'day in my life' of a New Yorker on her Friday off: coffee, Central Park, a museum, with caption 'my 4-day week Friday'.", None),
            ]),
            N("Hustle culture skepticism", -0.25, 1, [
                "In {this economy|NYC}? Good luck. My {boss|firm} would just {cram five days into four|cut my pay}.",
            ]),
        ]},
        "tokyo": {"vol": 80, "nar": [
            N("Government push & childcare", 0.35, 2, [
                "(translated from Japanese) Tokyo Metropolitan Government's 4-day week for staff {to support parents|for childcare} is {a good start|great}.",
                "Tokyo's 4-day week {could help|might fix} the birth rate? {Maybe.|Worth trying.}",
            ], [
                ("image", "News graphic of Tokyo Metropolitan Government building with headline text about a four-day work week for city employees.", "都庁 週休3日"),
            ]),
            N("Culture won't change", -0.35, 2, [
                "(translated from Japanese) A four-day week is {meaningless|pointless} if {unpaid overtime|zangyo} stays the same. {Nothing will change.|Same as always.}",
                "In {Japanese companies|my company} you'd just {work 4 longer days|feel guilty taking Friday off}. Culture first.",
            ]),
        ]},
        "sydney": {"vol": 85, "nar": [
            N("Lifestyle & productivity", 0.55, 4, [
                "Four-day week + Sydney summer = {beach Fridays|absolute bliss} 🏖️ Our {firm|team} isn't going back.",
                "Productivity at our {Sydney office|company} {went up|stayed the same} on the 4-day week. {Everyone's happier.|Just do it.}",
                "{Unions|ACTU} pushing for a 4-day week and {honestly|mate} I'm all for it.",
            ], [
                ("image", "Photo of friends surfing at Bondi Beach on a weekday morning, captioned 'Friday off hits different'.", "Friday off hits different"),
            ]),
            N("Small business pushback", -0.3, 1, [
                "Small business owner: a 4-day week {on 5 days pay|mandate} would {kill us|be unaffordable}. Not everyone's a big corporate.",
            ]),
        ]},
        "bangalore": {"vol": 95, "nar": [
            N("Longer days instead", -0.45, 4, [
                "4-day week in {Indian IT|Bangalore} just means {12-hour days|70-hour weeks squeezed into 4}. No thanks. 😩",
                "Our {company|manager} 'offered' a 4-day week with {12 hours a day|longer shifts}. That's not a 4-day week, that's {burnout|exploitation}.",
                "Bangalore traffic + {10-12 hr days|longer days} = {zero life|no time to sleep}. 4-day week won't fix that.",
                "Labour code allows {12-hour shifts|4 days of 12 hours}? {In Bengaluru traffic?|With our commutes?} Absolutely not.",
            ], [
                ("image", "Meme of an exhausted cartoon developer at a desk at night, captioned '4-day week they said... 12 hours a day they meant'.", "4-day week they said... 12 hours a day they meant"),
                ("image", "Photo of bumper-to-bumper traffic on Silk Board junction at night with red tail lights.", None),
            ]),
            N("Would love real 4-day week", 0.4, 2, [
                "A {real|proper} 4-day week {without longer hours|at 40 hours total} would be amazing for {Bangalore techies|us}. Startups should try.",
            ]),
        ]},
        "seoul": {"vol": 85, "nar": [
            N("Work-life balance hopes", 0.45, 3, [
                "(translated from Korean) A 4.5-day week {pilot|policy} for {public servants|companies} — finally! Korea works too much.",
                "Korea {has some of the longest working hours|works too much}. A 4-day week {would be a dream|is long overdue} 🙏",
            ], [
                ("image", "Korean news screenshot showing a graphic of a calendar with Friday afternoon crossed out and the headline about a 4.5-day work week.", "주 4.5일제"),
            ]),
            N("Pay cut & competitiveness fears", -0.3, 2, [
                "(translated from Korean) If it means {a pay cut|lower salary} then no. {Living costs in Seoul are too high.|Cannot afford.}",
            ]),
        ]},
    },
}

# Generic narratives for filler regions: (label, s, w, texts, media). {city} gets substituted.
GENERIC = {
    "ai-datacenters": [
        N("Energy & climate concern", -0.35, 3, [
            "Every new AI data center {near {city}|in our region} means more {gas plants|emissions}. {Not worth it.|Who decided this?}",
            "How much {power|water} does a ChatGPT query use? Asking because {{city}|my city} just approved {a data centre|another server farm}.",
            "AI data centres are {draining the grid|a climate problem} and nobody in {{city}|government} is talking about it.",
        ], [("image", "Infographic comparing the electricity use of a hyperscale data center to a mid-sized city.", "1 data center = 80,000 homes")]),
        N("Economic opportunity", 0.4, 3, [
            "{{city}|Our city} should be competing for AI data centres. {Jobs, tax, investment.|We need the investment.}",
            "Great news: a new {cloud region|data centre} {is coming to {city}|announced for {city}}. {Faster services, more jobs.|Let's go!}",
            "{Tech jobs|Investment} from data centres could put {{city}|us} on the map.",
        ], [("image", "Press photo of executives shaking hands in front of a slide reading 'New Cloud Region' with a city skyline.", "NEW CLOUD REGION")]),
        N("Curious / neutral", 0.05, 2, [
            "Didn't realise {{city}|we} had so many data centres. {Interesting thread.|TIL.}",
            "Anyone know how much power the new data centre {near {city}|here} will use?",
        ]),
    ],
    "electric-scooters": [
        N("Practical & green commuting", 0.4, 3, [
            "Bought an e-scooter for my commute in {city}. {Saves time and money.|Loving it so far.} ⚡",
            "{{city}|Our city} needs more bike lanes so e-scooters can {be safe|actually work}.",
            "E-scooters are {perfect|great} for the last mile in {city}. {Wish I'd done it sooner.|10/10.}",
        ], [("video", "Short POV video of a rider on an electric scooter in a city bike lane on a sunny morning.", None)]),
        N("Safety & clutter", -0.4, 3, [
            "E-scooters {on the pavement|everywhere} in {city} again. {Someone will get hurt.|Ban them.}",
            "Nearly got {hit|clipped} by an e-scooter in {city} today. {No lights, no helmet.|Doing 30 on the sidewalk.}",
        ], [("image", "Photo of rental e-scooters scattered across a sidewalk in front of a shop entrance.", None)]),
        N("Neutral / policy news", 0.0, 2, [
            "{City council|{city} authorities} {considering|debating} new e-scooter {rules|permits}. Thoughts?",
        ]),
    ],
    "four-day-week": [
        N("Work-life balance appeal", 0.5, 3, [
            "Would {absolutely|happily} take a 4-day week {over a raise|tomorrow}. Anyone in {city} doing it?",
            "A company in {city} just moved to a 4-day week and {staff love it|productivity is up}. More of this please.",
            "The 4-day week is {the future|inevitable}. {{city}|Our employers} should catch up.",
        ], [("image", "Meme of a calendar with Friday circled and labelled 'weekend now', with a cheering crowd.", "FRIDAY = WEEKEND NOW")]),
        N("Economic skepticism", -0.3, 2, [
            "4-day week sounds nice but {in this economy|with these wages} in {city}? {Not happening.|Employers won't pay.}",
            "Who covers the {fifth day|work}? Customers in {city} won't wait.",
        ]),
        N("Curious / neutral", 0.05, 2, [
            "Has anyone in {city} actually worked a 4-day week? {How did it go?|Genuinely curious.}",
        ]),
    ],
}

FILLER_VOL = {  # baseline volume weight for filler regions (bigger cities get more)
    "united-kingdom": 45, "germany": 35, "new-york": 45, "los-angeles": 35, "toronto": 30, "mexico-city": 30,
    "sao-paulo": 35, "lagos": 25, "mumbai": 35, "delhi": 30, "manila": 25, "seoul": 30, "tokyo": 30,
    "sydney": 25, "paris": 30, "madrid": 20, "warsaw": 15, "istanbul": 18, "chicago": 22, "vancouver": 15,
    "bogota": 15, "buenos-aires": 18, "nairobi": 15, "cairo": 15, "cape-town": 14, "dubai": 20,
    "bangalore": 30, "hyderabad": 18, "bangkok": 20, "kuala-lumpur": 18, "singapore": 25, "jakarta": 25,
    "ho-chi-minh-city": 15, "shanghai": 20, "taipei": 15, "auckland": 10, "texas-us": 20, "arizona-us": 12,
    "virginia-us": 12, "ireland": 15, "netherlands": 18, "sweden": 12, "johor": 8, "santiago": 14,
}

TOPIC_CODE = {"ai-datacenters": "aid", "electric-scooters": "esc", "four-day-week": "fdw"}
PREFIXES = ["", "", "", "", "Honestly, ", "Ok so ", "PSA: ", "Thread: ", "Unpopular opinion: ", "Lol ", "Wow. "]
SUFFIXES = ["", "", "", "", " 🙄", " 😤", " 👀", " 🔥", " 💯", " lol", " tbh", " Thoughts?", " Thread 🧵"]
POS_SUFFIX = ["", "", " 🙌", " ❤️", " 🚀", " 👏"]
NEG_SUFFIX = ["", "", " 😡", " 🤦", " 😩", " smh"]
NEWS_OUTLETS = ["news.example.com", "dailywire.example.org", "globalpost.example.net", "localnews.example.com", "techdesk.example.io"]
HANDLES = ["sky", "wave", "fox", "byte", "moss", "river", "nova", "pixel", "luna", "atlas", "echo", "kite", "sage", "orbit", "fern"]

# --------------------------------------------------------------------------------------
# Time dynamics: returns (volume multiplier, sentiment shift, narrative weight boost dict)
# --------------------------------------------------------------------------------------

def dynamics(topic, region, days_ago):
    vol, shift = 1.0, 0.0
    if topic == "ai-datacenters" and region == "ireland" and days_ago < 10:
        k = (10 - days_ago) / 10.0          # 0..1 ramps towards today
        vol, shift = 1.0 + 1.4 * k, -0.25 * k
    if topic == "electric-scooters" and region == "singapore":
        d = days_ago - 13
        if -1 <= d <= 2:                      # viral fire ~13 days ago, aftershock for ~2 days
            vol, shift = 4.0 - abs(d) * 0.8, -0.35
        elif -4 <= d < -1:
            vol, shift = 1.4, -0.12
        elif d > 2:
            shift = 0.15                      # milder before the fire
    if topic == "electric-scooters" and region == "jakarta" and days_ago < 7:
        vol = 1.3
    return vol, shift


ALT_RE = re.compile(r"\{([^{}]*)\}")


def expand(tpl, rng, city):
    s = tpl.replace("{city}", city)
    # Resolve innermost alternations repeatedly
    for _ in range(6):
        new = ALT_RE.sub(lambda m: rng.choice(m.group(1).split("|")), s)
        if new == s:
            break
        s = new
    return s


def weighted(rng, items, weights):
    return rng.choices(items, weights=weights, k=1)[0]


def short_id(*parts, n=10):
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:n]


def build_region_plan(topic, regions):
    """region_id -> {'vol': weight, 'nar': [...]}"""
    names = {r["id"]: r["name"] for r in regions}
    plan = {}
    stories = STORIES[topic]
    for rid in names:
        if rid in stories:
            plan[rid] = {"vol": stories[rid]["vol"], "nar": stories[rid]["nar"], "story": True}
        else:
            plan[rid] = {"vol": FILLER_VOL.get(rid, 12), "nar": GENERIC[topic], "story": False}
    return plan, names


def make_post(rng, topic, rid, rname, nar, ts, idx):
    locs, lang, sub = REGION_META[rid]
    text = expand(rng.choice(nar["texts"]), rng, rname)
    translated = text.startswith("(translated from")
    if not translated and lang != "en" and rng.random() < 0.15:
        text = f"(translated from {LANG_NAMES.get(lang, lang)}) " + text
        translated = True
    if not translated:
        pre = rng.choice(PREFIXES)
        if pre and text[:1].isupper() and not text[:2].isupper():
            text = text[0].lower() + text[1:]
        text = pre + text
    s_mean = nar["s"]
    if s_mean > 0.3:
        text += rng.choice(POS_SUFFIX)
    elif s_mean < -0.3:
        text += rng.choice(NEG_SUFFIX)
    else:
        text += rng.choice(SUFFIXES)
    text = text.strip()
    post_lang = lang if (translated or lang == "en") else ("en" if rng.random() < 0.8 else lang)
    if translated:
        post_lang = lang

    source = weighted(rng, SOURCES, SOURCE_W[topic])
    community = None
    if source == "reddit":
        community = sub if (sub and rng.random() < 0.7) else rng.choice(TOPIC_SUBS[topic])
    elif source == "mastodon":
        community = rng.choice(["mastodon.social", "mas.to", "fosstodon.org", "mstdn.social"])

    # author location: messy
    r = rng.random()
    if r < 0.22:
        author_loc = None
    else:
        author_loc = rng.choice(locs)
        if rng.random() < 0.12:
            author_loc = author_loc.lower()
        if rng.random() < 0.06:
            author_loc = author_loc + " | " + rng.choice(["she/her", "he/him", "views my own", "🌍", "tech + coffee"])
    if source == "news" and rng.random() < 0.5:
        author_loc = None

    media, ocr = [], None
    if nar["media"] and rng.random() < 0.24:
        mtype, desc, mocr = rng.choice(nar["media"])
        if source in ("tiktok", "youtube") and mtype == "image" and rng.random() < 0.6:
            mtype = "video"
            desc = "Video slideshow: " + desc[0].lower() + desc[1:]
        media.append({"type": mtype, "description": desc, "url": None})
        ocr = mocr
    elif source in ("tiktok", "youtube") and rng.random() < 0.35:
        # these sources are always video
        media.append({"type": "video", "description": f"Talking-head video of a creator in {rname} discussing {topic.replace('-', ' ')}; on-screen caption repeats the post text.", "url": None})

    pid = f"{TOPIC_CODE[topic]}-{short_id(topic, rid, idx)}"
    handle = rng.choice(HANDLES) + str(rng.randint(10, 9999))
    if source == "bluesky":
        url = f"https://bsky.app/profile/{handle}.bsky.social/post/{short_id(pid, 'b', n=13)}"
    elif source == "reddit":
        c = community if community and community.startswith("r/") else "r/all"
        url = f"https://www.reddit.com/{c}/comments/{short_id(pid, 'r', n=7)}/"
    elif source == "youtube":
        url = f"https://www.youtube.com/watch?v={short_id(pid, 'y', n=11)}"
    elif source == "tiktok":
        url = f"https://www.tiktok.com/@{handle}/video/{int(short_id(pid, 't', n=12), 16)}"
    elif source == "mastodon":
        url = f"https://{community}/@{handle}/{int(short_id(pid, 'm', n=10), 16)}"
    else:
        url = f"https://{rng.choice(NEWS_OUTLETS)}/{rid}/{topic}/{short_id(pid, 'n', n=8)}"

    base = {"news": 120, "tiktok": 900, "youtube": 400, "reddit": 150, "bluesky": 40, "mastodon": 15}[source]
    engagement = int(rng.lognormvariate(math.log(base), 1.1))
    if media:
        engagement = int(engagement * 1.6)

    post = {
        "id": pid, "topic": topic, "source": source, "community": community, "author_loc": author_loc,
        "lang": post_lang, "text": text, "media": media, "ts": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "url": url, "engagement": engagement,
    }
    return post, ocr


def generate_topic(topic, regions, now, rng, scale):
    plan, names = build_region_plan(topic, regions)
    posts, truths = [], []
    idx = 0
    for rid, cfg in plan.items():
        rname = names[rid]
        # base posts per day for this region; total ~ topic target
        per_day = cfg["vol"] * scale / DAYS * 0.5
        for days_ago in range(DAYS):
            vmul, shift = dynamics(topic, rid, days_ago)
            lam = per_day * vmul * (0.8 + 0.4 * rng.random())
            n = int(lam) + (1 if rng.random() < lam - int(lam) else 0)
            for _ in range(n):
                nar_list = cfg["nar"]
                w = [x["w"] for x in nar_list]
                if shift < 0:  # tilt towards negative narratives
                    w = [x["w"] * (1 + (-shift) * 4 if x["s"] < 0 else 1) for x in nar_list]
                nar = weighted(rng, nar_list, w)
                ts = now - timedelta(days=days_ago, seconds=rng.randint(0, 86399))
                post, ocr = make_post(rng, topic, rid, rname, nar, ts, idx)
                idx += 1
                s = max(-1.0, min(1.0, nar["s"] + shift + rng.gauss(0, 0.17)))
                posts.append(post)
                truths.append({"id": post["id"], "sentiment": round(s, 3), "narrative": nar["label"],
                               "region_id": rid, "ocr": ocr})
    order = sorted(range(len(posts)), key=lambda i: posts[i]["ts"])
    return [posts[i] for i in order], [truths[i] for i in order]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--now", default="2026-10-17T12:00:00Z")
    ap.add_argument("--scale", type=float, default=1.0)
    args = ap.parse_args()
    now = datetime.strptime(args.now, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    regions = json.loads((SEED_DIR / "regions.json").read_text())
    missing = [r["id"] for r in regions if r["id"] not in REGION_META]
    assert not missing, f"REGION_META missing {missing}"
    topics = json.loads((SEED_DIR / "topics.json").read_text())
    out = SEED_DIR / "raw"
    out.mkdir(parents=True, exist_ok=True)
    for t in topics:
        tid = t["id"]
        rng = random.Random(f"{args.seed}-{tid}")
        posts, truths = generate_topic(tid, regions, now, rng, args.scale)
        with open(out / f"{tid}.jsonl", "w", encoding="utf-8") as f:
            for p in posts:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
        with open(out / f"{tid}.truth.jsonl", "w", encoding="utf-8") as f:
            for tr in truths:
                f.write(json.dumps(tr, ensure_ascii=False) + "\n")
        n_media = sum(1 for p in posts if p["media"])
        print(f"{tid}: {len(posts)} posts ({n_media} with media, {n_media / len(posts):.0%})")


if __name__ == "__main__":
    main()
