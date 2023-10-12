from io import BytesIO
import vk_api
import random
import psycopg
import unicodedata
import dotenv
import os
from dotenv import set_key
from flask import Flask, json, request
from flask_restful import Api
from logging.config import dictConfig
from vk_api.upload import VkUpload

dictConfig(
    {
        "version": 1,
        "formatters": {
            "default": {
                "format": "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "default",
            }
        },
        "root": {"level": "DEBUG", "handlers": ["console"]},
    }
)

application = Flask(__name__)

api = Api()

botStatus = False


@application.route('/')
def index():
    return "Hello from VkCommentBot"


@application.route('/changebotstatus', methods=['PUT'])
def change_bot_status():

    dotenv.load_dotenv('.env')

    request_api_key = request.args.get('api_key')

    if request_api_key == os.environ['API_KEY']:

        BOT_STATUS = os.environ['BOT_STATUS']

        if BOT_STATUS == "True":
            os.environ['BOT_STATUS'] = "False"
            set_key(dotenv_path='.env', key_to_set="BOT_STATUS", value_to_set="False")
            application.logger.info("Бот был выключен")

        else:
            os.environ['BOT_STATUS'] = "True"
            set_key(dotenv_path='.env', key_to_set="BOT_STATUS", value_to_set="True")
            application.logger.info("Бот был включен")

        return os.environ['BOT_STATUS']
    else:
        return 'Wrong api_key'


@application.route('/checkbotstatus', methods=['GET'])
def check_bot_status():

    dotenv.load_dotenv('.env')

    if os.environ['BOT_STATUS'] == 'True':
        return json.dumps(True)
    else:
        return json.dumps(False)


@application.route('/changegroupsettings', methods=['PUT'])
def change_group_settings():

    dotenv.load_dotenv('.env')

    request_api_key = request.args.get('api_key')

    if request_api_key == os.environ['API_KEY']:

        request_group_id = request.args.get('group_id')
        request_group_token = request.args.get('group_token')
        request_user_token = request.args.get('user_token')

        changed_settings = []

        if request_group_id is not None:
            os.environ['GROUP_ID'] = request_group_id
            set_key(dotenv_path='.env', key_to_set="GROUP_ID", value_to_set=f"{request_group_id}")
            changed_settings.append('group_id')
        if request_group_token is not None:
            os.environ['GROUP_TOKEN'] = request_group_token
            set_key(dotenv_path='.env', key_to_set="GROUP_TOKEN", value_to_set=f"{request_group_token}")
            changed_settings.append('group_token')
        if request_user_token is not None:
            os.environ['USER_TOKEN'] = request_user_token
            set_key(dotenv_path='.env', key_to_set="USER_TOKEN", value_to_set=f"{request_user_token}")
            changed_settings.append('user_token')

        application.logger.info(f"Были изменены настройки группы ({changed_settings})")
        return f'Следующие настройки были изменены: {changed_settings}'
    else:
        return 'Wrong api_key'


@application.route('/checkgroupsettings', methods=['GET'])
def check_group_settings():

    dotenv.load_dotenv('.env')

    request_api_key = request.args.get('api_key')

    if request_api_key == os.environ['API_KEY']:
        return {"group_id:": os.environ['GROUP_ID'], "group_token": os.environ['GROUP_TOKEN'], "user_token": os.environ['USER_TOKEN']}
    else:
        return 'Wrong api_key'


@application.route('/', methods=['POST'])
def get_event():

    dotenv.load_dotenv('.env')

    if os.environ['BOT_STATUS'] == 'True':

        try:
            application.logger.info("Получен POST запрос")

            data = json.loads(request.data)

            if 'type' not in data.keys():
                application.logger.info("Полученный POST запрос не от ВК")
                return 'not vk'

            if data['type'] == 'confirmation':
                application.logger.info("Отправлен код подтверждения")
                return '600fca60'

            if data['type'] == 'wall_reply_new' and 'reply_to_user' not in data['object']:

                application.logger.info("Тип запроса - новый комментарий")

                with psycopg.connect(dbname=os.environ['DB_NAME'], user=os.environ['DB_USER'], password=os.environ['DB_PASSWORD'], host=os.environ['DB_HOST']) as conn:
                    with conn.cursor() as cursor:

                        application.logger.info("Подключен к базе данных")

                        cursor.execute("""SELECT v."VkId" FROM public."VkPost" v WHERE v."PostStatus" = 'Включен'""")

                        active_posts = []

                        for row in cursor:
                            active_posts.append(row[0])

                        post_id = data['object']['post_id']

                        if post_id in active_posts:
                            application.logger.info("Пост активен")
                            cursor.execute(f"""SELECT v."KeyWord" FROM public."VkPost" v WHERE v."VkId" = {post_id}""")
                            keyword = cursor.fetchone()[0]

                            comment_text = data['object']['text']

                            if caseless_equal(keyword, comment_text):

                                application.logger.info("Ключевое слово совпадает")

                                dotenv.load_dotenv('.env')

                                application.logger.info("Сессия ВК установлена")

                                reply_to_comment = data['object']['id']

                                cursor.execute(f"""SELECT COUNT(id) FROM public."Scenario" s WHERE s."PostId" = {post_id};""")
                                for row in cursor:
                                    scenarios_count = row[0]

                                random_number = random.randint(0, scenarios_count-1)

                                scenarios_ids = []

                                cursor.execute(f"""SELECT s."id" FROM public."Scenario" s WHERE s."PostId" = {post_id};""")
                                for row in cursor:
                                    scenarios_ids.append(row[0])

                                random_id = scenarios_ids[random_number]

                                cursor.execute(f"""SELECT s."Content", s."CommentImage" FROM public."Scenario" s WHERE s."id"={random_id};""")
                                for row in cursor:
                                    scenario_data = row

                                conn.close()
                                cursor.close()

                                text = scenario_data[0]
                                attachment = None
                                if scenario_data[1] is not None:

                                    vk_session = vk_api.VkApi(token=os.environ['USER_TOKEN'])
                                    vk = vk_session.get_api()
                                    upload = VkUpload(vk)
                                    attachment = upload_photo(upload, scenario_data[1])

                                vk_session = vk_api.VkApi(token=os.environ['GROUP_TOKEN'])
                                vk = vk_session.get_api()
                                vk.wall.createComment(owner_id=os.environ['GROUP_ID'], post_id=post_id, reply_to_comment=reply_to_comment, message=text, attachments=attachment)

                                application.logger.info("Ответ на комментарий написан")
                                return 'ok'
                            else:
                                application.logger.info(f'Комментарий не содержит ключевое слово: {keyword}. Полученное слово: {comment_text}.')
                                return 'ok'
                        else:
                            application.logger.info("Пост выключен или не активен")
                            return 'ok'
            else:
                application.logger.info("Пришёл запрос, но это не комментарий")
                return 'ok'
        except Exception as ex:
            print(ex)
            return 'ok'
    else:
        application.logger.info("Пришёл запрос но бот выключен")
        return 'ok'


def upload_photo(upload, comment_image):

    f = BytesIO(comment_image)

    response = upload.photo_wall(f)[0]

    owner_id = response['owner_id']
    photo_id = response['id']
    access_key = response['access_key']

    attachment = f'photo{owner_id}_{photo_id}_{access_key}'

    return attachment


def normalize_caseless(text):
    return unicodedata.normalize("NFKD", text.casefold())


def caseless_equal(left, right):
    return normalize_caseless(left) == normalize_caseless(right)


if __name__ == '__main__':
    application.run(host='0.0.0.0', port=5000)
