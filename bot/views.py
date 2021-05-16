"""
负责 request 的处理
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .api import forward_to_qq, forward_to_tg


@api_view(['POST'])
def qq_event(request):
    data = request.data
    forward_to_tg(data)

    return Response()


@api_view(['POST'])
def telegram_event(request):
    data = request.data
    forward_to_qq(data)

    return Response()
