"""Convert the shared reply schema into standard JSON Schema.

The schema built in ``src/modules/seeds/prompt.py`` uses the OpenAPI subset
Gemini accepts, where nullability is a ``nullable`` flag. Ollama and OpenAI
take standard JSON Schema instead, where it is a ``null`` type.

OpenAI's strict Structured Outputs additionally require every object to
declare ``additionalProperties: false`` and every property as required. The
shared schema already requires every property.
"""

from __future__ import annotations

from typing import Any, Mapping


def to_json_schema(schema: Mapping[str, Any], strict: bool = False) -> Any:
    """``{"type": "string", "nullable": true}`` -> ``{"type": ["string", "null"]}``."""
    converted = {}
    for key, value in schema.items():
        if key == "nullable":
            continue
        if isinstance(value, Mapping):
            # Covers "items" and "properties" (whose values are schemas) alike.
            converted[key] = to_json_schema(value, strict)
        else:
            converted[key] = value
    if schema.get("nullable"):
        converted["type"] = [schema["type"], "null"]
        if "enum" in converted:
            converted["enum"] = list(converted["enum"]) + [None]
    if strict and schema.get("type") == "object":
        converted["additionalProperties"] = False
    return converted
