import logging
import textwrap as tw
from argparse import ArgumentParser
from typing import Union

import requests
import telebot
from environs import Env

logger = logging.getLogger('TeleBot')


class TGLogsHandler(logging.Handler):
    def __init__(self, bot_token: str, chat_id: Union[int, str]):
        super().__init__()
        self.bot = telebot.TeleBot(bot_token)
        self.chat_id = chat_id

    def emit(self, record):
        log_entry = self.format(record)
        msg = self.bot.send_message(self.chat_id, log_entry)


def main():
    env = Env()
    env.read_env()
    api_token = env.str("TELEGRAM_BOT_TOKEN")
    admin_id = env.int("ADMIN_CHAT_ID")

    logging.basicConfig(level=logging.INFO)
    logger.setLevel(logging.INFO)
    logger.info('Commence logging.')
    logger.addHandler(TGLogsHandler(api_token, admin_id))

    arg_parser = ArgumentParser(
        description='Бот для проверки заданий на dvmn.org'
    )
    arg_parser.add_argument(
        '--id',
        help="ID чата, в который будут отправляться уведомления.",
        type=int,
        default=env.int('TG_USER_ID')
    )
    args = arg_parser.parse_args()

    bot = telebot.TeleBot(api_token)
    logger.info(f'Bot is launched.')
    logger.error('Это тестовая ошибка')

    dvmn_lpoll_url = "https://dvmn.org/api/long_polling/"
    auth_token_header = {
        "Authorization": env.str("DEVMAN_PERSONAL_TOKEN")
    }
    timestamp_param = {}

    while True:
        try:
            dvmn_lpoll_response = requests.get(
                dvmn_lpoll_url,
                headers=auth_token_header,
                params=timestamp_param
            )
            dvmn_lpoll_response.raise_for_status()
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError, requests.HTTPError) as err:
            logger.error('Ошибка при выполнении запроса к серверу.')
            logger.exception(err)

        reviews = dvmn_lpoll_response.json()
        if reviews["status"] == "timeout":
            timestamp_param['timestamp'] = reviews["timestamp_to_request"]
        elif reviews["status"] == "found":
            try:
                send_notification(bot, admin_id, reviews)
            except requests.HTTPError or requests.ConnectionError as err:
                logger.error(f'Error sending notification: {err}')
                logger.exception(err)
            timestamp_param['timestamp'] = reviews["last_attempt_timestamp"]


def send_notification(bot: telebot.TeleBot, chat_id: int, reviews: dict):
    attempt = reviews['new_attempts'][0]
    notification_text = f"""
        Вашу работу проверили: «{attempt['lesson_title']}\n
        {'К сожалению, в работе нашлись ошибки.' if attempt['is_negative'] else
        'Преподавателю всё понравилось, открыт следующий урок!'}

        Ссылка на урок: {attempt['lesson_url']}
    """
    msg = bot.send_message(
        chat_id,
        tw.dedent(notification_text),
        disable_web_page_preview=True)

    return msg


if __name__ == "__main__":
    main()
