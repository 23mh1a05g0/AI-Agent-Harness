"""LLM Service integrating Mock LLM and OpenAI for structured tool call generation."""

import json
import re
from typing import Dict, Any, Optional
from app.config import settings


class LLMService:
    """Service to interpret user prompts into structured tool calls."""

    def __init__(self):
        self.mock_enabled = settings.MOCK_LLM_ENABLED
        self.openai_api_key = settings.OPENAI_API_KEY
        self.model = settings.OPENAI_MODEL
        self.base_url = settings.OPENAI_BASE_URL

    def generate_tool_call(self, prompt: str, target_row_id: Optional[int] = None) -> Dict[str, Any]:
        """Convert a user prompt into a raw tool-call dictionary.

        The LLM NEVER decides:
        - Whether approval is required
        - Whether an action is trusted
        - Whether an action can execute
        - Precondition checks or date constraints
        """
        if self.mock_enabled or not self.openai_api_key:
            return self._mock_llm(prompt, target_row_id)
        return self._openai_llm(prompt, target_row_id)

    def _mock_llm(self, prompt: str, target_row_id: Optional[int] = None) -> Dict[str, Any]:
        """Deterministic mock LLM parsing without external API keys."""
        cleaned = prompt.strip().lower()

        # Check for bulk attempts
        if any(term in cleaned for term in ["purge all", "purge everything", "delete all", "delete everything", "bulk purge", "mass delete"]):
            return {
                "action_type": "bulk_purge",
                "target_row_id": target_row_id,
                "raw_intent": "bulk",
            }

        # Extract target_row_id if not explicitly provided
        extracted_id = target_row_id
        if extracted_id is None:
            # Look for numbers following row, item, id, # or standalone number
            match = re.search(r"(?:row|item|id|#|\b)\s*(\d+)", cleaned)
            if match:
                extracted_id = int(match.group(1))

        # Check action type
        if "purge" in cleaned or "delete" in cleaned:
            return {
                "action_type": "purge",
                "target_row_id": extracted_id,
            }
        elif "post" in cleaned or "mark_posted" in cleaned or "mark posted" in cleaned or "publish" in cleaned:
            return {
                "action_type": "mark_posted",
                "target_row_id": extracted_id,
            }

        # Unknown action or malformed intent
        return {
            "action_type": "unknown",
            "target_row_id": extracted_id,
        }

    def _openai_llm(self, prompt: str, target_row_id: Optional[int] = None) -> Dict[str, Any]:
        """OpenAI API integration with function calling."""
        from openai import OpenAI

        client = OpenAI(
            api_key=self.openai_api_key,
            base_url=self.base_url if self.base_url else None,
        )

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "purge",
                    "description": "Purge a specific content item by its row id.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target_row_id": {"type": "integer", "description": "The row ID to purge"}
                        },
                        "required": ["target_row_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mark_posted",
                    "description": "Mark a specific content item as posted by its row id.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target_row_id": {"type": "integer", "description": "The row ID to mark posted"}
                        },
                        "required": ["target_row_id"],
                    },
                },
            },
        ]

        system_message = (
            "You are a strict tool-calling agent. You can only call purge or mark_posted "
            "for a specific row ID. You cannot perform bulk operations."
        )

        user_content = prompt
        if target_row_id is not None:
            user_content += f" (Target row ID: {target_row_id})"

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_content},
                ],
                tools=tools,
                tool_choice="auto",
            )
            message = response.choices[0].message
            if message.tool_calls:
                call = message.tool_calls[0]
                args = json.loads(call.function.arguments)
                return {
                    "action_type": call.function.name,
                    "target_row_id": args.get("target_row_id", target_row_id),
                }
            return {"action_type": "unknown", "target_row_id": target_row_id}
        except Exception as e:
            # Fallback to deterministic mock if API call fails
            return self._mock_llm(prompt, target_row_id)


llm_service = LLMService()
