# EdgePlugHub API 文档

## 基本信息

- **Base URL**: `http://localhost:5000/api`
- **格式**: 所有请求和响应均使用JSON格式
- **认证**: 大部分API使用JWT认证，需要在请求头中包含`Authorization: Bearer <token>`

## 1. 认证 API

### 1.1 用户注册

- **URL**: `/auth/register`
- **方法**: `POST`
- **认证**: 不需要
- **请求体**:
  ```json
  {
    "username": "example_user",
    "email": "user@example.com",
    "password": "securepassword"
  }
  ```
- **响应**: 
  - **成功** (201): `{"msg": "User registered successfully"}`
  - **错误** (400): `{"msg": "Missing required fields"}`
  - **错误** (409): `{"msg": "Username already exists"}` 或 `{"msg": "Email already exists"}`

### 1.2 用户登录

- **URL**: `/auth/login`
- **方法**: `POST`
- **认证**: 不需要
- **请求体**:
  ```json
  {
    "username": "example_user",
    "password": "securepassword"
  }
  ```
- **响应**: 
  - **成功** (200): `{"access_token": "<JWT_TOKEN>", "user_id": "<USER_ID>"}`
  - **错误** (400): `{"msg": "Missing username or password"}`
  - **错误** (401): `{"msg": "Bad username or password"}`

### 1.3 获取用户信息

- **URL**: `/auth/user`
- **方法**: `GET`
- **认证**: 需要
- **响应**: 
  - **成功** (200): 
    ```json
    {
      "id": "<USER_ID>",
      "username": "example_user",
      "email": "user@example.com",
      "is_admin": false
    }
    ```
  - **错误** (404): `{"msg": "User not found"}`

## 2. 插件 API

### 2.1 获取插件列表

- **URL**: `/plugins`
- **方法**: `GET`
- **认证**: 不需要
- **查询参数**:
  - `status`: 插件状态，默认为 "approved"
  - `category`: 插件类别，可选
- **响应**: 
  - **成功** (200): 返回插件对象数组

### 2.2 获取插件详情

- **URL**: `/plugins/<plugin_id>`
- **方法**: `GET`
- **认证**: 不需要
- **响应**: 
  - **成功** (200): 返回插件详情对象
  - **错误** (404): 未找到插件

### 2.3 下载插件

- **URL**: `/plugins/download/<plugin_id>`
- **方法**: `GET`
- **认证**: 不需要
- **响应**: 
  - **成功** (200): 插件zip文件
  - **错误** (404): 插件不存在
  - **错误** (403): `{"msg": "Plugin not available for download"}`

### 2.4 上传插件

- **URL**: `/plugins`
- **方法**: `POST`
- **认证**: 需要
- **Content-Type**: `multipart/form-data`
- **表单字段**:
  - `name`: 插件名称 (必填)
  - `short_description`: 简短描述 (必填)
  - `description`: 详细描述 (必填)
  - `version`: 版本号 (必填)
  - `category`: 类别 (必填)
  - `git_repo`: Git仓库URL (可选)
  - `requires_auth`: 是否需要认证，"true"或"false" (可选)
  - `icon`: 图标文件 (可选)
  - `package`: 插件包文件，必须是zip格式 (必填)
- **响应**: 
  - **成功** (201): 返回创建的插件对象
  - **错误** (400): `{"msg": "Missing required fields"}` 或 `{"msg": "No package file"}` 或 `{"msg": "File type not allowed"}`

### 2.5 审核插件

- **URL**: `/plugins/<plugin_id>/review`
- **方法**: `POST`
- **认证**: 需要 (管理员)
- **请求体**:
  ```json
  {
    "status": "approved" // 或 "rejected"
  }
  ```
- **响应**: 
  - **成功** (200): `{"msg": "Plugin status updated to approved"}`
  - **错误** (403): `{"msg": "Unauthorized"}`
  - **错误** (400): `{"msg": "Missing status field"}` 或 `{"msg": "Invalid status value"}`

## 3. 插件对象结构

```json
{
  "id": "string",
  "name": "string",
  "short_description": "string",
  "description": "string",
  "version": "string",
  "author": "string",
  "icon_url": "string 或 null",
  "category": "string",
  "created_at": "ISO日期字符串",
  "updated_at": "ISO日期字符串",
  "status": "string",
  "downloads": "number",
  "rating": "number",
  "git_repo": "string 或 null",
  "requires_auth": "boolean"
}
``` 