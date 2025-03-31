# EdgePlugHub 后端服务

EdgePlugHub后端服务，提供插件管理API和用户认证服务。

## 功能特点

- RESTful API接口
- 插件上传和下载
- 用户认证和权限控制
- 插件搜索和管理

## 快速开始

### 直接运行

```bash
# 克隆仓库
git clone https://github.com/EdgeAIHub2024/edgeplughub-backend.git
cd edgeplughub-backend

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
export FLASK_APP=app.py
export JWT_SECRET_KEY=your-secret-key

# 初始化数据库
flask db upgrade

# 运行服务
flask run --host=0.0.0.0 --port=5000
```

### Docker部署

```bash
# Docker容器运行
docker build -t edgeplughub-backend .
docker run -d -p 5000:5000 \
  -e JWT_SECRET_KEY=your-secret-key \
  -v ./data:/app/data \
  --name edgeplughub-backend \
  edgeplughub-backend

# 使用Docker Compose
docker-compose up -d
```

## API端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/plugins` | GET | 获取插件列表 |
| `/api/plugins/<id>` | GET | 获取插件详情 |
| `/api/plugins/download/<id>` | GET | 下载插件 |
| `/api/plugins/upload` | POST | 上传新插件 |
| `/api/auth/login` | POST | 用户登录 |
| `/api/auth/register` | POST | 用户注册 |

## 配置

### 环境变量

- `DATABASE_URL`: 数据库连接地址 (默认: sqlite:///edgeplughub.db)
- `JWT_SECRET_KEY`: JWT密钥，必须设置
- `UPLOAD_FOLDER`: 插件上传目录 (默认: uploads)
- `LOG_LEVEL`: 日志级别 (默认: INFO)

## 项目结构

```
edgeplughub-backend/
├── app.py              # 应用入口
├── api/                # API接口
│   ├── auth.py         # 认证相关
│   └── plugins.py      # 插件相关
├── models/             # 数据模型
├── utils/              # 工具函数
├── config.py           # 配置文件
├── requirements.txt    # 依赖列表
└── Dockerfile          # Docker配置
```

## 开发

### 需求

- Python 3.7+
- Flask
- SQLAlchemy
- JWT

### 测试

```bash
pytest
```

## 许可证

MIT - 详情参阅[LICENSE](LICENSE)文件。 