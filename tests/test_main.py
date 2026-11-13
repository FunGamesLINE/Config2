"""Тесты проверки конфигурации."""

import unittest

from src.main import ConfigError, validate_config

VALID = {
    "package_name": "requests",
    "repository_url": "https://example.com/repo",
    "test_mode": False,
    "ascii_tree": True,
    "max_depth": 3,
    "filter_substring": "",
}


class ValidateConfigTest(unittest.TestCase):
    """Проверки функции validate_config."""

    def test_valid_config(self):
        """Верная конфигурация проходит проверку."""
        validate_config(VALID)

    def test_missing_param(self):
        """Отсутствующий параметр вызывает ошибку."""
        config = dict(VALID)
        del config["max_depth"]
        with self.assertRaises(ConfigError):
            validate_config(config)

    def test_wrong_type(self):
        """Неверный тип параметра вызывает ошибку."""
        config = dict(VALID, max_depth="3")
        with self.assertRaises(ConfigError):
            validate_config(config)


if __name__ == "__main__":
    unittest.main()