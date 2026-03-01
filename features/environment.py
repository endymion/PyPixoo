"""Behave hooks for PyPixoo specs."""

import requests
from unittest.mock import MagicMock, patch


def _mock_response(json_data):
    resp = MagicMock()
    resp.json.return_value = json_data
    return resp


def before_all(context):
    """Mock device HTTP so specs run without a real Pixoo on the network."""

    def fake_post(url, data=None, **kwargs):
        mode = getattr(context, "mock_mode", "success")
        if mode == "validate_fail" and data and "Channel/GetAllConf" in str(data):
            raise requests.exceptions.RequestException("mock network failure")
        if mode == "load_counter_fail" and data and "GetHttpGifId" in str(data):
            return _mock_response({"error_code": 1})
        if mode == "push_fail" and data and "SendHttpGif" in str(data):
            return _mock_response({"error_code": 1})
        return _mock_response({"error_code": 0, "PicId": 1})

    context._post_patcher = patch("pypixoo.pixoo.requests.post", side_effect=fake_post)
    context._post_patcher.start()


def before_scenario(context, scenario):
    """Set mock mode from scenario tags for failure-path coverage."""
    context.mock_mode = "success"
    if "mock_validate_fail" in scenario.tags:
        context.mock_mode = "validate_fail"
    elif "mock_load_counter_fail" in scenario.tags:
        context.mock_mode = "load_counter_fail"
    elif "mock_push_fail" in scenario.tags:
        context.mock_mode = "push_fail"


def after_all(context):
    context._post_patcher.stop()
