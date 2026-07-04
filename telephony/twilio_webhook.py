"""
Guardian Angel — Twilio Webhook Handlers

Receives incoming call webhooks from Twilio, extracts real-time transcription
chunks via Twilio Media Streams, and forwards them to the Guardian Angel
event processing pipeline.

IMPORTANT: This is a production-ready stub. To fully integrate:
1. Configure Twilio account SID and auth token in .env
2. Set up a Twilio phone number with call forwarding
3. Configure the Media Streams webhook URL to point to this server
4. Enable Twilio Speech Recognition / Media Streams add-on

Architecture:
    Twilio Call → Webhook → /telephony/incoming → TwiML (connect Media Stream)
                                                      ↓
    Twilio Media Stream → WebSocket → /telephony/stream → Transcript chunks
                                                              ↓
                                                     Guardian Angel Event API
"""

import os
import json
import logging
import base64
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import Response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telephony", tags=["telephony"])

# Environment configuration
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
GUARDIAN_API_BASE = os.getenv("GUARDIAN_API_BASE", "http://127.0.0.1:8000")


@router.post("/incoming")
async def handle_incoming_call(request: Request):
    """
    Handle incoming call webhook from Twilio.

    Returns TwiML that:
    1. Answers the call
    2. Starts a bidirectional Media Stream for real-time transcription
    3. Connects the call through (does NOT block the conversation)
    """
    # Determine the WebSocket URL for Media Streams
    host = request.headers.get("host", "localhost:8000")
    ws_url = f"wss://{host}/telephony/stream"

    # Extract caller info from Twilio webhook payload
    form_data = await request.form()
    caller_number = form_data.get("From", "unknown")
    called_number = form_data.get("To", "unknown")
    call_sid = form_data.get("CallSid", "unknown")

    logger.info(f"Incoming call: {caller_number} → {called_number} (SID: {call_sid})")

    # Return TwiML response that starts a Media Stream
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Start>
        <Stream url="{ws_url}" track="both_tracks">
            <Parameter name="caller_number" value="{caller_number}" />
            <Parameter name="called_number" value="{called_number}" />
            <Parameter name="call_sid" value="{call_sid}" />
        </Stream>
    </Start>
    <Dial>{called_number}</Dial>
</Response>"""

    return Response(content=twiml, media_type="application/xml")


@router.post("/status")
async def handle_call_status(request: Request):
    """
    Handle call status callback from Twilio.
    Logs call completion events for the audit trail.
    """
    form_data = await request.form()
    call_sid = form_data.get("CallSid", "unknown")
    call_status = form_data.get("CallStatus", "unknown")
    duration = form_data.get("CallDuration", "0")

    logger.info(f"Call status update: SID={call_sid}, Status={call_status}, Duration={duration}s")

    # In production, this would update the call record in the database
    # and potentially trigger post-call analysis

    return {"status": "acknowledged"}


@router.websocket("/stream")
async def handle_media_stream(websocket: WebSocket):
    """
    WebSocket endpoint for Twilio Media Streams.

    Receives real-time audio from Twilio, processes it into transcript
    chunks, and forwards them to the Guardian Angel event pipeline.

    Twilio Media Stream protocol:
    - 'connected': Stream connected
    - 'start': Stream metadata (call SID, track info)
    - 'media': Audio payload (base64 encoded mu-law)
    - 'stop': Stream ended
    """
    await websocket.accept()

    call_metadata = {
        "call_sid": None,
        "caller_number": None,
        "called_number": None,
        "stream_sid": None,
        "chunk_buffer": [],
        "chunk_index": 0
    }

    logger.info("Media Stream WebSocket connected.")

    try:
        async for raw_message in websocket.iter_text():
            try:
                message = json.loads(raw_message)
                event_type = message.get("event")

                if event_type == "connected":
                    logger.info("Twilio Media Stream: connected")

                elif event_type == "start":
                    # Extract call metadata from stream start event
                    start_data = message.get("start", {})
                    call_metadata["stream_sid"] = start_data.get("streamSid")
                    call_metadata["call_sid"] = start_data.get("callSid")

                    custom_params = start_data.get("customParameters", {})
                    call_metadata["caller_number"] = custom_params.get("caller_number", "unknown")
                    call_metadata["called_number"] = custom_params.get("called_number", "unknown")

                    logger.info(
                        f"Stream started: SID={call_metadata['stream_sid']}, "
                        f"Caller={call_metadata['caller_number']}"
                    )

                elif event_type == "media":
                    # In production, this audio payload would be sent to a
                    # Speech-to-Text service (e.g., Google Cloud STT, Deepgram)
                    # for real-time transcription. The transcription result would
                    # then be forwarded to the Guardian Angel event pipeline.
                    #
                    # For this stub, we log the receipt of audio data.
                    media_data = message.get("media", {})
                    # payload = base64.b64decode(media_data.get("payload", ""))
                    # track = media_data.get("track")  # "inbound" or "outbound"

                    # Stub: In production, accumulate audio and send to STT
                    # When transcription returns, forward to:
                    #   POST /api/events/call-chunk
                    #   {
                    #     "call_id": call_metadata["call_sid"],
                    #     "elder_id": <looked up from called_number>,
                    #     "caller_number": call_metadata["caller_number"],
                    #     "speaker": "caller" if track == "inbound" else "elder",
                    #     "text": <transcription_result>,
                    #     "chunk_index": call_metadata["chunk_index"]
                    #   }
                    pass

                elif event_type == "stop":
                    logger.info(f"Stream stopped: SID={call_metadata['stream_sid']}")
                    break

            except json.JSONDecodeError:
                logger.warning("Received non-JSON message on Media Stream WebSocket.")
                continue

    except WebSocketDisconnect:
        logger.info("Media Stream WebSocket disconnected.")
    except Exception as e:
        logger.error(f"Media Stream error: {e}")
    finally:
        logger.info(f"Media Stream session ended for call {call_metadata['call_sid']}")


def lookup_elder_by_phone(phone_number: str) -> Optional[str]:
    """
    Look up an elder's user ID by their registered phone number.

    In production, this queries the database for the user record
    associated with the given Twilio phone number.

    Args:
        phone_number: The called phone number (elder's number).

    Returns:
        The elder's user ID, or None if not found.
    """
    # Stub implementation — in production, query DB
    logger.info(f"Phone lookup stub for: {phone_number}")
    return None
