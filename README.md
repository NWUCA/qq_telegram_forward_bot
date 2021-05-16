# QQ Telegram Forward Bot
用于在 QQ 和 Telegram 群组之间转发消息.

QQ 机器人为[go-cqhttp](https://github.com/Mrs4s/go-cqhttp).

由于 Telegram Webhook 的需要, 该服务器需部署于国外. 并且需要反代设置域名并启用 HTTPS.

在 Telegram 端输入 `/bind qq号` 即可在 QQ 群的转发消息中显示自己的 QQ 昵称.

需要处理的消息类型有:
- 文字
- 图片
- 文件
- 视频
- 音频
- (仅 QQ) JSON 消息


## Deploy
```bash
gunicorn -b [domain:port] "bot.server:create_app()"
```
