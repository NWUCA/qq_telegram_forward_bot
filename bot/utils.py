import re
import json
import html

from django.conf import settings


def find_forward(id):
    forward = None
    for f in settings.FORWARD_LIST:
        if f.qq == id or f.tg == id:
            forward = f
    return forward
