import requests
import json
import datetime
import streamlit as st
from itertools import zip_longest
import os

def basic_info():
    config = dict()
    config["access_token"] = st.secrets["access_token"]
    config['instagram_account_id'] = st.secrets.get("instagram_account_id", "")
    config["version"] = 'v16.0'
    config["graph_domain"] = 'https://graph.facebook.com/'
    config["endpoint_base"] = config["graph_domain"] + config["version"] + '/'
    return config

def InstaApiCall(url, params, request_type):
    if request_type == 'POST':
        req = requests.post(url, params)
    else:
        req = requests.get(url, params)
    res = dict()
    res["url"] = url
    res["endpoint_params"] = params
    res["endpoint_params_pretty"] = json.dumps(params, indent=4)
    res["json_data"] = json.loads(req.content)
    res["json_data_pretty"] = json.dumps(res["json_data"], indent=4)
    return res

def getUserMedia(params, pagingUrl=''):
    Params = dict()
    Params['fields'] = 'id,caption,media_type,media_url,permalink,thumbnail_url,timestamp,username,like_count,comments_count'
    Params['access_token'] = params['access_token']

    if not params['endpoint_base']:
        return None

    if pagingUrl == '':
        url = params['endpoint_base'] + params['instagram_account_id'] + '/media'
    else:
        url = pagingUrl

    return InstaApiCall(url, Params, 'GET')

def saveCount(count, filename):
    with open(filename, 'w') as f:
        json.dump(count, f, indent=4)

def getCount(filename):
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.decoder.JSONDecodeError):
        return {}

st.set_page_config(layout="wide")
params = basic_info()

if not params['instagram_account_id']:
    st.write('instagram_account_idを確認')
else:
    response = getUserMedia(params)
    if not response:
        st.write('access_tokenを確認')
    else:
        posts = response['json_data']['data'][::-1]

        NUM_COLUMNS = 6
        MAX_WIDTH = 1000
        BOX_WIDTH = int(MAX_WIDTH / NUM_COLUMNS)
        BOX_HEIGHT = 400

        show_description = st.checkbox("説明文を表示")

        posts.reverse()
        post_groups = [list(filter(None, group)) for group in zip_longest(*[iter(posts)] * NUM_COLUMNS)]

        count_filename = "count.json"
        count = getCount(count_filename)
        today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%d')
        yesterday = (datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))) - datetime.timedelta(days=1)).strftime('%Y-%m-%d')

        if today not in count:
            count[today] = {}

        if datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%H:%M') == '23:59':
            count[yesterday] = count[today]

        for post_group in post_groups:
            with st.container():
                columns = st.columns(NUM_COLUMNS)
                for i, post in enumerate(post_group):
                    with columns[i]:
                        st.image(post['media_url'], width=BOX_WIDTH, use_column_width=True)
                        st.write(f"{datetime.datetime.strptime(post['timestamp'], '%Y-%m-%dT%H:%M:%S%z').astimezone(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S')}")
                        like_count_diff = post['like_count'] - count.get(yesterday, {}).get(post['id'], {}).get('like_count', post['like_count'])
                        comment_count_diff = post['comments_count'] - count.get(yesterday, {}).get(post['id'], {}).get('comments_count', post['comments_count'])
                        st.write(f"👍: {post['like_count']} ({'+' if like_count_diff >= 0 else ''}{like_count_diff})\n💬: {post['comments_count']} ({'+' if comment_count_diff >= 0 else ''}{comment_count_diff})\n")
                        caption = post['caption']
                        if caption is not None:
                            caption = caption.strip()
                            if "[Description]" in caption:
                                caption = caption.split("[Description]")[1].lstrip()
                            if "[Tags]" in caption:
                                caption = caption.split("[Tags]")[0].rstrip()
                            caption = caption.replace("#", "")
                            caption = caption.replace("[Equip]", "📷")
                            caption = caption.replace("[Develop]", "🖨")
                            if show_description:
                                st.write(caption or "No caption provided")
                            else:
                                st.write(caption[:0] if caption is not None and len(caption) > 50 else caption or "No caption provided")
                        count[today][post['id']] = {'like_count': post['like_count'], 'comments_count': post['comments_count']}
        
        saveCount(count, count_filename)
