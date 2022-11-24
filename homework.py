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

logging.basicConfig(
    level=logging.DEBUG,
    filename='bot.log',
    format='%(asctime)s, %(levelname)s, %(funcName)s, %(message)s'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)

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
    """Функция проверяет доступность переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Функция отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except telegram.error.TelegramError as error:
        logging.error(f'Ошибка отправки сообщения {error}')
    else:
        logging.debug(f'Сообщение {message} отправлено')


def get_api_answer(timestamp):
    """Функция делает запрос к API сервиса."""
    params = {'from_date': timestamp}
    timestamp = int(time.time())

    try:
        logging.info(f'Отправка запроса на {ENDPOINT} с параметрами {params}')
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            raise response
        return response.json()
    except JSONDecodeError:
        raise 'Ошибка формата данных'
    except requests.exceptions.RequestException:
        raise 'Ошибка соединения'


def check_response(response):
    """Функция проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        raise TypeError('Ответ вернулся не в виде словаря')
    if 'homeworks' not in response:
        raise 'Ключа homeworks нет в словаре'
    if 'current_date' not in response:
        raise 'Ключа current_date нет в словаре'
    if not isinstance(response['homeworks'], list):
        raise TypeError(
            'Запрос к серверу пришёл не в виде списка')
    return response['homeworks']


def parse_status(homeworks):
    """Функция извлекает информации домашней работе и ее статус."""
    if 'homework_name' not in homeworks:
        raise 'Ключ homework_name не обнаружен в словаре'
    homework_name = homeworks['homework_name']
    if 'status' not in homeworks:
        raise 'Ключ status не обнаружен в словаре'
    homework_status = homeworks.get('status')
    if homework_status is None:
        raise 'Пришел пустой список'
    if homework_status not in HOMEWORK_VERDICTS:
        raise 'Статус не обнаружен в списке'
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Отсутствует Токен(-ы)')
        sys.exit()
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
            logging.error(f'{error}')
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()