from flask import Flask, request
from config import discourse_api_key, vk_chat_id, vk_api_token
import random
import requests
import vk_api

app = Flask(__name__)
headers = {'Api-Key': discourse_api_key}

vk_session = vk_api.VkApi(token=vk_api_token)
vk_session._auth_token()
vk = vk_session.get_api()


@app.route('/', methods=['POST', 'GET'])
def on_webhook():
    request_data = request.get_json()
    msg = ""
    if 'assign' in request_data:
        assign_data = request_data['assign']
        if assign_data['type'] == 'assigned':
            msg = f"{assign_data['assigned_by_username']} назначил модератора {assign_data['assigned_to_username']} " \
                  f"ответственным за тему «{assign_data['topic_title']}» " \
                  f"(https://forum.ezcheats.ru/t/{assign_data['topic_id']})."
        elif assign_data['type'] == 'unassigned':
            msg = f"{assign_data['unassigned_by_username']} снял с модератора {assign_data['unassigned_to_username']} " \
                  f"ответственность за тему «{assign_data['topic_title']}» " \
                  f"(https://forum.ezcheats.ru/t/{assign_data['topic_id']})."
    elif 'reviewable' in request_data:
        if request.headers['X-Discourse-Event'] == 'reviewable_created':
            review_data = request_data['reviewable']
            created_by = requests.get(
                f"https://forum.ezcheats.ru/admin/users/{review_data['created_by_id']}.json",
                headers=headers).json()['username']
            if review_data['type'] == 'ReviewableFlaggedPost':
                target_created_by = requests.get(
                    f"https://forum.ezcheats.ru/admin/users/{review_data['target_created_by_id']}.json",
                    headers=headers).json()['username']
                msg = f"⚠️ {created_by} отправил жалобу на какое-то сообщение!\n" \
                    f"Автор: {target_created_by}\n" \
                    f"Ссылка: {review_data['target_url']}\n" \
                    f"Создано: {review_data['created_at']}\n\n" \
                    f"Пожалуйста, посмотрите: https://forum.ezcheats.ru/review/{review_data['id']}"
            elif review_data['type'] == 'ReviewableQueuedPost':
                msg = f"⚠️ На премодерации появился новый топик или сообщение!\n" \
                    f"Автор: {created_by}\n" \
                    f"Заголовок: «{review_data['payload']['title']}»\n" \
                    f"Создано: {review_data['created_at']} \n\n" \
                    f"Пожалуйста, посмотрите: https://forum.ezcheats.ru/review/{review_data['id']}"
    if msg != "":
        vk.messages.send(peer_id=vk_chat_id, message=msg, random_id=random.randint(1, 1000000))
        
    return 'True'


if __name__ == '__main__':
    app.run(host='0.0.0.0', ssl_context=(
        '/var/discourse/shared/standalone/ssl/mirea.ninja.cer', '/var/discourse/shared/standalone/ssl/mirea.ninja.key'))
    #app.run(host='0.0.0.0')
