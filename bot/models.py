from django.db import models


class User(models.Model):
    qq_id = models.BigIntegerField(unique=True, null=True)
    telegram_id = models.BigIntegerField(unique=True, null=True)
    qq_nickname = models.TextField()
    telegram_username = models.TextField()
    telegram_name = models.TextField()


class GroupCard(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    group = models.BigIntegerField(verbose_name="QQ 群号")
    card = models.TextField()


class Message(models.Model):
    """表示一条消息, 不存储具体内容, 用于回复, 撤回等功能"""
    message_id_qq = models.BigIntegerField(null=True)
    message_id_tg = models.TextField(null=True)
    qq_group_id = models.BigIntegerField(help_text='QQ 群号')
    deleted = models.BooleanField(default=False, help_text='是否被撤回')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    time = models.DateTimeField(auto_now_add=True)

