"""
Guardian Angel — Scam Pattern Database MCP Server

Exposes a tool to check call transcripts against known scam scripts and tactics.
Exposes tool: `match_patterns`
"""

import re
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("scam-pattern-server")

# Database of consumer-protection scam categories and associated regexes
SCAM_PATTERNS = {
    "fake_bank_fraud_alert": [
        r"account (will be|has been) (frozen|suspended|locked)",
        r"verify your (otp|pin|card number|password|credentials)",
        r"transfer.*to (safe|secure|temporary) account",
        r"unauthorized transaction|suspicious activity on your account",
    ],
    "government_impersonation": [
        r"warrant (for|against) your arrest",
        r"pay (immediately|now) to avoid (legal action|arrest|jail|prosecution)",
        r"irs|internal revenue service|social security administration",
        r"compromised social security number",
    ],
    "relative_in_trouble": [
        r"(grandson|granddaughter|son|daughter|grandchild|niece|nephew).{0,30}(jail|accident|hospital|police|car crash)",
        r"don'?t tell (my parents|anyone|your family|mom|dad)",
        r"bail money|need cash immediately|wire transfer for bail",
    ],
    "tech_support_scam": [
        r"virus (detected|found) on your (computer|device|windows|mac)",
        r"remote access|download anydesk|download teamviewer|install software",
        r"microsoft support|apple care|certified technician",
        r"hackers have access to your webcam",
    ],
    "romance_scam": [
        r"send money for (plane ticket|medical bill|visa|emergency)",
        r"cannot meet in person|camera (is broken|does not work)",
        r"crypto investment|make money together|guaranteed returns",
    ],
    "lottery_prize_scam": [
        r"won a (lottery|prize|sweepstakes|draw|raffle)",
        r"pay (taxes|processing fees|customs fees|administrative fees) (first|before receiving)",
        r"claim your reward|unclaimed funds",
    ],
    "utility_disconnection": [
        r"(power|gas|electricity|water) (will be|is going to be) (cut off|disconnected|shut down)",
        r"pay within (a few hours|an hour|1 hour|30 minutes)",
        r"pay with (gift card|prepaid card|bitcoin|vanilla card)",
    ]
}

@mcp.tool()
def match_patterns(text: str) -> dict:
    """
    Compare transcript text against known scam scripts and patterns.
    Returns matched categories and the specific phrases that triggered each match,
    along with a computed pattern match score (0-100).
    """
    matches = {}
    matched_phrases = []
    
    for category, patterns in SCAM_PATTERNS.items():
        category_hits = []
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                phrase = match.group(0)
                category_hits.append(phrase)
                matched_phrases.append(phrase)
        if category_hits:
            matches[category] = category_hits
            
    # Calculate a simple score based on the number of categories matched
    # 1 category = 35, 2 categories = 70, 3+ categories = 100
    num_matches = len(matches)
    score = min(100, num_matches * 35)
    
    return {
        "matched_categories": matches,
        "pattern_score": score,
        "matched_phrases": matched_phrases
    }

if __name__ == "__main__":
    mcp.run()
