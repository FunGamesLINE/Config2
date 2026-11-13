"""Тесты проверки конфигурации и получения зависимостей."""

import unittest

from src.main import (
    ConfigError,
    get_dependencies,
    make_manifest_url,
    validate_config,
)

VALID = {
    "package_name": "requests",
    "repository_url": "https://example.com/repo",
    "test_mode": False,
    "ascii_tree": True,
    "max_depth": 3,
    "filter_substring": "",
}

MANIFEST = """
[package]
name = "demo"

[dependencies]
serde = "1.0"
log = { version = "0.4", features = ["std"] }
local = { path = "../local" }

[dev-dependencies]
tempfile = "3"
"""


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


class DependenciesTest(unittest.TestCase):
    """Проверки получения зависимостей."""

    def test_direct_dependencies(self):
        """Возвращаются только прямые зависимости с версиями."""
        result = get_dependencies(MANIFEST)
        self.assertEqual(
            result,
            {"serde": "1.0", "log": "0.4", "local": "не указана"},
        )

    def test_no_dependencies(self):
        """Без раздела [dependencies] результат пустой."""
        self.assertEqual(get_dependencies("[package]\nname = 'a'"), {})

    def test_bad_toml(self):
        """Неверный TOML вызывает ошибку."""
        with self.assertRaises(ConfigError):
            get_dependencies("это не toml")

    def test_manifest_url(self):
        """Ссылка на Cargo.toml строится из адреса репозитория."""
        url = make_manifest_url("https://github.com/user/repo.git")
        self.assertEqual(
            url,
            "https://raw.githubusercontent.com/user/repo/HEAD/Cargo.toml",
        )

    def test_not_github(self):
        """Неверный адрес вызывает ошибку."""
        with self.assertRaises(ConfigError):
            make_manifest_url("https://example.com/repo")


if __name__ == "__main__":
    unittest.main()