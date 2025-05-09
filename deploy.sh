#!/bin/bash

# 基于指纹匹配的Web组件识别系统部署脚本
echo "开始部署组件识别系统..."

# 1. 清理不必要的文件
echo "清理Python缓存和临时文件..."
find . -name "__pycache__" -type d -exec rm -rf {} +
find . -name "*.pyc" -delete
find . -name "*.pyo" -delete
find . -name "*.pyd" -delete

# 可选：删除SQLite文件（如果已迁移到MySQL）
# rm -f db.sqlite3

# 2. 安装依赖
echo "安装依赖..."
pip install -r requirements.txt

# 3. 准备生产环境配置
echo "请确认您已在project/settings.py中修改以下设置:"
echo "- DEBUG = False"
echo "- 更新SECRET_KEY"
echo "- 正确配置ALLOWED_HOSTS"
echo "- 正确配置数据库连接信息"
read -p "配置已更新? (y/n) " config_updated
if [ "$config_updated" != "y" ]; then
    echo "请先更新配置后再继续"
    exit 1
fi

# 4. 收集静态文件
echo "收集静态文件..."
python manage.py collectstatic --noinput

# 5. 数据库迁移
echo "执行数据库迁移..."
python manage.py migrate

# 6. 创建超级管理员（如果需要）
read -p "是否需要创建超级管理员? (y/n) " create_admin
if [ "$create_admin" = "y" ]; then
    python manage.py createsuperuser
fi

# 7. 启动服务
echo "部署完成。您可以使用以下命令启动服务:"
echo "生产环境(使用Gunicorn):"
echo "gunicorn project.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120"
echo "开发环境(使用Django内置服务器):"
echo "python manage.py runserver 0.0.0.0:8000"

# 提醒安装Gunicorn(如果尚未安装)
echo "注意: 生产环境需要安装Gunicorn: pip install gunicorn" 