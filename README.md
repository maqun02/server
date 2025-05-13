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

# 网站组件识别系统

基于Django + Scrapy的网站技术组件识别系统。

## 主要功能

1. 多层次爬虫架构，按序执行：
   - 链接爬虫：抓取网站内的链接（内链、外链、nofollow链接）
   - 内容爬虫：使用Splash进行动态渲染，抓取HTML内容和静态资源链接
   - 资源爬虫：抓取静态资源（JS、CSS、图片等）并计算MD5哈希
   - 指纹匹配：对所有内容进行组件指纹匹配

2. 两种爬取模式：
   - 简单模式：仅爬取给定链接
   - 深度模式：爬取给定链接及其内部链接

3. 分布式爬取：
   - 使用Redis作为消息队列
   - 支持横向扩展爬虫实例

4. 动态渲染：
   - 使用Splash进行JavaScript渲染
   - 捕获AJAX加载的内容和资源

5. 组件识别：
   - 基于Aho-Corasick算法的高效多模式匹配
   - 支持HTML、JavaScript、CSS中的组件识别
   - 图片和图标使用MD5哈希进行匹配

## 技术架构

- 后端框架：Django + DRF
- 爬虫框架：Scrapy + Scrapy-Redis + Scrapy-Splash
- 消息队列：Redis
- 动态渲染：Splash
- 数据库：MySQL

## 数据模型

- 任务（CrawlerTask）：爬取任务信息
- 链接（CrawlerLink）：存储所有链接信息
- 内容（CrawlerResult）：存储页面内容和响应头
- 资源（StaticResource）：存储静态资源内容和MD5哈希
- 组件（IdentifiedComponent）：存储识别出的组件信息
- 指纹（Fingerprint）：存储组件指纹库

## 爬取流程

1. 用户创建爬取任务，指定URL和模式（简单/深度）
2. 系统启动链接爬虫，收集所有链接
3. 内容爬虫使用Splash渲染页面，抓取内容和静态资源链接
4. 资源爬虫下载所有静态资源，计算MD5哈希
5. 指纹匹配爬虫对所有内容和资源进行组件匹配
6. 结果保存到数据库，前端可查看识别的组件

## 部署要求

- Python 3.8+
- Redis 6.0+
- MySQL 8.0+
- Splash 3.0+

## 安装步骤

1. 克隆代码仓库
2. 安装依赖：`pip install -r requirements.txt`
3. 配置数据库和Redis连接
4. 运行迁移：`python manage.py migrate`
5. 启动开发服务器：`python manage.py runserver`

## 使用Docker

```bash
docker-compose up -d
```

## 环境变量

- `REDIS_HOST`: Redis服务器地址（默认：localhost）
- `REDIS_PORT`: Redis端口（默认：6379）
- `SPLASH_URL`: Splash服务URL（默认：http://splash:8050） 