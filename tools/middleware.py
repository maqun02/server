from django.utils.deprecation import MiddlewareMixin

class CloseCsrfMiddleware(MiddlewareMixin):
    """
    自定义中间件，用于禁用CSRF保护
    通过设置request.csrf_processing_done = True使Django跳过CSRF验证
    """
    def process_request(self, request):
        request.csrf_processing_done = True  # csrf处理完毕 