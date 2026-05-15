"""
Citizen Charter data for LTCATO About page.
Source: LTCATO Administrative / External Services charter.
"""

from __future__ import annotations

from typing import Any

CHARTER_SECTIONS: list[dict[str, Any]] = [
    {
        "id": "external",
        "title": "External Services",
        "subtitle": "Frontline services for LGUs, businesses, government agencies, and the public.",
        "services": [
            {
                "number": 1,
                "title": "Courtesy Call of Local and Foreign Visitors",
                "description": (
                    "This service aims to promote mutual understanding and cooperation "
                    "which will benefit both parties."
                ),
                "office": "LTCATO",
                "classification": "Simple",
                "transaction_type": "G2C, G2G, G2B",
                "who_may_avail": "All (LGUs, Private and Business Entity)",
                "requirements": [{"name": "Letter of Request", "where": "—"}],
                "steps": [
                    {
                        "client": "Submit letter of Intent (LOI) addressed to the Governor thru the LTCATO Department Head thru email (ltcato@laguna.gov.ph)",
                        "agency": "The receiving officer will get the details of the request & forward it to the division head for further action",
                        "fees": "None",
                        "time": "20 minutes",
                        "person": "Jennifer Barairo — Administrative Assistant IV; Raviel Aivan J. Litan — Administrative Aide I",
                    },
                    {
                        "client": "Prepare and submit letter to the GO-Executive describing details of the LOI, and any request of visiting party and inform the Clients to follow-up within 5 days",
                        "agency": "Forward to the Dept. Head for approval",
                        "fees": "None",
                        "time": "5 minutes",
                        "person": "—",
                    },
                    {
                        "client": "Welcome Party/Meeting",
                        "agency": "Coordinate with the GO-Executive as to the time and venue of the courtesy call; assign personnel to assist in welcoming the visiting party",
                        "fees": "None",
                        "time": "1 day",
                        "person": "Ma. Soledad E. Lagasca — Senior Tourism Operations Officer; Edgardo B. Victorio — OIC",
                    },
                ],
                "total_fees": "None",
                "total_time": "1 day and 25 minutes",
            },
            {
                "number": 2,
                "title": "Processing of Request for Conduct of Seminars and Trainings",
                "description": (
                    "The office recognizes the need to professionalize tourism industry workers / LGU tourism "
                    "front liners and improve accommodation facilities and tourist support services to sustain "
                    "the development of our province's tourism industry. The letter of request shall be submitted "
                    "to the office through electronic mail (E-mail) as well as the response to the request. "
                    "The seminar/training may be conducted through webinar zoom."
                ),
                "office": "LTCATO – Tourism Division (Planning, Development and Tourism Standards Unit & Promotions, Marketing and Creative Unit)",
                "classification": "Simple",
                "transaction_type": "G2C, G2B, G2G",
                "who_may_avail": "LGUs, Primary and Secondary Enterprises",
                "requirements": [{"name": "Letter of Request", "where": "—"}],
                "steps": [
                    {
                        "client": "Submit letter of request addressed to LTCATO Department Head through E-mail",
                        "agency": "Receive the letter of request and give to the department head for approval through the Tourism Division Head",
                        "fees": "None",
                        "time": "20 minutes",
                        "person": "Raviel Aivan J. Litan — Administrative Aide I",
                    },
                    {
                        "client": "Inform the client to follow-up after 5 days",
                        "agency": "Send reply to the client through email",
                        "fees": "None",
                        "time": "5 minutes",
                        "person": "—",
                    },
                    {
                        "client": "Wait for approval of the training/seminar",
                        "agency": "Let the Department Head approve the letter of request through the Tourism Division Head. Once approved, inform the client regarding the approval of the request",
                        "fees": "None",
                        "time": "1 day",
                        "person": "Edgardo B. Victorio — OIC",
                    },
                ],
                "total_fees": "None",
                "total_time": "1 day and 25 minutes",
            },
            {
                "number": 3,
                "title": "Processing of Request for the Submission of Tourism Data and Release of Directory of LGUs and Laguna Tourism Council (LTC)",
                "description": (
                    "The office recognizes the need to generate data on tourists/visitors arrival as reference "
                    "to gauge or measure the performance of tourism in Laguna (i.e., effectiveness of the tourism "
                    "promotion and development programs and activities being implemented). It is also important to "
                    "release copy of Directory of LGUs and LTC considering the present pandemic crisis, everything "
                    "relies on the electronic mail, social media and calls."
                ),
                "office": "LTCATO – Tourism Division (Planning, Development and Tourism Standards Unit & Promotions, Marketing and Creative Unit)",
                "classification": "Simple",
                "transaction_type": "G2B, G2G",
                "who_may_avail": "LGUs, Department of Tourism, Tourism Council and Association of Tourism Officers of the Philippines (ATOP)",
                "requirements": [{"name": "Letter of Request", "where": "—"}],
                "steps": [
                    {
                        "client": "Submit letter of request addressed to LTCATO Department Head through E-mail",
                        "agency": "Receive the letter of request and give to the department head for approval through the Tourism Division Head",
                        "fees": "None",
                        "time": "20 minutes",
                        "person": "Raviel Aivan J. Litan — Administrative Aide I",
                    },
                    {
                        "client": "Acknowledge the receipt of the letter from the client",
                        "agency": "Send reply to the client through email",
                        "fees": "None",
                        "time": "5 minutes",
                        "person": "—",
                    },
                    {
                        "client": "Wait for approval of the request",
                        "agency": "Let the Department Head approve the letter of request through the Tourism Division Head. Once approved, inform the client regarding the approval of the request",
                        "fees": "None",
                        "time": "5 minutes",
                        "person": "—",
                    },
                    {
                        "client": "Submission of the Tourism Data / Release of Directory of LGUs and LTC through Email or Messenger",
                        "agency": "Submit Tourism Data of LGUs and LTC through Email and Messenger",
                        "fees": "None",
                        "time": "5 minutes",
                        "person": "—",
                    },
                ],
                "total_fees": "None",
                "total_time": "35 minutes",
            },
            {
                "number": 4,
                "title": "Identification, Classification and Recognition of Historic Sites & Structures, Unique Cultural Traditions, Eminent Persons and Historical Events in Laguna",
                "description": (
                    "It is the duty of the Provincial Government of Laguna to deepen appreciation, promotion and "
                    "popularization of the heritage of the province, and prioritize its preservation and conservation. "
                    "The Covid-19 pandemic crisis has severely delimited the ocular inspection process, but electronic "
                    "social media offers a safer, faster and more creative communication approach in delivering needed "
                    "public services. Physical inspection is still needed, although minimized and in strict accordance "
                    "with the health protocol prescribed by the state."
                ),
                "office": "LTCATO – History, Arts and Culture Division",
                "classification": "Simple (1–3 Research Topics) · Complex (4–7) · Highly Technical (8+)",
                "transaction_type": "G2C, G2B, G2G",
                "who_may_avail": "LGUs, artists, cultural workers, the academe, students, government agencies",
                "requirements": [{"name": "Letter of request, e-mail, text messages", "where": "—"}],
                "steps": [
                    {
                        "client": "Transmit/submit Letter of request/query to LTCATO through e-mail or text message (ltcato@laguna.gov.ph)",
                        "agency": "Accept and download the letter of request/query and send an acknowledgement. The request/query is discussed and researched by the concerned individuals. Response is finalized through proper and official channel. If the requested file is too big, client may be requested to visit the office with their own CD or USB.",
                        "fees": "None",
                        "time": "3 working days (simple) / 7 working days (complex) / 20 working days (highly technical)",
                        "person": "Raviel Aivan J. Litan; Arnold L. Saavedra; Mariell V. Mercolisa; Ana Maria T. Tamban; Peter Jaynul V. Uckung — Division Head, HAC",
                    },
                ],
                "total_fees": "None",
                "total_time": "3 days, 3 mins (simple) · 7 days, 3 mins (complex) · 20 days, 3 mins (highly technical)",
            },
            {
                "number": 5,
                "title": "Trainings, Programs and Assistance for the Development of Local Talents, Artists and Cultural Workers",
                "description": (
                    "The Provincial Government of Laguna will support to the greatest extent possible, the local talents, "
                    "artists and cultural workers in their endeavor to professionalize their crafts and skills, and encourage "
                    "a deeper appreciation of the cultural traditions and uniqueness of Laguna's heritage. Electronic media "
                    "is utilized for seminars when personal gatherings are limited."
                ),
                "office": "LTCATO – History, Arts and Culture Division",
                "classification": "Simple",
                "transaction_type": "G2C, G2B, G2G",
                "who_may_avail": "LGUs, artists, cultural workers, the academe, students, government agencies",
                "requirements": [{"name": "Letter of request, e-mail, text messages", "where": "—"}],
                "steps": [
                    {
                        "client": "Transmit/submit Letter of request/query to LTCATO through e-mail or text message (ltcato@laguna.gov.ph)",
                        "agency": "Accept and download the letter of request/query and send an acknowledgement. The request/query is discussed and researched; response is finalized through proper channel with networking with government and public cultural agencies.",
                        "fees": "None",
                        "time": "3 working days (simple)",
                        "person": "Raviel Aivan J. Litan; Arnold L. Saavedra; Mariell V. Mercolisa; Ana Maria T. Tamban; Peter Jaynul V. Uckung — Division Head, HAC",
                    },
                ],
                "total_fees": "None",
                "total_time": "3 days, 3 minutes",
            },
            {
                "number": 6,
                "title": "Request for Information on Culture, Arts and Heritage",
                "description": (
                    "The Provincial Government of Laguna commits itself to intensifying interest among our constituents "
                    "on varied topics related to Laguna's heritage. Historical and cultural data will be disseminated "
                    "through electronic media with a faster pace and wider audience to strengthen nationalism, love of "
                    "country, respect for our heroes and pride in our people's achievements."
                ),
                "office": "LTCATO – History, Arts and Culture Division",
                "classification": "Simple (1–3 Research Topics)",
                "transaction_type": "G2C, G2B, G2G",
                "who_may_avail": "LGUs, artists, cultural workers, the academe, students, government agencies",
                "requirements": [{"name": "Letter of request, e-mail, text messages", "where": "—"}],
                "steps": [
                    {
                        "client": "Transmit/submit Letter of request/query to LTCATO through e-mail or text message (ltcato@laguna.gov.ph)",
                        "agency": "Accept and download the letter of request/query and send an acknowledgement. The request/query is discussed and researched; response is finalized through proper channel according to the nature of the subject.",
                        "fees": "None",
                        "time": "3 working days (simple)",
                        "person": "Raviel Aivan J. Litan; Arnold L. Saavedra; Mariell V. Mercolisa; Ana Maria T. Tamban; Peter Jaynul V. Uckung — Division Head, HAC",
                    },
                ],
                "total_fees": "None",
                "total_time": "3 days & 3 minutes",
            },
            {
                "number": 7,
                "title": "Request of Materials for Virtual Tour",
                "description": (
                    "The Office recognizes the importance of promoting and marketing tourism products and services "
                    "to create awareness, appreciation, interest and patronage of Laguna's tourist attractions and "
                    "destinations. It is the duty of the Provincial Government of Laguna to deepen appreciation, "
                    "promote and popularize the tourism of the province through electronic social media."
                ),
                "office": "LTCATO – Tourism Division (Planning, Development and Tourism Standards Unit & Promotions, Marketing and Creative Unit)",
                "classification": "Simple",
                "transaction_type": "G2C, G2G, G2B",
                "who_may_avail": "Government Agencies, Private Companies, Students, Academe, Tourists, Tourism Officers",
                "requirements": [
                    {
                        "name": "Scanned Government Issued ID, School ID, Company, BIR, GSIS, SSS, etc.",
                        "where": "SSS, BIR, GSIS, Company, School, etc.",
                    }
                ],
                "steps": [
                    {
                        "client": "Submit letter of Request addressed to LTCATO Department Head thru email (ltcato@laguna.gov.ph)",
                        "agency": "Receive and download the letter of request and send acknowledgement receipt",
                        "fees": "None",
                        "time": "20 minutes",
                        "person": "Raviel Aivan J. Litan — Administrative Aide I",
                    },
                    {
                        "client": "Wait for Approval of Request",
                        "agency": "Forward to the Dept. Head and Tourism Division Head the letter for approval; inform the client thru email; provide and send the approved materials thru email in video and photos",
                        "fees": "None",
                        "time": "2 days",
                        "person": "—",
                    },
                ],
                "total_fees": "None",
                "total_time": "2 days and 25 minutes",
            },
            {
                "number": 8,
                "title": "Inquiries on Tourism Products and Services and Activities",
                "description": (
                    "The Office recognizes the importance of providing latest and updated information and materials "
                    "regarding client's research and study about Laguna tourism. Networking or electronic social media "
                    "offers a safer, faster and more creative communication approach in delivering needed public services."
                ),
                "office": "LTCATO – Tourism Division (Planning, Development and Tourism Standards Unit & Promotions, Marketing and Creative Unit)",
                "classification": "Simple",
                "transaction_type": "G2G, G2B, G2C",
                "who_may_avail": "Government Agencies, Private Companies, Students, Academe, Tourists, Tourism Officers",
                "requirements": [
                    {"name": "Government Issued ID or School ID", "where": "—"},
                    {"name": "Scanned Company, BIR, GSIS, SSS, School ID, etc.", "where": "—"},
                ],
                "steps": [
                    {
                        "client": "Submit letter of Request addressed to LTCATO Department Head thru email",
                        "agency": "Receive the letter of request and send acknowledgment receipt",
                        "fees": "None",
                        "time": "20 minutes",
                        "person": "Raviel Aivan J. Litan — Administrative Aide I",
                    },
                    {
                        "client": "Inform the client to follow up after 5 days thru email",
                        "agency": "Forward to the Dept. Head and Tourism Division Head the letter of request for approval",
                        "fees": "None",
                        "time": "5 minutes",
                        "person": "—",
                    },
                    {
                        "client": "Wait for Approval of Request",
                        "agency": "Inform the client thru email; provide and send the materials thru email",
                        "fees": "None",
                        "time": "1–2 days",
                        "person": "—",
                    },
                ],
                "total_fees": "None",
                "total_time": "2 days and 25 minutes",
            },
        ],
    },
]

ABOUT_LAGUNA = {
    "intro": (
        "Laguna — the Pearl of the Orient's hidden gem — blends natural wonders, living heritage, "
        "vibrant festivals, and a thriving culture-and-arts scene. LTCATO serves as the provincial "
        "gateway for tourism promotion, standards, history, arts, culture, and trade development."
    ),
    "pillars": [
        {
            "icon": "ph-map-trifold",
            "title": "Tourism Development",
            "text": "Planning, promotion, and standards for destinations, accommodations, and visitor services across 24 municipalities and 6 cities.",
        },
        {
            "icon": "ph-palette",
            "title": "History, Arts & Culture",
            "text": "Preservation and promotion of historic sites, traditions, eminent persons, and cultural programs for Laguna's heritage.",
        },
        {
            "icon": "ph-storefront",
            "title": "Arts & Trade",
            "text": "Support for local artisans, MSMEs, and creative industries that showcase Laguna's products and craftsmanship.",
        },
        {
            "icon": "ph-users-three",
            "title": "Public Service",
            "text": "Transparent frontline services for LGUs, businesses, schools, and visitors — documented in our Citizen's Charter.",
        },
    ],
    "divisions": [
        {
            "name": "Tourism Division",
            "units": "Planning, Development and Tourism Standards · Promotions, Marketing and Creative",
            "focus": "Destination development, tourism data, trainings, virtual tours, and visitor inquiries.",
        },
        {
            "name": "History, Arts and Culture Division",
            "units": "Heritage research, cultural programs, and artist development",
            "focus": "Historic sites, cultural traditions, information requests, and talent development.",
        },
    ],
    "contact": {
        "email": "ltcato@laguna.gov.ph",
        "office": "Laguna Tourism, Culture, Arts and Trade Office (LTCATO)",
        "province": "Provincial Government of Laguna",
    },
}
