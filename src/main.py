import argparse
import yaml

MIN_DEPTH = 1

PARAMS = {
    "package_name": str,
    "repository_url": str,
    "test_mode": bool,
    "ascii_tree": bool,
    "max_depth": int,
    "filter_substring": str,
}


class ConfigError(Exception):
    """Ошибка в конфигурационном файле."""


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


def print_params(config):
    """Выводит параметры в формате ключ-значение."""
    for name in PARAMS:
        print(f"{name}: {config[name]}")


def main():
    """Читает конфигурацию и выводит параметры."""
    parser = argparse.ArgumentParser(description="Граф зависимостей пакета")
    parser.add_argument(
        "-c", "--config", default="config.yaml", help="путь к YAML-файлу"
    )
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        validate_config(config)
    except ConfigError as error:
        raise SystemExit(f"Ошибка: {error}")
    print_params(config)


if __name__ == "__main__":
    main()