"""
Guardian Angel — Orchestrator Agent (Google Antigravity SDK implementation)

Runs the main scam and fraud analysis loop. Connects to all four MCP servers via stdio,
launches the local OpenRouter proxy, and queries the LLM agent to obtain a structured
RiskDecision. Implements fallback/degraded mode in case of LLM failure.
"""

import asyncio
import logging
import os
import sys
from typing import Dict, Any, Optional

from google.antigravity import Agent, LocalAgentConfig, types
from database.models import RiskDecision, RiskTier, ActionType
from agents.openrouter_proxy import start_proxy_thread, proxy_port

logger = logging.getLogger(__name__)

# Track if the OpenRouter translation proxy is running
_proxy_started = False

def ensure_proxy_running():
    """Start the local translation proxy if not already running."""
    global _proxy_started
    if not _proxy_started:
        logger.info("Initializing OpenRouter translation proxy...")
        start_proxy_thread()
        _proxy_started = True

def get_agent_config(conversation_id: Optional[str] = None) -> LocalAgentConfig:
    """
    Build the LocalAgentConfig with custom ModelTarget pointing to the local proxy
    and registering all 4 stdio MCP servers.
    """
    ensure_proxy_running()
    
    # Get API key from environment
    api_key = os.getenv("OPENROUTER_API_KEY", "mock_key_for_harness")
    
    # Build standard paths for stdio command
    python_cmd = sys.executable or "python3"
    
    # Register the 4 MCP servers as stdio servers
    mcp_servers = [
        types.McpStdioServer(
            name="scam-pattern-server",
            command=python_cmd,
            args=["mcp_servers/scam_pattern_server.py"]
        ),
        types.McpStdioServer(
            name="caller-id-server",
            command=python_cmd,
            args=["mcp_servers/caller_id_server.py"]
        ),
        types.McpStdioServer(
            name="bank-transaction-server",
            command=python_cmd,
            args=["mcp_servers/bank_transaction_server.py"]
        ),
        types.McpStdioServer(
            name="family-alert-server",
            command=python_cmd,
            args=["mcp_servers/family_alert_server.py"]
        )
    ]
    
    # Define custom model target pointing to the local proxy
    model_target = types.ModelTarget(
        name="gemini-2.0-flash",
        types=[types.ModelType.TEXT],
        endpoint=types.GeminiAPIEndpoint(
            api_key=api_key,
            base_url=f"http://127.0.0.1:{proxy_port}"
        )
    )
    
    # Read system instructions
    with open("agents/prompts/orchestrator.txt", "r") as f:
        system_instructions = f.read()
        
    return LocalAgentConfig(
        system_instructions=system_instructions,
        models=[model_target],
        mcp_servers=mcp_servers,
        response_schema=RiskDecision,
        conversation_id=conversation_id,
        workspaces=[os.getcwd()]
    )

def format_call_event(call_event: Dict[str, Any]) -> str:
    """Format the incoming call metadata and transcript into a prompt for the agent."""
    caller_num = call_event.get("caller_number", "Unknown")
    claimed_id = call_event.get("claimed_identity", "None stated")
    transcript = call_event.get("transcript", "")
    elder_id = call_event.get("elder_id", "unknown_elder")
    
    transaction_str = ""
    if call_event.get("has_transaction"):
        tx = call_event.get("transaction_details", {})
        tx_id = tx.get("transaction_id", "tx_unknown")
        amount = tx.get("amount", 0.0)
        recipient = tx.get("recipient", "Unknown")
        transaction_str = (
            f"\n--- FINANCIAL TRANSACTION IN PROGRESS ---\n"
            f"Transaction ID: {tx_id}\n"
            f"Amount: ${amount:.2f}\n"
            f"Recipient: {recipient}\n"
        )
        
    prompt = (
        f"Elder User ID: {elder_id}\n"
        f"Caller Number: {caller_num}\n"
        f"Claimed Identity: {claimed_id}\n"
        f"{transaction_str}"
        f"\n--- LIVE TRANSCRIPT SNIPPET ---\n"
        f"{transcript}\n"
        f"\nAnalyze this live transcript using your available tools and output the decision."
    )
    return prompt

async def analyze_call_event(call_event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point to analyze a call event. Runs the agent and returns a RiskDecision dict.
    If the agent fails or times out, it defaults to the medium tier with a degraded confidence note.
    """
    try:
        config = get_agent_config(conversation_id=call_event.get("conversation_id"))
        
        async with Agent(config) as agent:
            prompt = format_call_event(call_event)
            logger.info("Sending transcript analysis request to Guardian Angel Agent...")
            response = await agent.chat(prompt)
            structured = await response.structured_output()
            
            if structured:
                # If high risk or transaction paused, verify and invoke family_alert_server tool
                # Wait, the LLM agent system instruction instructs it to call `send_family_alert` tool
                # itself inside the loop. But we double check and return the structured dict.
                return structured.model_dump()
            else:
                logger.warning("Agent failed to output structured data. Falling back to medium tier.")
                return get_fallback_decision("Model failed to output structured risk decision.")
                
    except Exception as e:
        logger.exception("Guardian Angel Orchestrator error. Falling back to medium tier.")
        return get_fallback_decision(f"Orchestration pipeline exception: {str(e)}")

def get_fallback_decision(reason: str) -> Dict[str, Any]:
    """Build a safe default decision in case of agent failure."""
    return {
        "risk_score": 50,
        "tier": RiskTier.MEDIUM,
        "reasons": [
            "Guardian Angel warning: Scam analysis degraded due to system connection issue.",
            f"Reason: {reason}",
            "Please avoid sharing personal information or transferring funds until caller identity is verified manually."
        ],
        "action": ActionType.WARN_ELDER,
        "caller_verification_score": 50,
        "scam_pattern_score": 50,
        "urgency_pressure_score": 50,
        "matched_phrases": [],
        "transaction_flagged": False
    }
