from src.panwatch.secrets import SecretBox, mask_config


def test_secret_box_round_trips_without_plaintext_leak():
    box = SecretBox("a-development-secret-that-is-long-enough")
    plaintext = '{"api_key":"sk-secret","phone_numbers":["13800138000"]}'

    encrypted = box.encrypt(plaintext)

    assert "sk-secret" not in encrypted
    assert box.decrypt(encrypted) == plaintext


def test_mask_config_hides_sensitive_values():
    masked = mask_config(
        {
            "webhook_url": "https://open.feishu.cn/secret",
            "access_key_id": "AK123456",
            "access_key_secret": "very-secret",
            "phone_numbers": "13800138000",
            "sign_name": "盯盘侠",
        }
    )

    assert masked["webhook_url"] == "••••••••"
    assert masked["access_key_id"] == "••••••••"
    assert masked["access_key_secret"] == "••••••••"
    assert masked["phone_numbers"] == "••••••••"
    assert masked["sign_name"] == "盯盘侠"

