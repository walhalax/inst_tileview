import requests
import json
import datetime
import streamlit as st
from itertools import zip_longest
import os
import seaborn as sns
import pandas as pd
import numpy as np
import japanize_matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from github import Github
import base64

def basic_info():
    config = dict()
    config["access_token"] = st.secrets["instagram_access_token"]
    config['instagram_account_id'] = st.secrets.get("instagram_account_id", "")
    config["version"] = 'v16.0'
    config["graph_domain"] = 'https://graph.facebook.com/'
    config["endpoint_base"] = config["graph_domain"] + config["version"] + '/'
    config["github_token"] = st.secrets["github_token"]
    config["github_repo"] = st.secrets["github_repo"]
    config["github_path"] = "count.json"
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

def saveCount(count, filename, config):
    headers = {"Authorization": f"token {config['github_token']}"}
    url = f"https://api.github.com/repos/{config['github_repo']}/contents/{filename}"    
    req = requests.get(url, headers=headers)

    if req.status_code == 200:
        content = json.loads(req.content)
        if "sha" in content:
            sha = content["sha"]
        else:
            print("Error: 'sha' key not found in the content.")
            return
    else:
        print(f"Creating count.json as it does not exist in the repository")
        data = {
            "message": "Create count.json",
            "content": base64.b64encode(json.dumps(count).encode("utf-8")).decode("utf-8"),
        }
        req = requests.put(url, headers=headers, data=json.dumps(data))
        if req.status_code == 201:
            print("count.json created successfully")
        else:
            print(f"Error: Request failed with status code {req.status_code}")
        return

    update_data = {
        "message": "Update count.json",
        "content": base64.b64encode(json.dumps(count).encode("utf-8")).decode("utf-8"),
        "sha": sha
    }
    update_req = requests.put(url, headers=headers, data=json.dumps(update_data))
    if update_req.status_code == 200:
        print("count.json updated successfully")
    else:
        print(f"Error: Request failed with status code {update_req.status_code}")

def getCount(filename, config):
    headers = {"Authorization": f"token {config['github_token']}"}
    url = f"https://api.github.com/repos/{config['github_repo']}/contents/{filename}"
    req = requests.get(url, headers=headers)
    if req.status_code == 200:
        content = base64.b64decode(json.loads(req.content)["content"]).decode("utf-8")
        return json.loads(content)
    else:
        return {}

st.set_page_config(layout="wide")
params = basic_info()

count_filename = params["github_path"]

if not params['instagram_account_id']:
    st.write('instagram_account_idが無効')
else:
    response = getUserMedia(params)
    user_response = getUser(params)
   # print("getUserMedia response: ", response) #データ取得チェック用コマンド
   # print("getUser response: ", user_response) #データ取得チェック用コマンド
    if not response or not user_response:
        st.write('access_tokenを無効')
    else:
        posts = response['json_data']['data'][::-1]
        user_data = user_response['json_data']
        followers_count = user_data.get('followers_count', 0)

        NUM_COLUMNS = 6
        MAX_WIDTH = 1000
        BOX_WIDTH = int(MAX_WIDTH / NUM_COLUMNS)
        BOX_HEIGHT = 400

        yesterday = (datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))) - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        follower_diff = followers_count - getCount(count_filename, params).get(yesterday, {}).get('followers_count', followers_count)
        upper_menu = st.expander("メニューを開閉", expanded=False)
        with upper_menu:
            show_description = st.checkbox("キャプションを表示")
            show_summary_chart = st.checkbox("サマリーチャートを表示")
            show_likes_comments_chart = st.checkbox("各投稿チャートの表示")

        posts.reverse()
        post_groups = [list(filter(None, group)) for group in zip_longest(*[iter(posts)] * NUM_COLUMNS)]

        count = getCount(count_filename, params)
        today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%d')

        if today not in count:
            count[today] = {}

        count[today]['followers_count'] = followers_count

        if datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%H:%M') == '23:59':
            count[yesterday] = count[today]

        max_like_diff = 0
        max_comment_diff = 0
        total_like_diff = 0
        total_comment_diff = 0
        for post_group in post_groups:
            for post in post_group:
                like_count_diff = post['like_count'] - count.get(yesterday, {}).get(post['id'], {}).get('like_count', post['like_count'])
                comment_count_diff = post['comments_count'] - count.get(yesterday, {}).get(post['id'], {}).get('comments_count', post['comments_count'])
                max_like_diff = max(like_count_diff, max_like_diff)
                max_comment_diff = max(comment_count_diff, max_comment_diff)
                total_like_diff += like_count_diff
                total_comment_diff += comment_count_diff
                count[today][post['id']] = {'like_count': post['like_count'], 'comments_count': post['comments_count']}
        saveCount(count, count_filename, params)

        st.markdown(
            f'<h4 style="font-size:1.2em;">👥: {followers_count} ({"+" if follower_diff > 0 else ("-" if follower_diff < 0 else "")}{abs(follower_diff)}) / 当日👍: {total_like_diff} / 当日💬: {total_comment_diff}</h4>',
            unsafe_allow_html=True)

        if show_summary_chart:
            st.markdown("**")
            # Prepare data for the summary chart
            daily_diff = []
            for key, value in count.items():
                date = datetime.datetime.strptime(key, "%Y-%m-%d")
                daily_data = {"Date": date,
                              "Likes": 0,
                              "Comments": 0,
                              "Followers": value.get("followers_count", 0)}
                for post_id, post_data in value.items():
                    if post_id != "followers_count":
                        daily_data["Likes"] += post_data.get("like_count", 0)
                        daily_data["Comments"] += post_data.get("comments_count", 0)
                daily_diff.append(daily_data)
            daily_diff_df = pd.DataFrame(daily_diff)
            daily_diff_df["Likes_Diff"] = daily_diff_df["Likes"].diff().fillna(0)
            daily_diff_df["Comments_Diff"] = daily_diff_df["Comments"].diff().fillna(0)

            # Plot the summary chart
            sns.set_style("darkgrid")
            sns.set(font='IPAexGothic')
            fig, ax1 = plt.subplots(figsize=(6, 3))
            ax2 = ax1.twinx()
            sns.lineplot(x=daily_diff_df['Date'], y=daily_diff_df["Followers"], ax=ax1, color="blue", label="フォロワー")
            sns.lineplot(x=daily_diff_df['Date'], y=daily_diff_df["Likes_Diff"], ax=ax1, color="orange", label="いいね")
            sns.lineplot(x=daily_diff_df['Date'], y=daily_diff_df["Comments_Diff"], ax=ax2, color="green", label="コメント")
            h1, l1 = ax1.get_legend_handles_labels()
            h2, l2 = ax2.get_legend_handles_labels()
            ax1.legend(h1 + h2, l1 + l2, loc="upper left")
            ax1.set_xlabel("日付")
            ax1.set_ylabel("フォロワー数/全いいね数")
            ax2.set_ylabel("全コメント数")
            ax1.set_xlim([daily_diff_df['Date'].min(), daily_diff_df['Date'].max()])
            ax1.set_xticks(daily_diff_df['Date'].unique())
            ax1.set_xticklabels([d.strftime('%-m/%-d') for d in daily_diff_df['Date']])
            ax1.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, pos: '{:,.0f}'.format(x)))
            ax2.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, pos: '{:,.0f}'.format(x)))
            plt.xticks(rotation=45)
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
                            f"👍: {post['like_count']} <span style='{'' if like_count_diff != max_like_diff or max_like_diff == 0 else 'color:green;'}'>({like_count_diff:+d})</span>"
                            f"\n💬: {post['comments_count']} <span style='{'' if comment_count_diff != max_comment_diff or max_comment_diff == 0 else 'color:green;'}'>({comment_count_diff:+d})</span>",
                            unsafe_allow_html=True)
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

                        if show_likes_comments_chart:
                            post_id = post['id']
                            daily_data = []
                            for key, value in count.items():
                                date = datetime.datetime.strptime(key, "%Y-%m-%d")
                                daily_data.append({"Date": date,
                                                    "Likes": value.get(post_id, {}).get("like_count", 0),
                                                    "Comments": value.get(post_id, {}).get("comments_count", 0)})
                            daily_df = pd.DataFrame(daily_data)
                            daily_df["Likes_Diff"] = daily_df["Likes"].diff().fillna(0)
                            daily_df["Comments_Diff"] = daily_df["Comments"].diff().fillna(0)

                            sns.set_style("darkgrid")
                            sns.set(font='IPAexGothic')
                            fig, ax1 = plt.subplots(figsize=(6, 3))
                            ax2 = ax1.twinx()
                            sns.lineplot(x=daily_df['Date'], y=daily_df["Likes_Diff"], ax=ax1, color="orange", label="いいね")
                            sns.lineplot(x=daily_df['Date'], y=daily_df["Comments_Diff"], ax=ax2, color="green", label="コメント")
                            h1, l1 = ax1.get_legend_handles_labels()
                            h2, l2 = ax2.get_legend_handles_labels()
                            ax1.legend(h1 + h2, l1 + l2, loc="upper left")
                            ax1.set_xlabel("日付")
                            ax1.set_ylabel("いいね数")
                            ax2.set_ylabel("コメント数")
                            ax1.set_xlim([daily_df['Date'].min(), daily_df['Date'].max()])
                            ax1.set_xticks(daily_df['Date'].unique())
                            ax1.set_xticklabels([d.strftime('%-m/%-d') for d in daily_df['Date']])
                            ax1.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, pos: '{:,.0f}'.format(x)))
                            ax2.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, pos: '{:,.0f}'.format(x)))
                            plt.xticks(rotation=45)
                            st.pyplot(fig)

                            if show_description:
                                st.write(caption or "No caption provided")
                            else:
                                st.write("")
