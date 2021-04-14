from flask import Flask, request
from config import discourse_api_key, vk_chat_id, vk_api_token, discourse_chatbot_api_key
import os
import dialogflow
import random
import requests
import vk_api
import sys
import time
import hashlib
import re
import struct
import pefile

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = 'private_key.json'

DIALOGFLOW_PROJECT_ID = 'your_project_id'
DIALOGFLOW_LANGUAGE_CODE = 'ru'
session_client = dialogflow.SessionsClient()

app = Flask(__name__)
headers = {'Api-Key': discourse_api_key}

vk_session = vk_api.VkApi(token=vk_api_token)
vk_session._auth_token()
vk = vk_session.get_api()


@app.route('/file_information/', methods=['POST'])
def get_file_info():
    headers = {'Api-Key': discourse_chatbot_api_key}
    request_data = request.get_json()
    if request.headers['X-Discourse-Event'] == 'post_created':
        if request_data['post']['topic_archetype'] == 'private_message':
            if 'проверить' in request_data['post']['raw'] and 'attachment' in request_data['post']['raw'] and request_data['post']['staff'] is True:
                name = request_data['post']['raw'].split('|attachment]')[0]
                name = name[1:]
                tmp = request_data['post']['raw'].split('|attachment](upload://')[1]
                file_name = tmp.split(') (')[0]
                url = 'https://forum.ezcheats.ru/uploads/short-url/' + file_name
                sample = ''
                with open(file_name, "wb") as file:
                    response = requests.get(url)
                    file.write(response.content)
                    sample = response.content
                
                ape = False
                try:
                    ape = pefile.PE(file_name, fast_load = True)
                except:
                    pass

                if ape != False:
                    pe          = pefile.PE(file_name)
                    
                    msg = f'''
<div data-theme-table="file-approved">
    Файл прошёл модерацию.

| | |
|----------|:-------------:|------:|
| Название | {name}
| MD5 |  {str(hashlib.md5(sample).hexdigest())}
| SHA1 | {str(hashlib.sha1(sample).hexdigest())}
| SHA256 | {str(hashlib.sha256(sample).hexdigest())}
| Размер | {str(len(sample))} (байт)
| imphash | {str(pe.get_imphash())}
</div>
                    '''

                else:
                    msg = f'''
<div data-theme-table="file-approved">
    Файл прошёл модерацию.

| | |
|----------|:-------------:|------:|
| Название | {name}
| MD5 |  {str(hashlib.md5(sample).hexdigest())}
| SHA1 | {str(hashlib.sha1(sample).hexdigest())}
| SHA256 | {str(hashlib.sha256(sample).hexdigest())}
| Размер | {str(len(sample))} (байт)
</div>
                    '''
                requests.post("https://forum.ezcheats.ru/posts.json", headers=headers, data={'topic_id': request_data['post']['topic_id'], 'raw': msg})

    return 'True'


@app.route('/chatbot/', methods=['POST'])
def chatbot_rout():
    headers = {'Api-Key': discourse_chatbot_api_key}
    request_data = request.get_json()
    if request.headers['X-Discourse-Event'] == 'post_created':
        topic_id = request_data['post']['topic_id']
        topic = requests.get(f"https://forum.ezcheats.ru/t/{topic_id}.json",
                headers=headers).json()
        message = ""
        # если это не раздел тех. поддержки читов
        if topic['category_id'] != 18 and topic['category_id'] != 17 and topic['category_id'] != 5:
            if 'помощь' in topic['tags']:
                if len(topic['post_stream']['posts']) == 1:
                    message = request_data['post']['raw']
                else:
                    if 'reply_to_user' in request_data['post']:
                        if request_data['post']['reply_to_user']['username'] == 'HelperBot':
                            message = request_data['post']['raw']
                        else:
                            if '@HelperBot' in request_data['post']['raw']:
                                message = request_data['post']['raw']
        else:
            if len(topic['post_stream']['posts']) == 1:
                message = request_data['post']['raw']
            else:
                if 'reply_to_user' in request_data['post']:
                    if request_data['post']['reply_to_user']['username'] == 'HelperBot':
                        message = request_data['post']['raw']
                else:
                    if '@HelperBot' in request_data['post']['raw']:
                        message = request_data['post']['raw']

        if message != "":
            SESSION_ID = topic_id
            session = session_client.session_path(DIALOGFLOW_PROJECT_ID, SESSION_ID)
            text_input = dialogflow.types.TextInput(text=message, language_code=DIALOGFLOW_LANGUAGE_CODE)
            query_input = dialogflow.types.QueryInput(text=text_input)
            try:
                response = session_client.detect_intent(session=session, query_input=query_input)
            except InvalidArgument:
                raise
            
            print("Query text:", response.query_result.query_text)
            print("Detected intent:", response.query_result.intent.display_name)
            print("Detected intent confidence:", response.query_result.intent_detection_confidence)
            print("Fulfillment text:", response.query_result.fulfillment_text)
            requests.post("https://forum.ezcheats.ru/posts.json", headers=headers, data={'topic_id': topic_id, 'raw': response.query_result.fulfillment_text})
    return 'True'


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
                if 'title' in review_data['payload']:
                    msg = f"⚠️ На премодерации появился новый топик!\n" \
                        f"Автор: {created_by}\n" \
                        f"Заголовок: «{review_data['payload']['title']}»\n" \
                        f"Создано: {review_data['created_at']} \n\n" \
                        f"Пожалуйста, посмотрите: https://forum.ezcheats.ru/review/{review_data['id']}"
                else:
                     msg = f"⚠️ На премодерации появилось новое сообщение!\n" \
                        f"Автор: {created_by}\n" \
                        f"Содержание: «{review_data['payload']['raw']}»\n" \
                        f"Создано: {review_data['created_at']} \n\n" \
                        f"Пожалуйста, посмотрите: https://forum.ezcheats.ru/review/{review_data['id']}"
    if msg != "":
        vk.messages.send(peer_id=vk_chat_id, message=msg, random_id=random.randint(1, 1000000))
        
    return 'True'


if __name__ == '__main__':
    app.run(host='0.0.0.0')
