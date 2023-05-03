import requests
import json
import datetime
import streamlit as st
from itertools import zip_longest
import os
import seaborn as sns
import matplotlib.pyplot as plt
import pandas as pd
import japanize_matplotlib

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

def getUser(params):
    Params = dict()
    Params['fields'] = 'followers_count'
    Params['access_token'] = params['access_token']

    if not params['endpoint_base']:
        return None

    url = params['endpoint_base'] + params['instagram_account_id']

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

count_filename = "count.json"

if not params['instagram_account_id']:
    st.write('.envファイルでinstagram_account_idを確認')
else:
    response = getUserMedia(params)
    user_response = getUser(params)
    if not response or not user_response:
        st.write('.envファイルでaccess_tokenを確認')
    else:
        posts = response['json_data']['data'][::-1]
        user_data = user_response['json_data']
        followers_count = user_data.get('followers_count', 0)

NUM_COLUMNS = 6
MAX_WIDTH = 1000
BOX_WIDTH = int(MAX_WIDTH / NUM_COLUMNS)
BOX_HEIGHT = 400

yesterday = (datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))) - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
follower_diff = followers_count - getCount(count_filename).get(yesterday, {}).get('followers_count', followers_count)
st.markdown(f'''
    Follower: {followers_count} ({'+' if follower_diff >= 0 else ''}{follower_diff})
    ''', unsafe_allow_html=True)

show_description = st.checkbox("キャプションを表示")
show_summary_chart = st.checkbox("サマリーチャートを表示")
show_like_comment_chart = st.checkbox("いいね/コメント数グラフを表示")

posts.reverse()
post_groups = [list(filter(None, group)) for group in zip_longest(*[iter(posts)] * NUM_COLUMNS)]

count = getCount(count_filename)
today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%d')

if today not in count:
    count[today] = {}

count[today]['followers_count'] = followers_count

if datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%H:%M') == '23:59':
    count[yesterday] = count[today]

max_like_diff = 0
max_comment_diff = 0
summary_chart_data = {"Date": [], "Count": [], "Type": []}

for post_group in post_groups:
    for post in post_group:
        like_count_diff = post['like_count'] - count.get(yesterday, {}).get(post['id'], {}).get('like_count', post['like_count'])
        comment_count_diff = post['comments_count'] - count.get(yesterday, {}).get(post['id'], {}).get('comments_count', post['comments_count'])
        max_like_diff = max(like_count_diff, max_like_diff)
        max_comment_diff = max(comment_count_diff, max_comment_diff)

if show_summary_chart:
    for date in count.keys():
        if date != today:
            summary_chart_data["Date"].append(datetime.datetime.strptime(date, '%Y-%m-%d').strftime('%m/%d'))
            summary_chart_data["Count"].append(count[date].get("followers_count", 0))
            summary_chart_data["Type"].append("フォロワー")
        for post_id in count[date].keys():
            if post_id not in ["followers_count"]:
                summary_chart_data["Date"].append(datetime.datetime.strptime(date, '%Y-%m-%d').strftime('%m/%d'))
                summary_chart_data["Count"].append(count[date][post_id].get("like_count", 0))
                summary_chart_data["Type"].append("いいね")
                summary_chart_data["Date"].append(datetime.datetime.strptime(date, '%Y-%m-%d').strftime('%m/%d'))
                summary_chart_data["Count"].append(count[date][post_id].get("comments_count", 0))
                summary_chart_data["Type"].append("コメント")

    summary_chart_df = pd.DataFrame(summary_chart_data)
    fig, ax1 = plt.subplots(figsize=(15, 10))
    summary_chart_palette = {"フォロワー": "lightblue", "いいね": "orange", "コメント": "green"}
    sns.lineplot(data=summary_chart_df[summary_chart_df["Type"] != "コメント"], x="Date", y="Count", hue="Type", palette=summary_chart_palette, ax=ax1)
    ax1.set_xlabel("日付")
    ax1.set_ylabel("いいね/フォロワー")

    ax2 = ax1.twinx()
    sns.lineplot(data=summary_chart_df[summary_chart_df["Type"] == "コメント"], x="Date", y="Count", color="green", ax=ax2)
    ax2.set_ylabel("コメント")

    plt.title("日別 サマリーチャート")
    st.pyplot(fig)

for post_group in post_groups:
    with st.container():
        columns = st.columns(NUM_COLUMNS)
        for i, post in enumerate(post_group):
            with columns[i]:
                st.image(post['media_url'], width=BOX_WIDTH, use_column_width=True)
                st.write(f"{datetime.datetime.strptime(post['timestamp'], '%Y-%m-%dT%H:%M:%S%z').astimezone(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S')}")
                like_count_diff = post['like_count'] - count.get(yesterday, {}).get(post['id'], {}).get('like_count', post['like_count'])
                comment_count_diff = post['comments_count'] - count.get(yesterday, {}).get(post['id'], {}).get('comments_count', post['comments_count'])
                st.markdown(
                f"👍: {post['like_count']} <span style='{'' if like_count_diff != max_like_diff or max_like_diff == 0 else 'color:green;'}'>({'+1' if like_count_diff >= 0 else ''}{like_count_diff})"
                f"\n💬: {post['comments_count']} <span style='{'' if comment_count_diff != max_comment_diff or max_comment_diff == 0 else 'color:green;'}'>({'+1' if comment_count_diff >= 0 else ''}{comment_count_diff})",
                unsafe_allow_html=True)

                likes_diff: int = post['like_count'] - count.get(yesterday, {}).get(post['id'], {}).get('like_count', post['like_count'])
                comments_diff: int = post['comments_count'] - count.get(yesterday, {}).get(post['id'], {}).get('comments_count', post['comments_count'])
                max_like_diff = max(likes_diff, max_like_diff)
                max_comment_diff = max(comments_diff, max_comment_diff)

                if show_like_comment_chart:
                    like_comment_chart_data = {"Date": [], "Count": [], "Type": []}
                    for date in count.keys():
                        if date != today and post["id"] in count[date]:
                            prev_count = count[date][post["id"]]
                            likes_diff = post['like_count'] - prev_count.get("like_count", 0)
                            comments_diff = post['comments_count'] - prev_count.get("comments_count", 0)

                            like_comment_chart_data["Date"].append(datetime.datetime.strptime(date, '%Y-%m-%d').strftime('%m/%d'))
                            like_comment_chart_data["Count"].append(likes_diff)
                            like_comment_chart_data["Type"].append("Like")

                            like_comment_chart_data["Date"].append(datetime.datetime.strptime(date, '%Y-%m-%d').strftime('%m/%d'))
                            like_comment_chart_data["Count"].append(comments_diff)
                            like_comment_chart_data["Type"].append("Comment")

                    if like_comment_chart_data["Date"]:
                        like_comment_chart_df = pd.DataFrame(like_comment_chart_data)
                        fig, ax3 = plt.subplots(figsize=(5, 3))
                        like_comment_chart_palette = {"Like": "orange", "Comment": "green"}
                        sns.lineplot(data=like_comment_chart_df[like_comment_chart_df["Type"] == "Like"], x="Date", y="Count", color="orange", ax=ax3)
                        ax3.set_xlabel("日付")
                        ax3.set_ylabel("いいね")

                        ax4 = ax3.twinx()
                        sns.lineplot(data=like_comment_chart_df[like_comment_chart_df["Type"] == "Comment"], x="Date", y="Count", color="green", ax=ax4)
                        ax4.set_ylabel("コメント")

                        plt.title("日別 いいね/コメント数")
                        st.pyplot(fig)

                caption = post['caption']
                if caption is not None:
                    caption = caption.strip()
                    if "[Description]" in caption:
                        caption = caption.split("[Description]")[1].lstrip()
                    if "[Tags]" in caption:
                        caption = caption.split("[Tags]")[0].rstrip()
                    caption = caption.replace("#", "")
                    caption = caption.replace("[model]", "👗")
                    caption = caption.replace("[Equip]", "📷")
                    caption = caption.replace("[Develop]", "🖨")
                    if show_description:
                        st.write(caption or "No caption provided")
                    else:
                        st.write(caption[:0] if caption is not None and len(caption) > 50 else caption or "No caption provided")
                    count[today][post['id']] = {'like_count': post['like_count'], 'comments_count': post['comments_count']}

saveCount(count, count_filename)
