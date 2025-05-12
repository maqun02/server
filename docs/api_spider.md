# 爬虫引擎 API 文档

本文档描述了Web组件识别系统爬虫引擎的API接口。这些接口允许前端应用程序控制爬虫任务、查询任务状态和管理爬虫队列。

## 基本信息

- 基础URL: `/api/scrapy/`
- 所有接口都需要身份验证
- 响应格式: JSON

## 认证

所有API调用都需要身份验证，支持以下认证方式:

- Token认证: 在请求头中包含 `Authorization: Token <your_token>`
- Session认证: 通过Django会话认证系统

## 接口列表

### 1. 获取爬虫系统统计信息

获取整个爬虫系统的运行状态和统计信息。

- **URL**: `/api/scrapy/stats/`
- **方法**: `GET`
- **权限**: 仅管理员
- **响应示例**:

```json
{
    "tasks": {
        "total": 42,
        "active": 3,
        "completed": 37,
        "failed": 2
    },
    "data": {
        "links": 1250,
        "pages": 845,
        "resources": 2156,
        "components": 128
    },
    "redis": {
        "status": "已连接",
        "host": "redis",
        "port": 6379,
        "keys": 57
    }
}
```

### 2. 启动爬虫任务

启动一个排队中或失败的爬虫任务。

- **URL**: `/api/scrapy/{task_id}/start_crawl/`
- **方法**: `POST`
- **权限**: 任务所有者或管理员
- **响应示例**:

```json
{
    "success": true,
    "message": "爬虫任务已成功启动",
    "task": {
        "id": 123,
        "url": "https://example.com",
        "status": "link_crawling",
        "mode": "deep",
        "created_at": "2023-11-01T12:00:00Z"
    }
}
```

### 3. 停止爬虫任务

强制停止一个正在运行的爬虫任务。

- **URL**: `/api/scrapy/{task_id}/stop_crawl/`
- **方法**: `POST`
- **权限**: 任务所有者或管理员
- **响应示例**:

```json
{
    "success": true,
    "message": "爬虫任务已停止",
    "task": {
        "id": 123,
        "url": "https://example.com",
        "status": "failed",
        "mode": "deep",
        "created_at": "2023-11-01T12:00:00Z"
    }
}
```

### 4. 重启爬虫任务

清空任务相关的所有数据并重新开始爬取。

- **URL**: `/api/scrapy/{task_id}/restart_crawl/`
- **方法**: `POST`
- **权限**: 任务所有者或管理员
- **响应示例**:

```json
{
    "success": true,
    "message": "爬虫任务已成功重启",
    "task": {
        "id": 123,
        "url": "https://example.com",
        "status": "link_crawling",
        "mode": "deep",
        "created_at": "2023-11-01T12:00:00Z"
    }
}
```

### 5. 获取任务状态

获取指定爬虫任务的详细状态和进度信息。

- **URL**: `/api/scrapy/{task_id}/status/`
- **方法**: `GET`
- **权限**: 任务所有者或管理员
- **响应示例**:

```json
{
    "task_id": 123,
    "url": "https://example.com",
    "status": "content_crawling",
    "status_display": "内容爬取中",
    "mode": "deep",
    "mode_display": "完整模式",
    "started_at": "2023-11-01T12:05:23Z",
    "ended_at": null,
    "stats": {
        "links_total": 35,
        "links_crawled": 12,
        "resources_total": 45,
        "resources_crawled": 0,
        "components_identified": 0,
        "progress": 32
    }
}
```

### 6. 获取任务识别的组件

获取指定任务识别的所有组件列表。

- **URL**: `/api/scrapy/{task_id}/components/`
- **方法**: `GET`
- **权限**: 任务所有者或管理员
- **参数**:
  - `component` (可选): 查询特定组件的详细信息
- **响应示例**:

```json
{
    "task_id": 123,
    "components": [
        {"component": "jQuery", "count": 5},
        {"component": "Bootstrap", "count": 3},
        {"component": "React", "count": 2}
    ],
    "total": 3
}
```

如果指定了component参数:

```json
{
    "component": "jQuery",
    "total_matches": 5,
    "match_details": [
        {"match_type": "js", "keyword": "jquery-3.6.0.min.js", "count": 3},
        {"match_type": "html", "keyword": "jquery", "count": 2}
    ],
    "urls": [
        "https://example.com/index.html",
        "https://example.com/about.html"
    ]
}
```

### 7. 获取队列状态

获取指定任务的Redis队列状态。

- **URL**: `/api/scrapy/{task_id}/queue_stats/`
- **方法**: `GET`
- **权限**: 任务所有者或管理员
- **响应示例**:

```json
{
    "task_id": 123,
    "queues": {
        "task:123:abc12345:link_spider:start_urls": 5,
        "task:123:abc12345:content_spider:start_urls": 12
    },
    "total_keys": 2
}
```

### 8. 手动运行指纹匹配

为指定任务手动触发指纹匹配过程。

- **URL**: `/api/scrapy/{task_id}/run_fingerprint_matching/`
- **方法**: `POST`
- **权限**: 任务所有者或管理员
- **响应示例**:

```json
{
    "success": true,
    "message": "指纹匹配过程已启动",
    "task": {
        "id": 123,
        "url": "https://example.com",
        "status": "fingerprint_matching",
        "mode": "deep",
        "created_at": "2023-11-01T12:00:00Z"
    }
}
```

### 9. 内容指纹匹配

对提供的内容进行组件指纹匹配。

- **URL**: `/api/scrapy/match_content/`
- **方法**: `POST`
- **权限**: 已认证用户
- **参数**:
  - `content` (必填): 需要匹配的内容文本
  - `reload_fingerprints` (可选): 是否重新加载指纹库，默认为false
- **请求示例**:

```json
{
    "content": "<html><body><script src=\"jquery-3.6.0.min.js\"></script></body></html>",
    "reload_fingerprints": false
}
```

- **响应示例**:

```json
{
    "success": true,
    "content_length": 71,
    "content_preview": "<html><body><script src=\"jquery-3.6.0.min.js\"></script></body></html>",
    "fingerprints_count": 150,
    "matches": [
        {"component": "jQuery", "keyword": "jquery-3.6.0.min.js"}
    ],
    "matches_count": 1
}
```

### 10. 获取指纹库统计信息

获取指纹库和匹配算法的统计信息。

- **URL**: `/api/scrapy/fingerprint_stats/`
- **方法**: `GET`
- **权限**: 已认证用户
- **响应示例**:

```json
{
    "total": 200,
    "approved": 150,
    "pending": 45,
    "rejected": 5,
    "matcher": {
        "is_loaded": true,
        "fingerprints_loaded": 150,
        "simple_fingerprints": 150,
        "use_simple_matching": true
    }
}
```

## 错误响应

API在遇到错误时会返回相应的HTTP状态码和描述错误的JSON对象:

```json
{
    "success": false,
    "message": "错误描述信息"
}
```

常见状态码:

- `400 Bad Request`: 请求参数错误
- `401 Unauthorized`: 未认证
- `403 Forbidden`: 没有权限
- `404 Not Found`: 资源不存在
- `500 Internal Server Error`: 服务器内部错误

## 使用示例

### 启动一个爬虫任务并监控进度

```javascript
// 1. 启动爬虫任务
fetch('/api/scrapy/123/start_crawl/', {
  method: 'POST',
  headers: {
    'Authorization': 'Token your_token_here',
    'Content-Type': 'application/json'
  }
})
.then(response => response.json())
.then(data => {
  console.log('任务已启动:', data);
  
  // 2. 定期检查任务状态
  const statusCheck = setInterval(() => {
    fetch('/api/scrapy/123/status/', {
      headers: {
        'Authorization': 'Token your_token_here'
      }
    })
    .then(response => response.json())
    .then(status => {
      console.log('当前进度:', status.stats.progress + '%');
      
      // 任务完成后停止检查
      if (status.status === 'completed' || status.status === 'failed') {
        clearInterval(statusCheck);
        console.log('任务已结束，状态:', status.status_display);
        
        // 3. 获取识别的组件
        if (status.status === 'completed') {
          fetch('/api/scrapy/123/components/', {
            headers: {
              'Authorization': 'Token your_token_here'
            }
          })
          .then(response => response.json())
          .then(components => {
            console.log('识别到的组件:', components);
          });
        }
      }
    });
  }, 5000); // 每5秒检查一次
});
``` 