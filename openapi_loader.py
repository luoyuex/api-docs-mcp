import json
import os
import logging
from mcp.types import Tool

log = logging.getLogger(__name__)

def load_openapi_spec(spec_path):
    """Loads an OpenAPI specification and extracts tool definitions."""
    if not os.path.exists(spec_path):
        log.error(f"OpenAPI spec file not found at {spec_path}")
        return []

    try:
        with open(spec_path, "r") as f:
            spec = json.load(f)
    except json.JSONDecodeError:
        log.error(f"Could not decode JSON from {spec_path}")
        return []

    tools = []
    paths = spec.get("paths", {})

    for path, path_details in paths.items():
        for method, details in path_details.items():
            # Extract input schema
            input_schema = {}
            if request_body := details.get("requestBody", {}):
                if content := request_body.get("content", {}):
                    for content_type in ["application/json", "multipart/form-data"]:
                        if content_type in content:
                            input_schema = content[content_type].get("schema", {})
                            break
            
            # Extract output schema
            output_schema = {}
            if responses := details.get("responses", {}):
                if response_ok := responses.get("200", {}):
                    if content := response_ok.get("content", {}):
                        if "application/json" in content:
                            output_schema = content["application/json"].get("schema", {})

            tool = Tool(
                name=details.get("operationId") or f"{method.upper()} {path}",
                description=details.get("summary", ""),
                inputSchema=input_schema,
                outputSchema=output_schema,
            )
            tools.append(tool)

    log.info(f"Loaded {len(tools)} tools from {spec_path}")
    return tools
