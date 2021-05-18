"""
QQ 和 Telegram 相关的 API, API 需要是非阻塞的
"""
import functools
import html
import json
import logging
import re
from collections import namedtuple
from queue import Queue
from threading import Thread
from typing import Any, Callable, Union

import requests
import telebot
from django.conf import settings
from telebot import types
from telebot.types import InputMediaPhoto

from .models import GroupCard, Message, User
from .utils import find_forward

logger = logging.getLogger(__name__)

telegram_bot = telebot.TeleBot(settings.TELEGRAM_API_TOKEN)
Task = namedtuple('Task', 'func args kwargs')
q: Any = Queue()


def worker():
    while True:
        task: Task = q.get()
        if q.qsize() > 0:
            logger.warning(f"The queue has approximate remaining {q.qsize()} task(s).")
        try:
            task.func(*task.args, **task.kwargs)
        except Exception as e:
            import traceback

            traceback.print_exc()
            logger.critical(e)


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

    data: Any = match[1]
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
    text = re.sub(image_re, lambda a: "", message)
    return image_urls, text


def process_qq_reply(message: str):
    reply_re = re.compile(r"\[CQ:reply,id=(.*?)]")

    match = re.search(reply_re, message)
    if not match:
        return None, None

    message_id = match[1]
    text = re.sub(reply_re, lambda a: "", message)
    try:
        message = Message.objects.get(message_id_qq=message_id)
    except Message.DoesNotExist:
        message = None
    return message, text


def process_at(message: str, forward):
    at_re = re.compile(r"\[CQ:at,qq=(.*?)]")

    match = re.search(at_re, message)
    if not match:
        return message

    at_id = match[1]
    try:
        at_user = User.objects.get(qq_id=at_id)
        text = re.sub(at_re, lambda a: f"@{at_user.qq_prefix(forward.qq)}", message)
        return text
    except User.DoesNotExist:
        return message


# TODO: 无法播放动图
@concurrent
def forward_to_tg(data):
    # 处理撤回事件
    if data['post_type'] == 'notice' and data['notice_type'] == 'group_recall':
        recalled_message = Message.objects.get(message_id_qq=data['message_id'])
        if recalled_message.user.qq_id == data['operator_id']:
            msg = f"{recalled_message.user.qq_prefix(data['group_id'])}撤回了这条消息"
        else:
            operator = User.objects.get(qq_id=data['operator_id'])
            msg = f"{operator.qq_prefix(data['group_id'])}撤回了这条成员消息"

        forward = find_forward(data['group_id'])
        if not forward:
            return

        telegram_bot.send_message(
            forward.tg, msg, reply_to_message_id=recalled_message.message_id_tg
        )

    if data['post_type'] != 'message':
        return

    if data['message_type'] != 'group':
        return

    forward = find_forward(data['group_id'])
    if not forward:
        return

    sender = data['sender']
    user, _ = User.objects.update_or_create(
        qq_id=data['user_id'], defaults={'qq_nickname': sender.get('nickname')}
    )

    card, _ = GroupCard.objects.update_or_create(
        user=user,
        group=forward.qq,
        defaults={'card': sender.get('card')},
    )

    message = Message.objects.create(
        message_id_qq=data['message_id'], qq_group_id=data['group_id'], user=user
    )

    msg_prefix = f"[{card.card}({user.qq_nickname})]:"

    reply_message, text = process_qq_reply(data['message'])
    if reply_message:
        reply_to_message_id = reply_message.message_id_tg
        data['message'] = text
    else:
        reply_to_message_id = None

    data['message'] = process_at(data['message'], forward)

    image_urls, text = process_qq_image(data['message'])
    if image_urls:
        medias = [InputMediaPhoto(url) for url in image_urls]
        msg = f"{msg_prefix} {text}"
        medias[0].caption = msg  # 插入消息内容
        logger.info(f"Invoking tg api, sending to {forward.tg}, media is: {medias}")
        tg_message = telegram_bot.send_media_group(
            forward.tg, medias, reply_to_message_id=reply_to_message_id
        )
        logger.info(f"tg api returned: {tg_message}")
        message.message_id_tg = tg_message[0].id
        message.save()
        return

    if resolved_json_msg := process_qq_json_message(data['message']):
        data['message'] = resolved_json_msg
    msg = f"{msg_prefix} {data['message']}"
    logger.info(f"Invoking tg api, sending to {forward.tg}, msg is: {msg}")
    tg_message = telegram_bot.send_message(
        forward.tg, msg, reply_to_message_id=reply_to_message_id
    )
    logger.info(f"tg api returned: {tg_message}")
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

    user, _ = User.objects.update_or_create(
        telegram_id=tg_user.id,
        defaults={
            'telegram_username': tg_user.username,
            'telegram_name': f"{tg_user.first_name} {tg_user.last_name if tg_user.last_name else ''}",
        },
    )

    message = Message.objects.create(
        message_id_tg=tg_message.id, qq_group_id=forward.qq, user=user
    )

    if tg_message.reply_to_message:
        reply_message = Message.objects.get(
            message_id_tg=tg_message.reply_to_message.message_id
        )
        msg = f"[CQ:reply,id={reply_message.message_id_qq}]"
    else:
        msg = ''

    msg += f"{user.qq_prefix_fallback(forward.qq)}: "
    if tg_message.content_type == 'text':
        msg += tg_message.text
    elif tg_message.content_type in ('sticker', 'photo'):
        if tg_message.sticker:
            arr = [tg_message.sticker.thumb]
        else:
            arr = tg_message.photo  # FIXME: 会发两张图
        cq_code_msg = ""
        for file in arr:
            tg_file = telegram_bot.get_file(file.file_id)
            path = f"https://api.telegram.org/file/bot{settings.TELEGRAM_API_TOKEN}/{tg_file.file_path}"
            cq_code_msg += f"[CQ:image,file={path}]"
        msg += cq_code_msg
        if tg_message.caption:
            msg += tg_message.caption
    else:
        msg += f"不支持的消息类型, content_type: {tg_message.content_type}"

    payload: dict[str, Union[int, str]] = {"message": msg, 'group_id': forward.qq}
    logger.info(f"Invoking coolq api, payload is {payload}")
    r = requests.post(settings.COOLQ_API_ADDRESS.format('send_msg'), json=payload)
    logger.info(f"coolq api result: {r.json()}")

    message.message_id_qq = r.json()['data']['message_id']
    message.save()
