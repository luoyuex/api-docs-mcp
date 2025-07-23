import json
import os
import logging
from typing import List, Dict, Any
from mcp.types import Tool

log = logging.getLogger(__name__)

def validate_openapi_spec(spec: Dict[str, Any]) -> bool:
    """验证 OpenAPI 规范的基本格式"""
    required_fields = ['openapi', 'info', 'paths']
    
    for field in required_fields:
        if field not in spec:
            log.error(f"OpenAPI 规范缺少必需字段: {field}")
            return False
    
    # 检查 OpenAPI 版本
    openapi_version = spec.get('openapi', '')
    if not openapi_version.startswith('3.'):
        log.warning(f"不支持的 OpenAPI 版本: {openapi_version}，建议使用 3.x 版本")
    
    # 检查 info 字段
    info = spec.get('info', {})
    if not isinstance(info, dict) or not info.get('title'):
        log.error("OpenAPI info 字段格式不正确或缺少 title")
        return False
    
    # 检查 paths 字段
    paths = spec.get('paths', {})
    if not isinstance(paths, dict) or not paths:
        log.error("OpenAPI paths 字段为空或格式不正确")
        return False
    
    log.info(f"验证通过：{info.get('title')} v{info.get('version', 'unknown')}，包含 {len(paths)} 个路径")
    return True

def load_openapi_spec(spec_path: str) -> List[Tool]:
    """Loads an OpenAPI specification and extracts tool definitions."""
    if not os.path.exists(spec_path):
        log.error(f"OpenAPI 规范文件不存在: {spec_path}")
        return []

    try:
        with open(spec_path, "r", encoding='utf-8') as f:
            spec = json.load(f)
    except json.JSONDecodeError as e:
        log.error(f"无法解析 JSON 文件 {spec_path}: {e}")
        return []
    except Exception as e:
        log.error(f"读取文件 {spec_path} 时发生错误: {e}")
        return []
    
    # 验证 OpenAPI 规范格式
    if not validate_openapi_spec(spec):
        log.error(f"OpenAPI 规范验证失败: {spec_path}")
        return []

    tools = []
    paths = spec.get("paths", {})
    
    total_endpoints = sum(len(methods) for methods in paths.values())
    log.info(f"开始加载 {total_endpoints} 个接口定义...")

    for path, path_details in paths.items():
        if not isinstance(path_details, dict):
            log.warning(f"跳过无效的路径定义: {path}")
            continue
            
        for method, details in path_details.items():
            if method.lower() not in ['get', 'post', 'put', 'delete', 'patch', 'head', 'options']:
                continue  # 跳过非HTTP方法（如 parameters、servers 等）
                
            if not isinstance(details, dict):
                log.warning(f"跳过无效的接口定义: {method.upper()} {path}")
                continue
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

            try:
                tool = Tool(
                    name=details.get("operationId") or f"{method.upper()} {path}",
                    description=details.get("summary", f"{method.upper()} {path}"),
                    inputSchema=input_schema,
                    outputSchema=output_schema,
                )
                tools.append(tool)
                log.debug(f"成功加载工具: {tool.name}")
            except Exception as e:
                log.error(f"创建工具时发生错误 ({method.upper()} {path}): {e}")
                continue

    log.info(f"成功从 {spec_path} 加载 {len(tools)} 个工具")
    return tools
