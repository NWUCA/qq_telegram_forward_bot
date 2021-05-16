"""
QQ 和 Telegram 相关的 API, API 需要是非阻塞的
"""

from queue import Queue
from threading import Thread
from typing import Literal, Callable, Union
from collections import namedtuple
import functools
import logging
import re
import html
import json

import telebot
from telebot import types
from telebot.types import InputMediaPhoto
import requests
from django.conf import settings

from .models import Message, GroupCard, User
from .utils import find_forward

logger = logging.getLogger(__name__)

telegram_bot = telebot.TeleBot(settings.TELEGRAM_API_TOKEN)
Task = namedtuple('Task', 'func args kwargs')
q = Queue()


def worker():
    task: Task = q.get()
    task.func(*task.args, **task.kwargs)


t = Thread(target=worker)
t.start()
# FIXME 何时线程结束..


def concurrent(func: Callable[..., None]):  # FIXME: 这个 type hint 似乎没有用..
    """
    该装饰器包装的方法不会阻塞
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        q.put(Task(func, args, kwargs))

    return wrapper


def process_qq_json_message(message: str):
    match = re.search(r"\[CQ:json,data=(.*?)]", message)

    if not match:
        return

    data = match[1]
    data = html.unescape(data)
    data = json.loads(data)['meta']
    if data.get('detail_1'):
        data = data['detail_1']
        return f"标题: {data.get('title', '')}\n描述: {data.get('desc', '')}\n{data.get('qqdocurl', '')}"
    if data.get('news'):
        data = data['news']
        return f"标题: {data.get('title', '')}\n{data.get('jumpUrl', '')}"


def process_qq_image(message: str):
    image_re = re.compile(r"\[CQ:image,file=(.*?),url=(.*?)]")
    image_urls = list(map(lambda a: a[1], re.findall(image_re, message)))
    text = re.sub(image_re, lambda a: " ", message)
    return image_urls, text


@concurrent
def forward_to_tg(data):
    if data['post_type'] != 'message':
        return

    if data['message_type'] != 'group':
        return

    forward = find_forward(data['group_id'])
    if not forward:
        return

    sender = data['sender']
    user, _ = User.objects.get_or_create(
        qq_id=data['user_id'],
        defaults={'qq_nickname': sender.get('nickname')}
    )

    card, _ = GroupCard.objects.update_or_create(
        user=user,
        group=forward.qq,
        defaults={'card': sender.get('card')},
    )

    message = Message.objects.create(
        message_id_qq=data['message_id'],
        qq_group_id=data['group_id'],
        user=user
    )

    msg_prefix = f"[{card.card}({user.qq_nickname})]:"

    image_urls, text = process_qq_image(data['message'])
    if image_urls:
        medias = [InputMediaPhoto(url) for url in image_urls]
        msg = f"{msg_prefix} {text}"
        medias[0].caption = msg  # 插入消息内容
        tg_message = telegram_bot.send_media_group(forward.tg, medias)
        message.message_id_tg = tg_message[0].id
        message.save()
        return

    if resolved_json_msg := process_qq_json_message(data['message']):
        data['message'] = resolved_json_msg
    msg = f"{msg_prefix} {data['message']}"
    tg_message = telegram_bot.send_message(forward.tg, msg)
    message.message_id_tg = tg_message.id
    message.save()


@concurrent
def forward_to_qq(data):
    update = types.Update.de_json(data)
    tg_message: types.Message = update.message

    if tg_message.chat.type not in ('group', 'supergroup'):
        return

    forward = find_forward(tg_message.chat.id)
    if not forward:
        return

    text = tg_message.text
    tg_user = tg_message.from_user
    if text and text.startswith('/bind'):
        qq_id = text.split(' ')[1]
        try:
            user = User.objects.get(qq_id=qq_id)

            try:
                User.objects.get(telegram_id=tg_user.id).delete()
            except User.DoesNotExist:
                pass

            user.telegram_id = tg_user.id
            user.save()
        except User.DoesNotExist:
            pass
        return

    user, _ = User.objects.get_or_create(
        telegram_id=tg_user.id,
        defaults={
            'telegram_username': tg_user.username,
            'telegram_name': f"{tg_user.first_name} {tg_user.last_name}",
        }
    )

    message = Message.objects.create(
        message_id_tg=tg_message.id,
        qq_group_id=forward.qq,
        user=user
    )

    payload: dict[str, Union[int, str]] = {"message": tg_message.text, 'group_id': forward.qq}
    r = requests.post(settings['COOLQ_API_ADDRESS'].format('send_msg'), json=payload)

    message.message_id_qq = r.json()['message_id']
    message.save()
