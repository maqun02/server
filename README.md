# 基于指纹匹配的Web组件识别系统

这是一个基于Django框架开发的Web组件识别系统，使用Aho-Corasick算法进行高效的多模式匹配，帮助用户快速识别网站中使用的组件。

## 系统功能

- **用户管理**：区分管理员和普通用户权限
- **指纹库管理**：提交、审核、查询组件指纹
- **网站爬虫**：支持简单模式和深度模式的网站爬行
- **组件识别**：使用高效的Aho-Corasick算法进行多模式匹配
- **结果展示**：展示识别结果并支持报告生成
- **日志系统**：记录系统操作和事件

## 系统架构

- **用户模块 (users)**：管理用户账户和权限
- **指纹库模块 (fingerprints)**：管理组件指纹
- **爬虫任务模块 (tasks)**：创建和管理爬虫任务
- **结果模块 (results)**：存储和展示识别结果
- **日志模块 (logs)**：记录系统日志
- **爬虫引擎 (scrapy_engine)**：基于Scrapy框架的爬虫实现

## 部署方法

### 方法一：传统部署

1. 克隆代码库
2. 安装所需依赖:
   ```bash
   pip install -r requirements.txt
   ```
3. 执行部署脚本:
   ```bash
   bash deploy.sh
   ```

### 方法二：Docker部署

1. 使用Docker Compose一键部署:
   ```bash
   docker-compose up -d
   ```
   
这将启动Web应用、MySQL数据库和Redis服务。

## 环境要求

- Python 3.8+
- MySQL 5.7+
- Redis 6.0+ (用于分布式爬虫，可选)

## 启动方式
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
pkill -f "python manage.py runserver"或ctrl+c

## API文档

系统提供RESTful API接口，主要包括:

- `/api/users/` - 用户管理
- `/api/fingerprints/` - 指纹库管理
- `/api/tasks/` - 爬虫任务管理
- `/api/results/` - 识别结果查询
- `/api/logs/` - 系统日志查询

## 配置说明

编辑 `project/settings.py` 修改以下关键配置:

```python
# 数据库配置
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'fwf',
        'USER': 'username',
        'PASSWORD': 'password',
        'HOST': 'localhost',
        'PORT': '3306',
    }
}

# Redis配置 (用于分布式爬虫)
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
```

## 技术栈

- **后端框架**: Django, Django REST Framework
- **数据库**: MySQL
- **爬虫框架**: Scrapy
- **分布式支持**: Redis, Scrapy-Redis
- **核心算法**: Aho-Corasick多模式匹配算法

## 许可证

项目采用[MIT许可证](LICENSE) 