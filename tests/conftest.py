import pytest
import requests
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    pass


@pytest.fixture
def client():
    c = APIClient()
    return c


# @pytest.fixture(scope='session', autouse=True)
# def mock_requests(monkeypatch):
#     def mock_response():
#         r = requests.Response()
#         r.status_code = 200
#         return r
#
#     monkeypatch.setattr(requests, 'post', mock_response)


# FIXME
def mock_send_to_tg(requests_mock, app):
    def callback(request, context):
        res = {"message_id": -1, "date": "fake", "chat": None}
        if request.path.split('/')[-1] == 'sendmediagroup':
            res = [res]
        return {"ok": True, "result": res}

    requests_mock.post(
        app.config['TELEGRAM_API_ADDRESS'].format(app.config['TELEGRAM_API_TOKEN'], "sendMessage"),
        json=callback
    )
    requests_mock.get(
        app.config['TELEGRAM_API_ADDRESS'].format(app.config['TELEGRAM_API_TOKEN'], "sendMediaGroup"),
        json=callback
    )

