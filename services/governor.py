"""
Provincial Governor profile data for LTCATO public pages.
"""

from __future__ import annotations

from typing import Any

GOVERNOR: dict[str, Any] = {
    "name": "Marisol Castillo Aragones",
    "nickname": "Sol",
    "title": "Governor of Laguna",
    "term_label": "19th Governor · Province of Laguna",
    "assumed_office": "June 30, 2025",
    "party": "Independent (formerly PDP–Laban)",
    "birthplace": "San Pablo City, Laguna",
    "education": "B.S. Development Communication, University of the Philippines Los Baños (1998)",
    "portrait": "images/sol.jpg",
    "gallery": [
        {"file": "images/sol.jpg", "caption": "Official portrait at the Laguna Provincial Capitol"},
        {"file": "images/sol1.jpg", "caption": "Engaging with Laguna communities across the province"},
        {"file": "images/sol2.jpg", "caption": "Leading provincial programs for health, education, and tourism"},
    ],
    "tagline": (
        "From community broadcasting to the provincial capitol — a leader shaped by "
        "storytelling, public service, and a deep commitment to Laguna."
    ),
    "summary": (
        "Governor Sol Aragones leads the Provincial Government of Laguna with a vision rooted in "
        "accessible healthcare, quality education, sustainable tourism, and transparent governance. "
        "Her path from UP Los Baños and years in broadcast journalism to Congress and the governorship "
        "reflects a lifelong dedication to listening to communities and turning their needs into policy."
    ),
    "highlights": [
        {
            "icon": "ph-heart",
            "title": "Healthcare for all",
            "text": (
                "Expanding access to medicines, strengthening public hospitals, and bringing "
                "health services closer to barangays and municipalities."
            ),
        },
        {
            "icon": "ph-graduation-cap",
            "title": "Education & youth",
            "text": (
                "Growing scholarship programs and supporting schools so Laguna's students have "
                "pathways to skills, employment, and leadership."
            ),
        },
        {
            "icon": "ph-map-trifold",
            "title": "Tourism & livelihood",
            "text": (
                "Partnering with offices like LTCATO to promote destinations, preserve heritage, "
                "and create jobs through culture, arts, and trade."
            ),
        },
        {
            "icon": "ph-handshake",
            "title": "Good governance",
            "text": (
                "Promoting accountable, responsive provincial services — including tourism, "
                "cultural programs, and frontline transactions documented in the Citizen's Charter."
            ),
        },
    ],
    "timeline": [
        {
            "year": "1998",
            "title": "UP Los Baños graduate",
            "text": "Completed Development Communication with a focus on community broadcasting.",
        },
        {
            "year": "1999–2012",
            "title": "Broadcast journalist",
            "text": (
                "Reported for ABS-CBN on TV Patrol, Bandila, and DZMM; covered health and "
                "community stories nationwide for more than a decade."
            ),
        },
        {
            "year": "2013–2022",
            "title": "Member of Congress",
            "text": (
                "Represented Laguna's 3rd District; authored measures on teen pregnancy prevention, "
                "protection of pregnant workers, and anti-discrimination."
            ),
        },
        {
            "year": "2025",
            "title": "Governor of Laguna",
            "text": (
                "Elected on her second gubernatorial bid; assumed office June 30, 2025 as Laguna's "
                "19th governor and second woman to hold the post."
            ),
        },
    ],
    "priorities": [
        "Provincial pharmacies and free maintenance medicines for qualified residents",
        "Hospital upgrades and barangay-level health outreach",
        "Scholarships and workforce development for Laguna youth",
        "Tourism promotion, cultural preservation, and MSME support through provincial programs",
    ],
    "quote": (
        "Public office is a continuation of the work we do in the field — to hear people's stories "
        "and deliver solutions that reach every municipality and city in Laguna."
    ),
}

GOVERNOR_TEASER: dict[str, str] = {
    "eyebrow": "Provincial leadership",
    "heading": "Governor of Laguna",
    "name": GOVERNOR["name"],
    "nickname": GOVERNOR["nickname"],
    "assumed_office": GOVERNOR["assumed_office"],
    "lead": GOVERNOR["summary"][:280] + "…",
    "cta": "Read full profile",
}
