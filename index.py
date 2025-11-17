from datetime import datetime, timedelta
import json
import re
import time
import markdown
from ncatbot.core import BotClient
from ncatbot.core.api import BotAPI
from ncatbot.core.helper.forward_constructor import ForwardConstructor
from ncatbot.core.event.message_segment import Text, Image, File, Video
from ncatbot.core.event.message_segment import MessageArray
from ncatbot.plugin_system import on_message
import os
import requests
from utils import *


class MessageSender:
    def __init__(self, api: BotAPI):
        self.api = api
        self.messages = []

    def add_message(self, message: str, abstract: str):
        self.messages.append({"message": message, "abstract": abstract})

    def send_all_and_clear(self):
        if len(self.messages) == 0:
            return
        if len(self.messages) == 1:
            self.api.send_group_msg_sync(
                group_id=int(os.getenv("GHHELPER_TARGET_GROUP")),
                message=self.messages[0]["message"],
            )
            self.messages.clear()
            return
        frc = ForwardConstructor("2426919699", "GithubHelper")
        summary = ""
        for msg in self.messages:
            frc.attach_text(msg["message"])
            summary += msg["abstract"]
        self.api.send_group_msg_sync(
            group_id=int(os.getenv("GHHELPER_TARGET_GROUP")), message=summary.strip())
        self.api.post_forward_msg_sync(group_id=os.getenv(
            "GHHELPER_TARGET_GROUP"), msg=frc.to_forward())
        self.messages.clear()




bot = BotClient()


@on_message
async def handle_group_msg(ctx):
    if len(ctx.message.to_list()) > 1:
        return
    # print(ctx.group_id == os.getenv("GHHELPER_TARGET_GROUP"),ctx.group_id,type(ctx.group_id),type(os.getenv("GHHELPER_TARGET_GROUP")),os.getenv("GHHELPER_TARGET_GROUP"))
    if ctx.group_id == os.getenv("GHHELPER_TARGET_GROUP"):
        if ctx.message.to_list()[0]['type'] != 'text':
            return
        # print(ctx.group_id)
        result = re.findall(
            r"#[0-9]{1,}L", ctx.message.to_list()[0]['data']['text'])
        result = list(set(result))
        marked = []
        if result:
            print(result)
            os.makedirs("./temp", exist_ok=True)
            resp = MessageArray()
            for item in result:
                marked.append(int(item[1:-1]))
                number = int(item[1:-1])
                print(f"Fetching issue #{number}")
                response = gh.get(
                    f"https://api.github.com/repos/{os.getenv('GHHELPER_TARGET_REPO')}/issues/{number}")
                if response.status_code == 200:
                    response = response.json()
                    markdown_content = f"`#{number}`\n\n# {response['title']}\n\nAuthor:{response['user']['login']}\n\nCreated at:{response['created_at']}\n\nUpdated at:{response['updated_at']}\n\n"+(
                        "" if response['closed_at'] is None else f"Closed at:{response['closed_at']}\n\n")+response['body']
                    html_content = markdown.markdown(markdown_content, extensions=[
                                                     'fenced_code', 'tables'])
                    html_style = f"""<!DOCTYPE html>
<html>
<head>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.2.0/github-markdown.min.css">
    <style>
        .markdown-body {'{'}
            padding:10px;
        {'}'}
    </style>
</head>
<body>
<article class="markdown-body">
{html_content}
</article>
</body>
</html>
"""
                    generate_img_from_html(
                        html_style, "markdown-body", number)
                    print(f"Generated image for issue #{number}")
                    resp.add_image(Image(f'./temp/{number}.png'))
            if resp.messages:
                await ctx.reply(rtf=resp, at=False)
        result = re.findall(
            r"#[0-9]{1,}", ctx.message.to_list()[0]['data']['text'])
        result = list(set(result))
        if result:
            resp = ""
            for item in result:
                if int(item[1:]) in marked:
                    continue
                number = int(item[1:])
                if issue := generate_msg_of_number(number):
                    resp += f"{str(issue)}\n\n"
            if resp.strip() != "":
                await ctx.reply(text=resp.strip(), at=False)
        return
api = bot.run_backend(
    remote_mode=True,
    root=int(os.getenv("GHHELPER_ROOT")),
    bt_uin=int(os.getenv("GHHELPER_UIN")),
    ws_uri=os.getenv("GHHELPER_WS_URI"),
    ws_token=os.getenv("GHHELPER_WS_TOKEN"),
    webui_uri=os.getenv("GHHELPER_WEBUI_URI"),
    webui_token=os.getenv("GHHELPER_WEBUI_TOKEN"),
    debug=False,
)

mss = MessageSender(api)


def send_message(message: str, abstract):
    # api.send_group_msg_sync(group_id=int(
    #     os.getenv("GHHELPER_TARGET_GROUP")), message=message)
    # print("="*20+"\n"+message+"\n"+"="*20)
    mss.add_message(message, abstract)


with open("./visited_event.json", "r", encoding="utf-8") as f:
    if f.read().strip() == "":
        with open("./visited_event.json", "w", encoding="utf-8") as f:
            f.write("[]")


latest_issue_num = max([issue["number"] for issue in gh.get(
    f"https://api.github.com/repos/{os.getenv('GHHELPER_TARGET_REPO')}/issues").json()])
with open("./latest_issue_num.txt", "w", encoding="utf-8") as f:
    f.write(str(latest_issue_num))

while True:
    events_resp = gh.get(
        f"https://api.github.com/repos/{os.getenv('GHHELPER_TARGET_REPO')}/issues/events")
    if events_resp.status_code == 200:
        events = events_resp.json()
        events_local = json.load(
            open("./visited_event.json", "r", encoding="utf-8"))
        issue_event_map = {}
        for event in events:
            if event["id"] in events_local:
                continue
            message = ""
            if event["event"] in ["closed", "reopened", "merged"]:
                closed_reasoned = {
                    None: "",
                    "not_planned": "因非计划而",
                    "duplicate": "因重复而",
                    "completed": "因完成而",
                }
                message = {'closed': closed_reasoned[event.get('state_reason', None)]+'关闭了',
                           'reopened': '重新打开了', 'merged': '合并了'}[event['event']]
            if event['event'] == "labeled":
                label_specials = {
                    "💡 Accept": "接受了",
                    "⭕ Confirmed": "确认了",
                }
                if event['label']['name'] in label_specials:
                    message = f"{label_specials[event['label']['name']]}"
                else:
                    message = f"添加了标签 {event['label']['name']}"
            if event['event'] == "convert_to_draft":
                message = "转换为草稿状态"
            if event['event'] == "ready_for_review":
                message = "标记为准备好Review了"
            if event['event'] == "marked_as_duplicate":
                message = "标记为重复了"
            if event['event'] == "renamed":
                message = f'将标题从 "{event["rename"]["from"]}" 改为 "{event["rename"]["to"]}"'
            if event['event'] == "review_requested":
                message = f'请求 {event["requested_reviewer"]["login"]} 进行代码审查'
            if message:
                issue_event_map.setdefault(event["issue"]["number"], []).append(
                    (event['actor']['login'], message))
            events_local.append(event["id"])
        for issue_number in issue_event_map:
            actor_event_maps = {}
            for actor, message in issue_event_map[issue_number]:
                actor_event_maps.setdefault(actor, []).append(message)
            combined_messages = []
            for actor in actor_event_maps:
                cm = f"被 {actor} " + \
                    "，".join(actor_event_maps[actor])
                combined_messages.append(cm)
            if issue := generate_msg_of_number(issue_number):
                # if issue := "ISSUE":
                send_message(
                    f"#{issue_number} {','.join(combined_messages)}\n\n"+issue, f"#{issue_number} {','.join(combined_messages)}\n")

        with open("./visited_event.json", "w", encoding="utf-8") as f:
            f.write(json.dumps(events_local))
    issues = gh.get(
        f"https://api.github.com/repos/{os.getenv('GHHELPER_TARGET_REPO')}/issues")
    if issues.status_code == 200:
        issues = issues.json()
        try:
            latest_issue_num_local = int(
                open("./latest_issue_num.txt", "r").read().strip())
            new_latest_issue_num = latest_issue_num_local
            for issue in issues:
                if issue["number"] > latest_issue_num_local:
                    new_latest_issue_num = max(
                        new_latest_issue_num, issue["number"])
                    if issue := generate_msg_of_number(issue["number"]):
                        # if issue := "ISSUE":
                        send_message(message="有新的 Issue/PR \n\n"+issue,
                                     abstract=f"有新的 Issue/PR #{issue['number']} #{issue['title']}")
            with open("./latest_issue_num.txt", "w", encoding="utf-8") as f:
                f.write(str(new_latest_issue_num))
        except TypeError as e:
            print("Error return value. "+repr(e))

    mss.send_all_and_clear()

    time.sleep(60)
