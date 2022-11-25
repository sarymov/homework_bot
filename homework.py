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


class NotSendingError(Exception):
    """Кастомное исключение"""
    pass


class WrongAPIResponseCodeError(Exception):
    """Кастомное исключение"""
    pass


class FormatAPIError(Exception):
    """Кастомное исключение"""
    pass


class ConnectionAPIError(Exception):
    """Кастомное исключение"""
    pass


class CustomError(Exception):
    """Кастомное исключение"""
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
        raise NotSendingError(msg)
    else:
        logging.debug(f'Сообщение {message} отправлено')


def get_api_answer(timestamp):
    """Функция делает запрос к API сервиса."""
    params = {'from_date': timestamp}
    # Я немного не понял какой словарь нужно еще сюда написать, чтобы его применить#
    try:
        logging.info(f'Отправка запроса на {ENDPOINT} с параметрами {params}')
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
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
        raise CustomError('Ключа homeworks нет в словаре')
    if 'current_date' not in response:
        raise CustomError('Ключа current_date нет в словаре')
    if not isinstance(response['homeworks'], list):
        raise TypeError(
            'Запрос к серверу пришёл не в виде списка')
    return response['homeworks']


def parse_status(homeworks):
    """Функция извлекает информации домашней работе и ее статус."""
    logging.debug('Извлекаем инфу о домашке и ее статусе')
    if 'homework_name' not in homeworks:
        raise TypeError('Ключ homework_name не обнаружен в словаре')
    homework_name = homeworks['homework_name']
    if 'status' not in homeworks:
        raise TypeError('Ключ status не обнаружен в словаре')
    homework_status = homeworks.get('status')
    if homework_status is None:
        raise TypeError('Пришел пустой список')
    if homework_status not in HOMEWORK_VERDICTS:
        raise TypeError('Статус не обнаружен в списке')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    logging.debug('Работает основная логика')
    if not check_tokens():
        logging.critical('Отсутствует Токен(-ы)')
        sys.exit('Завершение работы из-за отсутствия Токенов')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)

    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            logging.info(f'Получен список работ {response}')
            if homeworks:
                send_message(bot, parse_status(homeworks[0]))
            else:
                logging.debug('Нет новых статусов')
                send_message(bot, 'Нет новых статусов')
            timestamp = response.get('current_date')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
        except Exception as error:
            logging.error(f'{error}')
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
