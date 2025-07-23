import json
import httpx
import os
import logging
from mcp.server.fastmcp import FastMCP
from typing import Any, Dict, List, Optional
from openapi_loader import load_openapi_spec
import types
import inspect

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

OPENAPI_PATH = os.path.join(os.path.dirname(__file__), "apidocs.json")

mcp = FastMCP("openapi")

# 加载 OpenAPI 工具定义
try:
    log.info(f"开始加载 OpenAPI 规范文件: {OPENAPI_PATH}")
    openapi_tools = load_openapi_spec(OPENAPI_PATH)
    if not openapi_tools:
        log.error("无法加载任何 OpenAPI 工具，程序退出")
        exit(1)
except Exception as e:
    log.error(f"加载 OpenAPI 工具时发生错误: {e}")
    exit(1)

# 加载原始 OpenAPI spec 以便查找 endpoint
try:
    with open(OPENAPI_PATH, "r", encoding='utf-8') as f:
        openapi_spec = json.load(f)
except Exception as e:
    log.error(f"加载 OpenAPI 规范文件失败: {e}")
    exit(1)

def parse_schema(schema: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """解析 JSON Schema 并返回字段信息列表"""
    if not schema or not isinstance(schema, dict):
        return []
    
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    result = []
    
    try:
        for name, info in props.items():
            if not isinstance(info, dict):
                continue
                
            field_info = {
                "name": name,
                "type": info.get("type", "unknown"),
                "required": name in required,
                "description": info.get("description", "")
            }
            
            # 添加更多规范信息
            if "format" in info:
                field_info["format"] = info["format"]
            if "example" in info:
                field_info["example"] = info["example"]
            if "enum" in info:
                field_info["enum"] = info["enum"]
            if "maxLength" in info:
                field_info["maxLength"] = info["maxLength"]
            if "minLength" in info:
                field_info["minLength"] = info["minLength"]
                
            result.append(field_info)
    except Exception as e:
        log.warning(f"解析 schema 时发生错误: {e}")
        
    return result

def simplify_data(data: Any, max_depth: int = 3, current_depth: int = 0) -> Any:
    """简化数据结构，数组只保留第一个元素，限制递归深度"""
    if current_depth >= max_depth:
        return "...数据过深，已省略..."
        
    try:
        if isinstance(data, list) and len(data) > 0:
            # 保留数组的第一个元素，但保留数组的结构信息
            return [simplify_data(data[0], max_depth, current_depth + 1)]
        elif isinstance(data, dict):
            return {k: simplify_data(v, max_depth, current_depth + 1) for k, v in data.items()}
        else:
            return data
    except Exception as e:
        log.warning(f"简化数据时发生错误: {e}")
        return data

def extract_example_data(details: Dict[str, Any]) -> Dict[str, Any]:
    """从接口定义中提取并简化案例数据"""
    examples = {}
    
    try:
        # 获取请求示例
        request_body = details.get("requestBody", {})
        content = request_body.get("content", {})
        
        for content_type, content_info in content.items():
            if not isinstance(content_info, dict):
                continue
                
            example = content_info.get("example")
            if example:
                examples["request"] = simplify_data(example)
                break
                
            # 如果没有 example，尝试从 schema 中获取
            schema = content_info.get("schema", {})
            if isinstance(schema, dict) and "properties" in schema:
                schema_example = {}
                for prop_name, prop_info in schema["properties"].items():
                    if isinstance(prop_info, dict) and "example" in prop_info:
                        schema_example[prop_name] = prop_info["example"]
                if schema_example:
                    examples["request"] = schema_example
                    break
        
        # 获取响应示例
        responses = details.get("responses", {})
        for status, response_info in responses.items():
            if not isinstance(response_info, dict):
                continue
                
            response_content = response_info.get("content", {})
            for content_type, content_info in response_content.items():
                if not isinstance(content_info, dict):
                    continue
                    
                example = content_info.get("example")
                if example:
                    examples["response"] = simplify_data(example)
                    break
            if "response" in examples:
                break
                
    except Exception as e:
        log.warning(f"提取示例数据时发生错误: {e}")
    
    return examples

def make_schema_tool(tool_name: str, schema: dict, details: dict, method: str, path: str) -> callable:
    """创建接口字段查询工具函数"""
    async def schema_func() -> dict:
        """获取接口的字段信息和案例数据"""
        result = {
            "summary": details.get("summary", "未知接口"),
            "method": method.upper(),
            "path": path
        }
        
        # 获取字段信息
        fields = parse_schema(schema)
        if fields:
            result["fields"] = fields
        
        # 获取案例数据
        examples = extract_example_data(details)
        if examples:
            result["examples"] = examples
        
        # 如果既没有字段也没有案例，返回基本信息
        if not fields and not examples:
            result["note"] = "此接口无参数字段和案例数据"
        
        return result
    
    schema_func.__name__ = tool_name
    return schema_func

# 注册接口字段查询工具
registered_tools = 0
for path, path_item in openapi_spec.get("paths", {}).items():
    for method, details in path_item.items():
        if method.lower() not in ['get', 'post', 'put', 'delete', 'patch', 'head', 'options']:
            continue  # 跳过非HTTP方法
            
        op_id = details.get("operationId") or f"{method}_{path.replace('/', '_').replace('{', '').replace('}', '')}"
        # 找到对应的 tool 对象
        tool = next((t for t in openapi_tools if t.name == (details.get("operationId") or f"{method.upper()} {path}")), None)
        if not tool:
            continue
        
        # 注册字段查询工具，使用更清晰的命名
        schema_tool_name = f"get_{op_id}_schema"
        schema_func = make_schema_tool(schema_tool_name, tool.inputSchema, details, method, path)
        
        # 生成更详细的工具描述
        summary = details.get('summary', '未知接口')
        description = f"查看 {method.upper()} {path} 接口的详细信息\n功能: {summary}\n返回接口的参数字段、类型、是否必填、示例数据等完整规范信息"
        schema_func.__doc__ = description
        
        mcp.add_tool(schema_func)
        registered_tools += 1

log.info(f"成功注册 {registered_tools} 个接口查询工具")

if registered_tools == 0:
    log.warning("未注册任何工具，请检查 OpenAPI 规范文件")

if __name__ == "__main__":
    try:
        log.info("启动 OpenAPI MCP 服务器...")
        mcp.run(transport="sse")
    except KeyboardInterrupt:
        log.info("接收到中断信号，正在关闭服务器...")
    except Exception as e:
        log.error(f"服务器运行时发生错误: {e}")
        exit(1)