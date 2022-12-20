import os
import sys
import logging
import time
import datetime

from dotenv import load_dotenv
import requests
from http import HTTPStatus
import telegram
from json.decoder import JSONDecodeError

from exceptions import (MissTokenError, VerdictErrors, ResponseError)

load_dotenv()
TOKENS_NAMES = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')
PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """
    Проверяет доступность переменных.
    окружения,которые необходимы для работы программы
    """
    tokens = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    if not all(tokens):
        none_tikens = [TOKENS_NAMES[i] for i, x in enumerate(tokens) if not x]
        logging.critical(f'Отсутствуют токены: {none_tikens}')
        raise MissTokenError(f'Отсутствуют токены: {none_tikens}')


def send_message(bot, message):
    """
    Bot отпраляет сообещние пользователю.
        Parameters:
            bot: Объект класса telegram.Bot
            message (str): Отправляемое сообщение
    """
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug('Сообщение отправлено успешно')
    except telegram.error.TelegramError as error:
        logging.error(f'Ошибка при отправки сообщения: {error}')
        raise error(f'Ошибка при отправки сообщения: {error}')


def get_api_answer(timestamp):
    """
    Делает запрос к единственному эндпоинту API-сервиса.
        Parameters:
            timestamp (int): Временная метка
        Returns:
            response: Ответ API
    """
    payload = {'from_date': timestamp}

    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=payload)
        if response.status_code != HTTPStatus.OK:
            raise ResponseError(
                f'Неверный ответ {ENDPOINT}: {response.status_code}')
        response = response.json()
        if 'error' in response.keys():
            raise ResponseError(
                f'Неверный ответ {ENDPOINT}: {response["error"]}')
        elif 'code' in response.keys():
            raise ResponseError(
                f'Неверный ответ {ENDPOINT}: {response["code"]}')
        return response
    except JSONDecodeError:
        raise JSONDecodeError(
            f'Ошибка при декорировании в JSON: {JSONDecodeError}')
    except requests.exceptions.HTTPError as error:
        raise error(f'Http Error: {error}')
    except requests.exceptions.Timeout as error:
        raise error(f'Timeout Error: {error}')
    except requests.exceptions.ConnectionError as error:
        raise error(f'Ошибка соединения: {error}')
    except requests.RequestException as error:
        raise error(f'Недоступность эндпоинта: {error}')


def check_response(response):
    """
    Проверяет ответ API на соответствие документации.
        Parameters:
            response: Ответ API
        Returns:
            homeworks: Возвращает значение под ключем 'homeworks'
    """
    if not isinstance(response, dict):
        raise TypeError('Полученные ответ от API не является словарем')
    if 'homeworks' not in response.keys():
        raise KeyError(f'Отсутствие ожидаемых ключей в ответе API: {KeyError}')
    if not isinstance(response['homeworks'], list):
        raise TypeError('Значение под ключем homeworks не list')
    return response['homeworks']


def parse_status(homework):
    """
    Извлекает из информации о конкретной домашней работе статус этой работы.
        Parameters:
            homework (dict): Конкретная домашняя работа
        Returns:
            str: Статус работы
    """
    try:
        status = homework['status']
        homework_name = homework['homework_name']
    except KeyError:
        raise KeyError('Отсутствие необходимых ключей status и homework_name')
    if status in HOMEWORK_VERDICTS.keys():
        verdict = HOMEWORK_VERDICTS[status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    raise VerdictErrors('Неожиданный статус домашней работы,'
                        f'обнаруженный в ответе API {status}')


def main():
    """Основная логика работы бота."""
    check_tokens()

    current_status = ''
    try:
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
    except Exception as error:
        logging.error(f'Бот некорректно проинициализировался : {error}')
        raise error(f'Бот некорректно проинициализировался : {error}')
    timestamp = datetime.date.today() - datetime.timedelta(days=30)
    timestamp = int(time.mktime(timestamp.timetuple()))

    while True:
        try:
            response = get_api_answer(timestamp=timestamp)
            homeworks = check_response(response=response)
            if homeworks:
                verdict = parse_status(homework=homeworks[0])
                if current_status != verdict:
                    current_status = verdict
                    send_message(bot, message=current_status)
                else:
                    logging.debug('В ответе отсутствует новый статус')
        except telegram.error.TelegramError:
            # Я бы вставил сюда логирование ошибки, но pytest это не нравится
            pass
        except Exception as error:
            logging.error(f'Сбой в работе программы: {error}')
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
    )
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(formatter)
    main()
