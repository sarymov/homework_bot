import logging
import os
import sys
import time
from http import HTTPStatus
from json import JSONDecodeError

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

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

# Да, без докстрингов не проходят тесты на сайте #
# Яндекс практикума #


class SergeyException(Exception):
    """Докстринг для тестов."""

    pass


class NotSendingError(SergeyException):
    """Докстринг для тестов."""

    pass


class WrongAPIResponseCodeError(SergeyException):
    """Докстринг для тестов."""

    pass


class FormatAPIError(SergeyException):
    """Докстринг для тестов."""

    pass


class ConnectionAPIError(SergeyException):
    """Докстринг для тестов."""

    pass


class CustomError(SergeyException):
    """Докстринг для тестов."""

    pass


def check_tokens():
    """Функция проверяет доступность переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Функция отправляет сообщение в Telegram чат."""
    try:
        logging.debug('Пытаемся отравить сообщение')
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except telegram.error.TelegramError as error:
        msg = f'Ошибка отправки сообщения {error}'
        logging.error(msg)
        raise NotSendingError(msg) from error
    else:
        logging.debug(f'Сообщение {message} отправлено')


def get_api_answer(timestamp):
    """Функция делает запрос к API сервиса."""
    params = {'from_date': timestamp}
    request_params = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': params
    }

    try:
        logging.info(f'Отправка запроса на {ENDPOINT} с параметрами {params}')
        response = requests.get(**request_params)
        if response.status_code != HTTPStatus.OK:
            msg = 'Запрос к API не прошел'
            logging.error(msg)
            raise WrongAPIResponseCodeError(msg)
        return response.json()
    except JSONDecodeError as error:
        raise CustomError from error
    except requests.exceptions.RequestException as error:
        raise ConnectionAPIError(f'Ошибка соединения {error}')


def check_response(response):
    """Функция проверяет ответ API на корректность."""
    logging.debug('Проверяем корректность ответов API')
    if not isinstance(response, dict):
        raise TypeError('Ответ вернулся не в виде словаря')
    if 'homeworks' not in response:
        raise KeyError('Ключа homeworks нет в словаре')
    if 'current_date' not in response:
        raise KeyError('Ключа current_date нет в словаре')
    if not isinstance(response['homeworks'], list):
        raise TypeError(
            'Запрос к серверу пришёл не в виде списка')
    return response['homeworks']


def parse_status(homeworks):
    """Функция извлекает информации домашней работе и ее статус."""
    logging.debug('Извлекаем инфу о домашке и ее статусе')
    if 'homework_name' not in homeworks:
        raise KeyError('Ключ homework_name не обнаружен в словаре')
    homework_name = homeworks['homework_name']
    if 'status' not in homeworks:
        raise KeyError('Ключ status не обнаружен в словаре')
    homework_status = homeworks.get('status')
    if homework_status is None:
        raise ValueError('Пришел пустой список')
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError('Статус не обнаружен в списке')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    prev_report = None
    first_msg = None

    logging.debug('Работает основная логика')

    if not check_tokens():
        logging.critical('Отсутствует Токен(-ы)')
        sys.exit('Завершение работы из-за отсутствия Токенов')

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            new_homeworks = check_response(response)
            logging.info(f'Получен список работ {response}')
            if new_homeworks:
                current_report = new_homeworks[0]
            if current_report != prev_report:
                prev_report = parse_status(current_report)
                send_message(bot, parse_status(current_report))
            else:
                logging.debug('Нет новых статусов')

        except NotSendingError as error:
            logging.error(f' Ошибка отправки {error}')
        except Exception as error:
            logging.error(f'{error}')
            message = f'Сбой в работе программы: {error}'
            if message != first_msg:
                send_message(bot, message)
                first_msg = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
    logging.basicConfig(
        level=logging.DEBUG,
        filename='bot.log',
        format='%(asctime)s, %(levelname)s, %(funcName)s, %(message)s'
    )
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(handler)
