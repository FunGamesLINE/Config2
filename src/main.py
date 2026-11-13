import argparse
import json
import tomllib
import urllib.request

import yaml

MIN_DEPTH = 1
ROOT_DEPTH = 0
TIMEOUT = 10
GITHUB_PREFIX = "https://github.com/"
RAW_PREFIX = "https://raw.githubusercontent.com/"
API_URL = "https://crates.io/api/v1/crates/"
MANIFEST_NAME = "Cargo.toml"
NORMAL_KIND = "normal"
HEADERS = {"User-Agent": "dep-graph-student-project"}

PARAMS = {
    "package_name": str,
    "repository_url": str,
    "test_mode": bool,
    "ascii_tree": bool,
    "max_depth": int,
    "filter_substring": str,
}


class ConfigError(Exception):
    """Ошибка в конфигурации или при получении данных."""


def load_config(path):
    """Читает YAML-файл и возвращает словарь параметров."""
    try:
        with open(path, encoding="utf-8") as file:
            config = yaml.safe_load(file)
    except OSError as error:
        raise ConfigError(f"Не удалось открыть файл: {error}")
    except yaml.YAMLError as error:
        raise ConfigError(f"Ошибка разбора YAML: {error}")
    if not isinstance(config, dict):
        raise ConfigError("Конфигурация должна быть набором ключ: значение")
    return config


def check_type(name, value):
    """Проверяет, что значение параметра имеет нужный тип."""
    expected = PARAMS[name]
    if type(value) is not expected:
        raise ConfigError(
            f"Параметр '{name}' должен иметь тип {expected.__name__}"
        )


def validate_config(config):
    """Проверяет наличие, типы и значения всех параметров."""
    for name in PARAMS:
        if name not in config:
            raise ConfigError(f"Не задан параметр '{name}'")
        check_type(name, config[name])
    if not config["package_name"].strip():
        raise ConfigError("Параметр 'package_name' не должен быть пустым")
    if not config["repository_url"].strip():
        raise ConfigError("Параметр 'repository_url' не должен быть пустым")
    if config["max_depth"] < MIN_DEPTH:
        raise ConfigError(f"Параметр 'max_depth' должен быть >= {MIN_DEPTH}")


def make_manifest_url(repository_url):
    """Строит ссылку на файл Cargo.toml в корне репозитория GitHub."""
    url = repository_url.strip().rstrip("/").removesuffix(".git")
    if not url.startswith(GITHUB_PREFIX):
        raise ConfigError("Поддерживаются только репозитории GitHub")
    path = url.removeprefix(GITHUB_PREFIX)
    return f"{RAW_PREFIX}{path}/HEAD/{MANIFEST_NAME}"


def read_local_file(path):
    """Читает текст тестового файла с диска."""
    try:
        with open(path, encoding="utf-8") as file:
            return file.read()
    except OSError as error:
        raise ConfigError(f"Не удалось открыть файл: {error}")


def download_text(url):
    """Скачивает текстовый файл по ссылке."""
    request = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.read().decode("utf-8")
    except (OSError, ValueError) as error:
        raise ConfigError(f"Не удалось скачать {url}: {error}")


def read_manifest_text(config):
    """Возвращает текст тестового файла или Cargo.toml из репозитория."""
    if config["test_mode"]:
        return read_local_file(config["repository_url"])
    return download_text(make_manifest_url(config["repository_url"]))


def get_version(spec):
    """Возвращает версию зависимости из её описания."""
    if isinstance(spec, str):
        return spec
    return spec.get("version", "не указана")


def get_dependencies(text):
    """Возвращает словарь прямых зависимостей: имя - версия."""
    try:
        manifest = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"Ошибка разбора Cargo.toml: {error}")
    section = manifest.get("dependencies", {})
    return {name: get_version(spec) for name, spec in section.items()}


def parse_graph(text):
    """Разбирает описание тестового графа: строки вида 'A: B C'."""
    graph = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        name, separator, rest = line.partition(":")
        if not separator:
            raise ConfigError(f"Неверная строка графа: '{line}'")
        graph[name.strip()] = rest.split()
    return graph


def fetch_json(url):
    """Скачивает ответ по ссылке и разбирает его как JSON."""
    text = download_text(url)
    try:
        return json.loads(text)
    except ValueError as error:
        raise ConfigError(f"Неверный ответ от {url}: {error}")


def get_latest_version(name):
    """Возвращает последнюю версию пакета из реестра crates.io."""
    info = fetch_json(f"{API_URL}{name}")
    try:
        return info["crate"]["max_version"]
    except (KeyError, TypeError):
        raise ConfigError(f"Не найдена версия пакета '{name}'")


def fetch_crate_dependencies(name):
    """Получает имена зависимостей последней версии пакета с crates.io."""
    version = get_latest_version(name)
    data = fetch_json(f"{API_URL}{name}/{version}/dependencies")
    try:
        return [
            item["crate_id"]
            for item in data["dependencies"]
            if item["kind"] == NORMAL_KIND
        ]
    except (KeyError, TypeError):
        raise ConfigError(f"Неверный ответ реестра для '{name}'")


def load_source(config):
    """Возвращает словарь пакет - список зависимостей с корневым пакетом."""
    text = read_manifest_text(config)
    name = config["package_name"]
    if config["test_mode"]:
        source = parse_graph(text)
        if name not in source:
            raise ConfigError(f"Пакет '{name}' не найден в файле графа")
        return source
    return {name: list(get_dependencies(text))}


def get_children(source, name, test_mode):
    """Возвращает зависимости пакета, при необходимости загружая их."""
    if name not in source and not test_mode:
        source[name] = fetch_crate_dependencies(name)
    return source.get(name, [])


def is_skipped(name, substring):
    """Проверяет, нужно ли пропустить пакет из-за подстроки в имени."""
    return bool(substring) and substring in name


def build_graph(level, graph, source, config, depth):
    """Строит граф обходом в ширину. Вызов обрабатывает один уровень."""
    if not level or depth >= config["max_depth"]:
        return
    next_level = []
    for name in level:
        if name in graph:
            continue
        children = get_children(source, name, config["test_mode"])
        children = [
            child
            for child in children
            if not is_skipped(child, config["filter_substring"])
        ]
        graph[name] = children
        next_level.extend(children)
    build_graph(next_level, graph, source, config, depth + 1)


def print_graph(package_name, graph):
    """Выводит граф: пакет и его прямые зависимости."""
    print(f"Граф зависимостей пакета {package_name}:")
    for name, children in graph.items():
        text = " ".join(children) or "нет"
        print(f"{name}: {text}")


def main():
    """Читает конфигурацию, строит и выводит граф зависимостей."""
    parser = argparse.ArgumentParser(description="Граф зависимостей пакета")
    parser.add_argument(
        "-c", "--config", default="config.yaml", help="путь к YAML-файлу"
    )
    args = parser.parse_args()
    graph = {}
    try:
        config = load_config(args.config)
        validate_config(config)
        source = load_source(config)
        root = [config["package_name"]]
        build_graph(root, graph, source, config, ROOT_DEPTH)
    except ConfigError as error:
        raise SystemExit(f"Ошибка: {error}")
    print_graph(config["package_name"], graph)


if __name__ == "__main__":
    main()