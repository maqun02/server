# This package will contain the spiders of your Scrapy project
#
# Please refer to the documentation for information on how to create and manage
# your spiders.
import os
import sys
import django

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

# 设置Django环境
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")
django.setup()

# 现在可以导入Django模型
from tasks.models import CrawlerTask
from results.models import CrawlerLink, CrawlerResult, StaticResource
from logs.utils import log_action
