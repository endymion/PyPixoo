"""Behave hooks for PyPixoo specs."""

from unittest.mock import MagicMock, patch


def _mock_response(json_data):
    resp = MagicMock()
    resp.json.return_value = json_data
    return resp


def before_all(context):
    """Mock device HTTP so specs run without a real Pixoo on the network."""

    def fake_post(url, data=None, **kwargs):
        # All device commands return success; GetHttpGifId needs PicId.
        return _mock_response({"error_code": 0, "PicId": 1})

    context._post_patcher = patch("pypixoo.pixoo.requests.post", side_effect=fake_post)
    context._post_patcher.start()


def after_all(context):
    context._post_patcher.stop()
