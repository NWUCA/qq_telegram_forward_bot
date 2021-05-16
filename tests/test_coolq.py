from datetime import datetime

from bot.models import Message, User


def data_generator(
    message,
    user_id: int = 1,
    time: datetime.isoformat = '2019-01-01 00:08:00',
    role: str = 'member',
    card: str = 'test_card',
    nickname: str = 'test_nickname',
    message_type: str = 'group',
    auto_prefix_slash: bool = True
):
    if auto_prefix_slash:
        message = "/" + message
    assert message_type in ('group', 'private')
    timestamp = datetime.fromisoformat(time).timestamp()
    data = {
        "anonymous": "None",
        "font": 1591808,
        "message": message,
        "message_id": 1,
        "message_type": message_type,
        "post_type": "message",
        "raw_message": message,
        "self_id": 0,
        "sender": {
            "age": 0,
            "area": "",
            "card": card,
            "level": "活跃",
            "nickname": nickname,
            "role": role,
            "sex": "unknown",
            "title": "头衔",
            "user_id": user_id
        },
        "sub_type": "normal",
        "time": timestamp,
        "user_id": user_id
    }
    if message_type == 'group':
        data["group_id"] = 102334415
    return data


def test_handle_qq_event(client):
    data = data_generator('test', auto_prefix_slash=False)
    r = client.post('/qq/', data)
    user = User.objects.all()[0]
    assert user.nickname == data['sender']['nickname']
    assert user.card_name == data['sender']['card']
    message = Message.objects.all()[0]
    assert message.type == data['message_type']


def test_help(client):
    response = client.post('/qq/', data_generator('help'))
    assert response.status_code == 200
    assert 'github' in response.data['reply']
    assert '/zao' in response.data['reply']
