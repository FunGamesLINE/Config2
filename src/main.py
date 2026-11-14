import argparse
import base64
import json
import string
import tomllib
import urllib.request
import webbrowser
import zlib
from pathlib import Path

import yaml

MIN_DEPTH = 1
ROOT_DEPTH = 0
TIMEOUT = 10
BLOCK_SIZE = 3
GITHUB_PREFIX = "https://github.com/"
RAW_PREFIX = "https://raw.githubusercontent.com/"
API_URL = "https://crates.io/api/v1/crates/"
REVERSE_SUFFIX = "/reverse_dependencies?per_page=100"
PLANTUML_URL = "https://www.plantuml.com/plantuml/png/"
IMAGE_FILE = "graph.png"
MANIFEST_NAME = "Cargo.toml"
NORMAL_KIND = "normal"
HEADERS = {"User-Agent": "dep-graph-student-project"}

BASE64_ALPHABET = (
    string.ascii_uppercase + string.ascii_lowercase + string.digits + "+/"
)
PLANTUML_ALPHABET = (
    string.digits + string.ascii_uppercase + string.ascii_lowercase + "-_"
)
TRANSLATION = str.maketrans(BASE64_ALPHABET, PLANTUML_ALPHABET)

BRANCH = "|-- "
LAST_BRANCH = "`-- "
LINE_PREFIX = "|   "
EMPTY_PREFIX = "    "
REPEAT_MARK = " (*)"

PARAMS = {
    "package_name": str,
    "repository_url": str,
    "test_mode": bool,
    "reverse_mode": bool,
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


def download_bytes(url):
    """Скачивает файл по ссылке и возвращает его содержимое."""
    request = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.read()
    except (OSError, ValueError) as error:
        raise ConfigError(f"Не удалось скачать {url}: {error}")


def download_text(url):
    """Скачивает текстовый файл по ссылке."""
    data = download_bytes(url)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ConfigError(f"Не удалось прочитать {url}: {error}")


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


def invert_graph(graph):
    """Разворачивает граф: пакет - список пакетов, зависящих от него."""
    reverse = {}
    for name, children in graph.items():
        reverse.setdefault(name, [])
        for child in children:
            reverse.setdefault(child, []).append(name)
    return reverse


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


def fetch_reverse_dependencies(name):
    """Получает имена пакетов, которые зависят от пакета, с crates.io."""
    data = fetch_json(f"{API_URL}{name}{REVERSE_SUFFIX}")
    try:
        owners = {item["id"]: item["crate"] for item in data["versions"]}
        result = []
        for item in data["dependencies"]:
            owner = owners[item["version_id"]]
            if item["kind"] == NORMAL_KIND and owner not in result:
                result.append(owner)
        return result
    except (KeyError, TypeError):
        raise ConfigError(f"Неверный ответ реестра для '{name}'")


def load_source(config):
    """Возвращает словарь пакет - список его зависимостей (или зависимых)."""
    name = config["package_name"]
    if config["reverse_mode"] and not config["test_mode"]:
        return {}
    text = read_manifest_text(config)
    if config["test_mode"]:
        source = parse_graph(text)
        if config["reverse_mode"]:
            source = invert_graph(source)
        if name not in source:
            raise ConfigError(f"Пакет '{name}' не найден в файле графа")
        return source
    return {name: list(get_dependencies(text))}


def get_children(source, name, config):
    """Возвращает зависимости пакета, при необходимости загружая их."""
    if name not in source and not config["test_mode"]:
        if config["reverse_mode"]:
            source[name] = fetch_reverse_dependencies(name)
        else:
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
        children = get_children(source, name, config)
        children = [
            child
            for child in children
            if not is_skipped(child, config["filter_substring"])
        ]
        graph[name] = children
        next_level.extend(children)
    build_graph(next_level, graph, source, config, depth + 1)


def print_graph(package_name, graph, reverse_mode):
    """Выводит граф: пакет и его прямые или обратные зависимости."""
    if reverse_mode:
        title = "Обратные зависимости пакета"
    else:
        title = "Граф зависимостей пакета"
    print(f"{title} {package_name}:")
    for name, children in graph.items():
        text = " ".join(children) or "нет"
        print(f"{name}: {text}")


def add_tree_lines(graph, name, prefix, shown, lines):
    """Добавляет в lines строки ASCII-дерева для зависимостей пакета."""
    shown.add(name)
    children = graph.get(name, [])
    last_index = len(children) - 1
    for index, child in enumerate(children):
        is_last = index == last_index
        branch = LAST_BRANCH if is_last else BRANCH
        repeated = child in shown and bool(graph.get(child))
        mark = REPEAT_MARK if repeated else ""
        lines.append(f"{prefix}{branch}{child}{mark}")
        if child not in shown:
            extra = EMPTY_PREFIX if is_last else LINE_PREFIX
            add_tree_lines(graph, child, prefix + extra, shown, lines)


def make_ascii_tree(root, graph):
    """Возвращает текст ASCII-дерева зависимостей пакета."""
    lines = [root]
    add_tree_lines(graph, root, "", set(), lines)
    return "\n".join(lines)


def collect_names(graph):
    """Возвращает все пакеты графа без повторов в порядке появления."""
    names = []
    for name, children in graph.items():
        for item in [name] + children:
            if item not in names:
                names.append(item)
    return names


def get_edges(graph, reverse_mode):
    """Возвращает список рёбер (зависящий пакет, нужный ему пакет)."""
    edges = []
    for name, children in graph.items():
        for child in children:
            if reverse_mode:
                edges.append((child, name))
            else:
                edges.append((name, child))
    return edges


def make_plantuml(graph, reverse_mode):
    """Формирует текст диаграммы PlantUML по графу зависимостей."""
    names = collect_names(graph)
    aliases = {name: f"n{index}" for index, name in enumerate(names)}
    lines = ["@startuml"]
    for name, alias in aliases.items():
        lines.append(f'component "{name}" as {alias}')
    for source, target in get_edges(graph, reverse_mode):
        lines.append(f"{aliases[source]} --> {aliases[target]}")
    lines.append("@enduml")
    return "\n".join(lines)


def encode_plantuml(text):
    """Кодирует текст диаграммы для адреса сервера PlantUML."""
    compressor = zlib.compressobj(
        zlib.Z_BEST_COMPRESSION, zlib.DEFLATED, -zlib.MAX_WBITS
    )
    packed = compressor.compress(text.encode("utf-8")) + compressor.flush()
    packed += bytes(-len(packed) % BLOCK_SIZE)
    encoded = base64.b64encode(packed).decode("ascii")
    return encoded.translate(TRANSLATION)


def show_image(plantuml_text):
    """Скачивает изображение диаграммы, сохраняет и открывает его."""
    url = f"{PLANTUML_URL}{encode_plantuml(plantuml_text)}"
    data = download_bytes(url)
    try:
        with open(IMAGE_FILE, "wb") as file:
            file.write(data)
    except OSError as error:
        raise ConfigError(f"Не удалось сохранить изображение: {error}")
    print(f"Изображение сохранено в файл {IMAGE_FILE}")
    webbrowser.open(Path(IMAGE_FILE).resolve().as_uri())


def show_results(config, graph):
    """Выводит граф, ASCII-дерево, текст PlantUML и показывает рисунок."""
    name = config["package_name"]
    print_graph(name, graph, config["reverse_mode"])
    if config["ascii_tree"]:
        print()
        print(make_ascii_tree(name, graph))
    plantuml_text = make_plantuml(graph, config["reverse_mode"])
    print()
    print(plantuml_text)
    show_image(plantuml_text)


def main():
    """Читает конфигурацию, строит граф и выводит результаты."""
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
        show_results(config, graph)
    except ConfigError as error:
        raise SystemExit(f"Ошибка: {error}")


if __name__ == "__main__":
    main()