"""
Guardian Angel — Caller ID Lookup MCP Server

Exposes tools to verify phone numbers, check scam registries, and cross-reference claimed identities.
Exposes tools: `reverse_lookup`, `check_scam_registry`, `verify_institution`
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("caller-id-server")

# Directory of verified institution phone numbers (normalized format)
VERIFIED_INSTITUTIONS = {
    "1800112211": "State Bank of India Fraud Department",
    "18004253800": "State Bank of India Customer Care",
    "18002026161": "HDFC Bank Customer Support",
    "18602676161": "HDFC Bank Credit Cards Division",
    "18001080": "ICICI Bank Hotline",
    "18008291040": "Internal Revenue Service (IRS) Taxpayer Helpline",
    "18007721213": "Social Security Administration (SSA) General Line",
    "18009359935": "Chase Bank Customer Service",
    "18882804331": "Amazon Customer Service",
}

# Scam registry (reported spam/scam numbers)
SCAM_REGISTRY = {
    "18881234567": {"category": "Fake Tech Support", "reports": 412},
    "18009999999": {"category": "Fake IRS Agent", "reports": 850},
    "19005550199": {"category": "Sweepstakes Scam", "reports": 97},
    "14155552671": {"category": "Utility Cutoff Threat", "reports": 184},
    "15559876543": {"category": "Relative in Trouble bail scam", "reports": 63},
}

def _normalize_number(phone_number: str) -> str:
    """Helper to remove common formatting characters (+, -, space, parens)"""
    return "".join(c for c in phone_number if c.isdigit())

@mcp.tool()
def reverse_lookup(phone_number: str) -> dict:
    """
    Perform a reverse lookup on a phone number to check if it matches a known, verified institution.
    """
    norm_num = _normalize_number(phone_number)
    
    # Check verified directory
    for num, name in VERIFIED_INSTITUTIONS.items():
        if norm_num.endswith(num) or num.endswith(norm_num):
            return {
                "found": True,
                "verified": True,
                "owner": name,
                "note": "This is a verified phone number of the institution."
            }
            
    return {
        "found": False,
        "verified": False,
        "owner": "Unknown Caller",
        "note": "This number is not in the directory of verified institutions."
    }

@mcp.tool()
def check_scam_registry(phone_number: str) -> dict:
    """
    Check if a number has been reported in the scam number registry.
    """
    norm_num = _normalize_number(phone_number)
    
    # Check scam registry
    for num, details in SCAM_REGISTRY.items():
        if norm_num.endswith(num) or num.endswith(norm_num):
            return {
                "flagged": True,
                "category": details["category"],
                "report_count": details["reports"],
                "risk_score": 100 if details["reports"] > 100 else 75,
                "reason": f"Number is flagged in scam registry for {details['category']} with {details['reports']} reports."
            }
            
    return {
        "flagged": False,
        "category": None,
        "report_count": 0,
        "risk_score": 0,
        "reason": "Number has not been reported to the scam registry."
    }

@mcp.tool()
def verify_institution(claimed_identity: str, phone_number: str) -> dict:
    """
    Verify if the caller ID matches a verified phone number for the claimed institution.
    """
    if not claimed_identity:
        return {
            "verified": False,
            "risk_score": 50,
            "reason": "No claimed identity stated for verification."
        }
        
    norm_num = _normalize_number(phone_number)
    lookup_result = reverse_lookup(phone_number)
    
    # If the number is verified, does it match the claimed identity?
    if lookup_result["verified"]:
        owner_lower = lookup_result["owner"].lower()
        claim_lower = claimed_identity.lower()
        # Substring match check
        if claim_lower in owner_lower or owner_lower in claim_lower:
            return {
                "verified": True,
                "risk_score": 0,
                "reason": f"Caller ID matches verified number for {lookup_result['owner']}."
            }
        else:
            return {
                "verified": False,
                "risk_score": 90,
                "reason": f"Spoofing warning: Caller claims to be {claimed_identity} but the number belongs to {lookup_result['owner']}."
            }
            
    # If not verified, but they claim to be a major institution, flag it as unverified
    major_institutions = ["sbi", "state bank", "hdfc", "icici", "chase", "irs", "internal revenue", "social security", "amazon"]
    claim_lower = claimed_identity.lower()
    for inst in major_institutions:
        if inst in claim_lower:
            return {
                "verified": False,
                "risk_score": 75,
                "reason": f"Suspicious: Caller claims to be from {claimed_identity}, but calling number {phone_number} is not verified for this institution."
            }
            
    return {
        "verified": False,
        "risk_score": 50,
        "reason": "Uncertain caller: Phone number is unverified, but identity does not match a known flagged institution."
    }

if __name__ == "__main__":
    mcp.run()
