import json
import httpx
import os
from mcp.server.fastmcp import FastMCP
from typing import Any
from openapi_loader import load_openapi_spec
import types
import inspect

OPENAPI_PATH = os.path.join(os.path.dirname(__file__), "apidocs.json")

mcp = FastMCP("openapi")

# 加载 OpenAPI 工具定义
openapi_tools = load_openapi_spec(OPENAPI_PATH)

# 加载原始 OpenAPI spec 以便查找 endpoint
with open(OPENAPI_PATH, "r") as f:
    openapi_spec = json.load(f)

def parse_schema(schema):
    if not schema or not isinstance(schema, dict):
        return []
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    result = []
    for name, info in props.items():
        result.append({
            "name": name,
            "type": info.get("type", "unknown"),
            "required": name in required,
            "description": info.get("description", "")
        })
    return result

def simplify_data(data):
    """简化数据结构，数组只保留第一个元素"""
    if isinstance(data, list) and len(data) > 0:
        return simplify_data(data[0])
    elif isinstance(data, dict):
        return {k: simplify_data(v) for k, v in data.items()}
    else:
        return data

def extract_example_data(details):
    """从接口定义中提取并简化案例数据"""
    examples = {}
    
    # 获取请求示例
    request_body = details.get("requestBody", {})
    content = request_body.get("content", {})
    
    for content_type, content_info in content.items():
        example = content_info.get("example")
        if example:
            examples["request"] = simplify_data(example)
            break
    
    # 获取响应示例
    responses = details.get("responses", {})
    for status, response_info in responses.items():
        response_content = response_info.get("content", {})
        for content_type, content_info in response_content.items():
            example = content_info.get("example")
            if example:
                examples["response"] = simplify_data(example)
                break
        if "response" in examples:
            break
    
    return examples

def make_schema_tool(tool_name, schema, details):
    """创建字段查询工具函数"""
    async def schema_func() -> dict:
        """获取接口的字段信息和案例数据"""
        result = {
            "summary": details.get("summary", ""),
            "method": "",
            "path": ""
        }
        
        # 获取字段信息
        fields = parse_schema(schema)
        if fields:
            result["fields"] = fields
        
        # 获取案例数据
        examples = extract_example_data(details)
        if examples:
            result["examples"] = examples
        
        # 如果既没有字段也没有案例
        if not fields and not examples:
            result["note"] = "此接口无参数字段和案例数据"
        
        return result
    
    schema_func.__name__ = tool_name
    return schema_func

# 只注册字段查询工具，不注册接口调用工具
for path, path_item in openapi_spec.get("paths", {}).items():
    for method, details in path_item.items():
        op_id = details.get("operationId") or f"{method.upper()} {path}"
        # 找到 tool 对象
        tool = next((t for t in openapi_tools if t.name == op_id), None)
        if not tool:
            continue
        
        # 只注册字段查询工具
        schema_tool_name = f"get_{op_id}_fields"
        schema_func = make_schema_tool(schema_tool_name, tool.inputSchema, details)
        schema_func.__doc__ = f"获取 {details.get('summary', op_id)} 接口的字段信息或案例数据"
        mcp.add_tool(schema_func)

if __name__ == "__main__":
    mcp.run(transport="sse")