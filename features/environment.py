"""Behave hooks for PyPixoo specs."""

import base64
import json
import os

import requests
from unittest.mock import MagicMock, patch


def _mock_response(json_data):
    resp = MagicMock()
    resp.json.return_value = json_data
    return resp


def before_all(context):
    """Mock device HTTP so specs run without a real Pixoo on the network.
    Set PIXOO_REAL_DEVICE=1 to disable mocking for @real_device scenarios."""
    context._real_device = os.environ.get("PIXOO_REAL_DEVICE") == "1"
    if context._real_device:
        context._post_patcher = None
        return

    def fake_post(url, data=None, **kwargs):
        mode = getattr(context, "mock_mode", "success")
        if mode == "validate_fail" and data and "Channel/GetAllConf" in str(data):
            raise requests.exceptions.RequestException("mock network failure")
        if mode == "load_counter_fail" and data and "GetHttpGifId" in str(data):
            return _mock_response({"error_code": 1})
        if mode == "push_fail" and data and "SendHttpGif" in str(data):
            return _mock_response({"error_code": 1})
        if "SendHttpGif" in str(data):
            try:
                payload = json.loads(data) if isinstance(data, str) else data
                pic_data = payload.get("PicData", "")
                raw = base64.b64decode(pic_data)
                history = getattr(context, "_push_history", None)
                if history is not None:
                    history.append(list(raw))
            except (json.JSONDecodeError, TypeError, KeyError):
                pass
        return _mock_response({"error_code": 0, "PicId": 1})

    context._push_history: list = []
    context._post_patcher = patch("pypixoo.pixoo.requests.post", side_effect=fake_post)
    context._post_patcher.start()


def before_scenario(context, scenario):
    """Set mock mode from scenario tags for failure-path coverage."""
    context.mock_mode = "success"
    if hasattr(context, "_push_history"):
        context._push_history.clear()
    if "mock_validate_fail" in scenario.tags:
        context.mock_mode = "validate_fail"
    elif "mock_load_counter_fail" in scenario.tags:
        context.mock_mode = "load_counter_fail"
    elif "mock_push_fail" in scenario.tags:
        context.mock_mode = "push_fail"


def after_all(context):
    if context._post_patcher is not None:
        context._post_patcher.stop()
