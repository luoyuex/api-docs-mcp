### api-doce-mcp
#### 概述
用于读取接口文档的信息，自动读取 OpenAPI 文档，apifox等平台可导出OpenAPI Spec 版本的json，替换apidocs.json即可
每个 OpenAPI 接口会自动注册为一个 MCP 工具（Tool）。
工具的参数签名、类型、描述等全部根据 OpenAPI schema 自动生成，客户端（如 Trae、Claude、Cursor）可以自动识别和展示每个参数的详细信息。每个接口还会自动注册一个 schema 查询工具（如 get_login_schema），用于返回该接口的参数字段、类型、是否必填、备注等结构化信息。这样 AI/用户可以直接查询接口需要哪些字段，而不是盲目调用接口。
只需维护 OpenAPI 文档，无需手动注册工具或维护参数列表。新增/修改接口只需更新 apidocs.json，服务端自动适配。

### MCP配置
```json
{
  "mcpServers": {
    "OpenAPI Python MCP (SSE Only)": {
      "url": "http://127.0.0.1:8000/sse"
    }
  }
}
```

### 使用案例
查看mcp的登录接口返回的字段信息，然后根据字段信息实现 LoginScreen.js 登录功能，接口的实现和调用可以参考 HomeScreen.js


