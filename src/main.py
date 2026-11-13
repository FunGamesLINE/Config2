import argparse
import tomllib
import urllib.request

import yaml

MIN_DEPTH = 1
TIMEOUT = 10
GITHUB_PREFIX = "https://github.com/"
RAW_PREFIX = "https://raw.githubusercontent.com/"
MANIFEST_NAME = "Cargo.toml"

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
    """Читает текст тестового файла Cargo.toml с диска."""
    try:
        with open(path, encoding="utf-8") as file:
            return file.read()
    except OSError as error:
        raise ConfigError(f"Не удалось открыть файл: {error}")


def download_text(url):
    """Скачивает текстовый файл по ссылке."""
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
            return response.read().decode("utf-8")
    except (OSError, ValueError) as error:
        raise ConfigError(f"Не удалось скачать {url}: {error}")


def read_manifest_text(config):
    """Возвращает текст Cargo.toml из файла или из репозитория."""
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


def print_dependencies(package_name, dependencies):
    """Выводит прямые зависимости пакета."""
    print(f"Прямые зависимости пакета {package_name}:")
    if not dependencies:
        print("нет")
    for name, version in dependencies.items():
        print(f"{name} {version}")


def main():
    """Читает конфигурацию и выводит прямые зависимости пакета."""
    parser = argparse.ArgumentParser(description="Граф зависимостей пакета")
    parser.add_argument(
        "-c", "--config", default="config.yaml", help="путь к YAML-файлу"
    )
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        validate_config(config)
        text = read_manifest_text(config)
        dependencies = get_dependencies(text)
    except ConfigError as error:
        raise SystemExit(f"Ошибка: {error}")
    print_dependencies(config["package_name"], dependencies)


if __name__ == "__main__":
    main()