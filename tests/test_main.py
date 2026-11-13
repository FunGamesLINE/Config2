"""Тесты конфигурации, получения зависимостей и построения графа."""

import unittest

from src.main import (
    ConfigError,
    build_graph,
    get_dependencies,
    make_manifest_url,
    parse_graph,
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

SOURCE = {
    "A": ["B", "C"],
    "B": ["D"],
    "C": ["D", "E"],
    "D": ["F"],
    "E": [],
    "F": [],
}

CYCLE = {"X": ["Y"], "Y": ["Z"], "Z": ["X"]}


def make_graph(root, source, max_depth, substring=""):
    """Строит граф в тестовом режиме и возвращает его."""
    config = dict(
        VALID,
        test_mode=True,
        max_depth=max_depth,
        filter_substring=substring,
    )
    graph = {}
    build_graph([root], graph, source, config, 0)
    return graph


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


class ParseGraphTest(unittest.TestCase):
    """Проверки разбора файла тестового графа."""

    def test_parse(self):
        """Строки разбираются в словарь пакет - зависимости."""
        result = parse_graph("A: B C\nB:\n\n")
        self.assertEqual(result, {"A": ["B", "C"], "B": []})

    def test_bad_line(self):
        """Строка без двоеточия вызывает ошибку."""
        with self.assertRaises(ConfigError):
            parse_graph("A B C")


class BuildGraphTest(unittest.TestCase):
    """Проверки построения графа зависимостей."""

    def test_full_graph(self):
        """Транзитивные зависимости попадают в граф."""
        graph = make_graph("A", SOURCE, 10)
        self.assertEqual(graph, SOURCE)

    def test_max_depth(self):
        """Граф не глубже заданной глубины."""
        graph = make_graph("A", SOURCE, 2)
        self.assertEqual(
            graph,
            {"A": ["B", "C"], "B": ["D"], "C": ["D", "E"]},
        )

    def test_filter(self):
        """Пакеты с подстрокой в имени исключаются."""
        graph = make_graph("A", SOURCE, 10, "D")
        self.assertEqual(
            graph,
            {"A": ["B", "C"], "B": [], "C": ["E"], "E": []},
        )

    def test_cycle(self):
        """Цикл не приводит к зависанию."""
        graph = make_graph("X", CYCLE, 10)
        self.assertEqual(graph, CYCLE)


if __name__ == "__main__":
    unittest.main()