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

# 动态注册每个工具
def make_tool_func_with_signature(path, method, details, tool):
    schema = tool.inputSchema or {}
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    # 构造参数列表
    params = []
    annotations = {}
    for name, info in props.items():
        typ = info.get("type", "str")
        if typ == "integer":
            pytyp = int
        elif typ == "number":
            pytyp = float
        elif typ == "boolean":
            pytyp = bool
        else:
            pytyp = str
        annotations[name] = pytyp
        if name in required:
            params.append(inspect.Parameter(name, inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=pytyp))
        else:
            params.append(inspect.Parameter(name, inspect.Parameter.POSITIONAL_OR_KEYWORD, default=None, annotation=pytyp))
    # 构造函数
    async def tool_func_template(**kwargs):
        url = f"http://127.0.0.1:8000{path}"
        headers = {}
        files = None
        data = None
        json_data = None
        if details.get("requestBody", {}).get("content", {}).get("multipart/form-data"):
            files = {}
            for k, v in kwargs.items():
                files[k] = v
        else:
            json_data = kwargs
        async with httpx.AsyncClient() as client:
            resp = await client.request(method.upper(), url, headers=headers, files=files, json=json_data, data=data)
            try:
                return resp.json()
            except Exception:
                return resp.text
    # 设置签名
    tool_func = types.FunctionType(tool_func_template.__code__, tool_func_template.__globals__, name=tool.name, argdefs=tool_func_template.__defaults__, closure=tool_func_template.__closure__)
    tool_func.__annotations__ = annotations
    tool_func.__doc__ = tool.description or ""
    tool_func.__signature__ = inspect.Signature(params)
    return tool_func

for path, path_item in openapi_spec.get("paths", {}).items():
    for method, details in path_item.items():
        op_id = details.get("operationId") or f"{method.upper()} {path}"
        # 找到 tool 对象
        tool = next((t for t in openapi_tools if t.name == op_id), None)
        if not tool:
            continue
        # 用明确参数签名注册工具
        func = make_tool_func_with_signature(path, method, details, tool)
        mcp.add_tool(func)
        # 注册 schema 查询工具
        def make_schema_func(schema, name, desc):
            async def schema_func() -> list:
                """返回接口的参数字段信息（字段名、类型、是否必填、备注）"""
                fields = parse_schema(schema)
                if not fields:
                    return {"message": "该接口没有定义参数 schema"}
                return fields
            schema_func.__name__ = name
            schema_func.__doc__ = desc
            return schema_func
        schema_tool_name = f"get_{op_id}_schema"
        schema_func = make_schema_func(tool.inputSchema, schema_tool_name, f"获取 {op_id} 的参数定义")
        mcp.add_tool(schema_func)

if __name__ == "__main__":
    mcp.run(transport="sse")