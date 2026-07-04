"""
Guardian Angel — Bank Transaction Guardrail MCP Server

Exposes tools to inspect financial transactions, evaluate transaction risk,
and pause transactions for dual human verification.
Exposes tools: `get_transaction`, `check_transaction_risk`, `pause_and_confirm`
"""

from typing import Dict, Any
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("bank-transaction-server")

# In-memory mock database of pending transactions
# In a real system, this connects directly to the bank's open banking API or core banking backend.
MOCK_TRANSACTIONS: Dict[str, Dict[str, Any]] = {
    "tx_987654": {
        "id": "tx_987654",
        "elder_id": "user_elder_1",
        "amount": 4500.0,
        "recipient": "Western Union Wire Transfer - London",
        "status": "pending",
        "timestamp": "2026-07-04T20:00:00Z",
        "verification_required": True,
        "verification_reason": None,
    },
    "tx_123456": {
        "id": "tx_123456",
        "elder_id": "user_elder_1",
        "amount": 45.50,
        "recipient": "Local Grocery Store",
        "status": "completed",
        "timestamp": "2026-07-04T18:30:00Z",
        "verification_required": False,
        "verification_reason": None,
    },
    "tx_111222": {
        "id": "tx_111222",
        "elder_id": "user_elder_1",
        "amount": 1500.0,
        "recipient": "Target Gift Card Purchase",
        "status": "pending",
        "timestamp": "2026-07-04T20:15:00Z",
        "verification_required": True,
        "verification_reason": None,
    }
}

# Mock transaction history of typical users to calculate risk
USER_HISTORY: Dict[str, list] = {
    "user_elder_1": [
        {"amount": 50.0, "recipient": "Electricity Board", "category": "utility"},
        {"amount": 120.0, "recipient": "Supermarket", "category": "groceries"},
        {"amount": 35.0, "recipient": "Pharmacy", "category": "medical"},
        {"amount": 45.50, "recipient": "Local Grocery Store", "category": "groceries"},
    ]
}

@mcp.tool()
def get_transaction(transaction_id: str) -> dict:
    """
    Retrieve transaction details for inspection.
    """
    tx = MOCK_TRANSACTIONS.get(transaction_id)
    if tx:
        return {"found": True, "transaction": tx}
    return {"found": False, "transaction": None, "reason": "Transaction ID not found"}

@mcp.tool()
def check_transaction_risk(elder_id: str, amount: float, recipient: str) -> dict:
    """
    Evaluate transaction risk based on historical transactions, amount, and recipient keywords.
    High risk recipients: wire transfers, cryptocurrency, gift cards, unknown individual accounts.
    High risk amounts: transactions exceeding typical historical ranges.
    """
    history = USER_HISTORY.get(elder_id, [])
    
    # Calculate typical average amount
    avg_amount = sum(h["amount"] for h in history) / len(history) if history else 50.0
    max_amount = max(h["amount"] for h in history) if history else 150.0
    
    reasons = []
    risk_score = 0
    
    # Check amount risk
    if amount > max_amount * 10:
        reasons.append(f"Amount ${amount:.2f} is extremely high (typical max is ${max_amount:.2f})")
        risk_score += 45
    elif amount > max_amount * 3:
        reasons.append(f"Amount ${amount:.2f} is significantly higher than typical transactions")
        risk_score += 25
        
    # Check recipient risk keywords
    rec_lower = recipient.lower()
    high_risk_keywords = {
        "western union": ("Wire Transfer Service", 45),
        "moneygram": ("Wire Transfer Service", 45),
        "gift card": ("Gift Card / Voucher Store", 45),
        "target card": ("Gift Card Purchase", 40),
        "apple card": ("Gift Card Purchase", 40),
        "bitcoin": ("Cryptocurrency ATM / Exchange", 50),
        "crypto": ("Cryptocurrency Exchange", 50),
        "wire transfer": ("Wire Transfer", 40),
    }
    
    keyword_matched = False
    for kw, (category, penalty) in high_risk_keywords.items():
        if kw in rec_lower:
            reasons.append(f"Recipient matched high-risk keyword/category: {category}")
            risk_score += penalty
            keyword_matched = True
            break
            
    if not keyword_matched and recipient not in [h["recipient"] for h in history]:
        reasons.append(f"Recipient '{recipient}' is new and not in user transaction history")
        risk_score += 15
        
    final_score = min(100, risk_score)
    
    return {
        "risk_score": final_score,
        "flagged": final_score >= 50,
        "reasons": reasons if reasons else ["Normal transaction patterns"],
        "analysis": {
            "avg_historical_amount": avg_amount,
            "max_historical_amount": max_amount,
            "recipient_is_new": recipient not in [h["recipient"] for h in history]
        }
    }

@mcp.tool()
def pause_and_confirm(transaction_id: str, reason: str) -> dict:
    """
    Pause a pending transaction and request dual human confirmation (Elder AND notified Family member).
    Returns the action taken and status. Note: NEVER cancels a transaction outright.
    """
    tx = MOCK_TRANSACTIONS.get(transaction_id)
    if not tx:
        return {"success": False, "reason": f"Transaction {transaction_id} not found."}
        
    tx["status"] = "paused_and_confirm"
    tx["verification_required"] = True
    tx["verification_reason"] = reason
    
    # Save back to database
    MOCK_TRANSACTIONS[transaction_id] = tx
    
    return {
        "success": True,
        "transaction_id": transaction_id,
        "status": "paused_and_confirm",
        "action": "pause_and_confirm",
        "message": f"Transaction of ${tx['amount']:.2f} to '{tx['recipient']}' has been paused. "
                   f"Requires confirmation from the elder and authorized family. Reason: {reason}"
    }

if __name__ == "__main__":
    mcp.run()
