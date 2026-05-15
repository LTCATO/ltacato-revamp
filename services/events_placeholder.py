"""
Placeholder events data until the super-admin events table is connected.
Replace list_events / get_event with Supabase queries when ready.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

PLACEHOLDER_EVENTS: list[dict[str, Any]] = [
    {
        "id": 1,
        "title": "Laguna Cultural Festival",
        "category": "cultural",
        "status": "upcoming",
        "summary": "Celebrate Laguna's rich heritage through traditional music, dance, crafts, and local cuisine.",
        "description": (
            "The Laguna Cultural Festival is the province's flagship celebration of identity and creativity. "
            "Staged at the provincial capitol grounds, the event brings together municipalities to showcase "
            "folk dances, rondalla performances, woven textiles, and heirloom recipes passed down for generations.\n\n"
            "Visitors can walk through cultural pavilions, meet local artisans, and join interactive workshops "
            "on embroidery, wood carving, and traditional cooking. Evening programs feature grand street parades "
            "and a fireworks display over the town plaza."
        ),
        "image": "https://images.unsplash.com/photo-1492684223066-81342ee5ff30?auto=format&fit=crop&w=1200&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1533174072545-7a4b6ad7a6c3?auto=format&fit=crop&w=800&q=80",
        ],
        "municipality": "Sta. Cruz",
        "venue": "Laguna Provincial Capitol Grounds",
        "address": "Brgy. Bubukal, Sta. Cruz, Laguna",
        "date_month": "MAR",
        "date_day": 15,
        "date_year": 2026,
        "date_label": "March 15, 2026",
        "date_end_label": "March 17, 2026",
        "time": "9:00 AM – 6:00 PM",
        "organizer": "LTCATO · Provincial Government of Laguna",
        "admission": "Free admission · Paid workshops from ₱150",
        "contact": "events@ltcato.laguna.gov.ph · (049) 123-4567",
        "attendee_count": 127,
        "highlights": [
            "Grand cultural parade with municipal delegations",
            "Live rondalla and folk dance competitions",
            "Artisan market and heritage food fair",
            "Free guided capitol heritage tours",
        ],
        "schedule": [
            {"time": "9:00 AM", "title": "Opening ceremony & ribbon cutting"},
            {"time": "10:30 AM", "title": "Municipal pavilion tours open"},
            {"time": "2:00 PM", "title": "Folk dance showcase"},
            {"time": "6:00 PM", "title": "Evening concert & fireworks"},
        ],
    },
    {
        "id": 2,
        "title": "Laguna Food Festival",
        "category": "food",
        "status": "upcoming",
        "summary": "Taste signature dishes from Calamba and across Laguna in one vibrant weekend food fair.",
        "description": (
            "The Laguna Food Festival gathers the province's best chefs, home cooks, and food entrepreneurs "
            "for a celebration of local flavor—from kesong puti and bibingka to modern fusion stalls inspired "
            "by Rizal-era recipes.\n\n"
            "Expect cooking demos, blind tasting contests, and a night market along the lakeshore promenade. "
            "All vendors are accredited by LTCATO and local health offices."
        ),
        "image": "https://images.unsplash.com/photo-1549488344-1f9b8d2bd1f3?auto=format&fit=crop&w=1200&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1555939594-58d7cb561ad1?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=800&q=80",
        ],
        "municipality": "Calamba City",
        "venue": "Rizal Shrine Lakeside Promenade",
        "address": "J.P. Rizal St., Calamba City, Laguna",
        "date_month": "APR",
        "date_day": 22,
        "date_year": 2026,
        "date_label": "April 22, 2026",
        "date_end_label": "April 24, 2026",
        "time": "10:00 AM – 10:00 PM",
        "organizer": "LTCATO · Calamba City Tourism Office",
        "admission": "₱50 entrance · Kids under 7 free",
        "contact": "calamba.tourism@laguna.gov.ph",
        "attendee_count": 89,
        "highlights": [
            "50+ accredited food stalls",
            "Celebrity chef live cooking sessions",
            "Laguna coffee & dessert alley",
            "Family picnic zones by the lake",
        ],
        "schedule": [
            {"time": "10:00 AM", "title": "Market opens · Morning tastings"},
            {"time": "1:00 PM", "title": "Kesong puti masterclass"},
            {"time": "4:00 PM", "title": "Street food cook-off finals"},
            {"time": "8:00 PM", "title": "Night market & acoustic sets"},
        ],
    },
    {
        "id": 3,
        "title": "Eco-Tourism Adventure Weekend",
        "category": "adventure",
        "status": "upcoming",
        "summary": "Guided nature walks, waterfall tours, and conservation activities across Pagsanjan and Lumban.",
        "description": (
            "Join accredited eco-guides for a weekend of responsible adventure in Laguna's green corridors. "
            "Activities include a gentle trek to hidden cascades, bird-watching along the Pagsanjan River, "
            "and a tree-planting drive supported by local environmental youth groups.\n\n"
            "All participants receive a safety briefing and are grouped by fitness level. Leave-no-trace "
            "principles are enforced throughout the program."
        ),
        "image": "https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?auto=format&fit=crop&w=1200&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1432405972618-c60b0225b8f9?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1469474968028-56623f02e42e?auto=format&fit=crop&w=800&q=80",
        ],
        "municipality": "Pagsanjan",
        "venue": "Pagsanjan Tourism Operations Center",
        "address": "National Hwy., Pagsanjan, Laguna",
        "date_month": "MAY",
        "date_day": 8,
        "date_year": 2026,
        "date_label": "May 8, 2026",
        "date_end_label": "May 9, 2026",
        "time": "6:00 AM – 4:00 PM",
        "organizer": "LTCATO · Pagsanjan LGU",
        "admission": "Packages from ₱350 (includes guide & gear)",
        "contact": "pagsanjan.eco@laguna.gov.ph",
        "attendee_count": 156,
        "highlights": [
            "Certified eco-guides on every trail",
            "Optional shooting-the-rapids add-on",
            "Native tree planting certificate",
            "Wildlife spotting with local naturalists",
        ],
        "schedule": [
            {"time": "6:00 AM", "title": "Registration & safety briefing"},
            {"time": "7:00 AM", "title": "Forest trail group departures"},
            {"time": "12:00 PM", "title": "Riverside lunch (zero-waste)"},
            {"time": "2:00 PM", "title": "Tree planting & closing rites"},
        ],
    },
    {
        "id": 4,
        "title": "Anahaw Arts & Trade Fair",
        "category": "arts",
        "status": "upcoming",
        "summary": "A showcase of Laguna artisans, painters, and MSME products from the culture and trade sectors.",
        "description": (
            "The Anahaw Arts & Trade Fair connects Laguna's creative economy with travelers seeking authentic "
            "souvenirs and contemporary art. Booths feature hand-painted taka, resin crafts, woven bags, "
            "and certified organic products from community cooperatives.\n\n"
            "Daily talks cover branding for local makers and how to list products on official tourism channels."
        ),
        "image": "https://images.unsplash.com/photo-1460661419731-7acf35ad9851?auto=format&fit=crop&w=1200&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1515405295579-ba7b45403062?auto=format&fit=crop&w=800&q=80",
        ],
        "municipality": "San Pedro City",
        "venue": "San Pedro City Convention Center",
        "address": "National Rd., San Pedro, Laguna",
        "date_month": "JUN",
        "date_day": 12,
        "date_year": 2026,
        "date_label": "June 12, 2026",
        "date_end_label": "June 14, 2026",
        "time": "9:00 AM – 7:00 PM",
        "organizer": "LTCATO · Arts & Trade Division",
        "admission": "Free",
        "contact": "arts.trade@ltcato.laguna.gov.ph",
        "attendee_count": 64,
        "highlights": [
            "Live painting and taka demonstrations",
            "MSME product launch pavilion",
            "Meet-the-maker sessions",
            "Official LTCATO souvenir pop-up",
        ],
        "schedule": [
            {"time": "9:00 AM", "title": "Fair opens · Ribbon cutting"},
            {"time": "11:00 AM", "title": "Artists' talk: Laguna crafts today"},
            {"time": "3:00 PM", "title": "Trade clinic for cooperatives"},
            {"time": "6:00 PM", "title": "Closing auction for charity pieces"},
        ],
    },
    {
        "id": 5,
        "title": "Paete Woodcarving Festival",
        "category": "cultural",
        "status": "upcoming",
        "summary": "Honor Paete's master carvers with exhibits, workshops, and a procession of santos and folk icons.",
        "description": (
            "Paete—the carving capital of the Philippines—opens its ateliers for this annual festival. "
            "Watch master sculptors turn blocks of wood into intricate figures, join beginner chisel workshops, "
            "and explore the town's museum of religious art.\n\n"
            "The highlight is the twilight procession of newly blessed carvings through the historic streets."
        ),
        "image": "https://images.unsplash.com/photo-1452860606245-08befc4ff4db?auto=format&fit=crop&w=1200&q=80",
        "gallery": [],
        "municipality": "Paete",
        "venue": "Paete Municipal Plaza & Atelier Row",
        "address": "J.V. Quesada St., Paete, Laguna",
        "date_month": "JUL",
        "date_day": 25,
        "date_year": 2026,
        "date_label": "July 25, 2026",
        "date_end_label": "July 26, 2026",
        "time": "8:00 AM – 8:00 PM",
        "organizer": "Paete LGU · LTCATO",
        "admission": "Free · Workshop slots ₱200",
        "contact": "paete.tourism@laguna.gov.ph",
        "attendee_count": 98,
        "highlights": [
            "Open-atelier tours with master carvers",
            "Hands-on beginner woodcraft sessions",
            "Heritage church art exhibit",
            "Twilight carving procession",
        ],
        "schedule": [
            {"time": "8:00 AM", "title": "Atelier row opens"},
            {"time": "1:00 PM", "title": "Carving competition judging"},
            {"time": "5:00 PM", "title": "Museum guided tours"},
            {"time": "7:00 PM", "title": "Procession & blessing"},
        ],
    },
    {
        "id": 6,
        "title": "Lumban Embroidery & Lake Festival",
        "category": "cultural",
        "status": "upcoming",
        "summary": "Fashion shows of calado and burdang Lumban on the shores of Laguna de Bay.",
        "description": (
            "Lumban celebrates its world-famous hand embroidery with runway shows, textile exhibits, "
            "and lakeside regattas. Local designers debut contemporary pieces using traditional calado techniques.\n\n"
            "Food boats serve regional specialties while visitors browse fabric markets along the boardwalk."
        ),
        "image": "https://images.unsplash.com/photo-1558171813-4c088753af8f?auto=format&fit=crop&w=1200&q=80",
        "gallery": [],
        "municipality": "Lumban",
        "venue": "Lumban Lakeside Park",
        "address": "Lakeshore Rd., Lumban, Laguna",
        "date_month": "AUG",
        "date_day": 18,
        "date_year": 2026,
        "date_label": "August 18, 2026",
        "date_end_label": "August 19, 2026",
        "time": "3:00 PM – 9:00 PM",
        "organizer": "Lumban LGU · LTCATO",
        "admission": "Free seating · VIP pavilion ₱300",
        "contact": "lumban.events@laguna.gov.ph",
        "attendee_count": 72,
        "highlights": [
            "Calado fashion runway on the lake deck",
            "Embroidery workshop tents",
            "Sunset boat parade",
            "Local fabric market",
        ],
        "schedule": [
            {"time": "3:00 PM", "title": "Textile exhibit opens"},
            {"time": "5:00 PM", "title": "Fashion show main program"},
            {"time": "7:00 PM", "title": "Boat parade & fireworks"},
        ],
    },
]


def get_categories() -> list[str]:
    return sorted({e["category"] for e in PLACEHOLDER_EVENTS})


def get_municipalities() -> list[str]:
    return sorted({e["municipality"] for e in PLACEHOLDER_EVENTS})


def list_events(
    *,
    category: str | None = None,
    municipality: str | None = None,
    q: str | None = None,
) -> list[dict[str, Any]]:
    results = deepcopy(PLACEHOLDER_EVENTS)

    if category:
        results = [e for e in results if e["category"] == category.lower()]

    if municipality:
        results = [e for e in results if e["municipality"].lower() == municipality.lower()]

    if q:
        term = q.lower().strip()
        results = [
            e
            for e in results
            if term in e["title"].lower()
            or term in e["summary"].lower()
            or term in e["municipality"].lower()
            or term in e.get("venue", "").lower()
        ]

    return results


def get_event(event_id: int) -> dict[str, Any] | None:
    for event in PLACEHOLDER_EVENTS:
        if event["id"] == event_id:
            return deepcopy(event)
    return None


def get_related_events(event: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    related = [
        deepcopy(e)
        for e in PLACEHOLDER_EVENTS
        if e["id"] != event["id"] and e["category"] == event.get("category")
    ]
    if len(related) < limit:
        extras = [
            deepcopy(e)
            for e in PLACEHOLDER_EVENTS
            if e["id"] != event["id"] and e not in related
        ]
        related.extend(extras)
    return related[:limit]
