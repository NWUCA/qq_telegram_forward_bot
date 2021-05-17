"""
负责 request 的处理
"""
import logging

from rest_framework.decorators import api_view
from rest_framework.response import Response

from .api import forward_to_qq, forward_to_tg

logger = logging.getLogger(__name__)


@api_view(['POST'])
def qq_event(request):
    data = request.data
    logger.info(f"QQ event, data: {data}")
    forward_to_tg(data)

    return Response()


@api_view(['POST'])
def telegram_event(request):
    data = request.data
    logger.info(f"Telegram event, data: {data}")
    forward_to_qq(data)

    return Response()
