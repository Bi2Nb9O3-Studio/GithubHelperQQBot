from datetime import datetime, timedelta
import json
import re
import time
from ncatbot.core import BotClient
from ncatbot.plugin_system import on_message
import os

import requests
import dotenv
dotenv.load_dotenv()


class SessionWithCatch(requests.Session):
    def request(self, *args, **kwargs):
        try:
            return super().request(*args, **kwargs)
        except requests.RequestException as e:
            print(f"HTTP Request failed: {e}")
            return requests.Response()


gh = SessionWithCatch()
gh.headers.update({
    "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}",
    "Accept": "application/vnd.github.v3+json",
    "X-GitHub-Api-Version": "2022-11-28"
})


def format_github_item_simple(item_data):
    """
    通用GitHub项目格式化 - 适配Issue和Pull Request的各种状态
    """
    # 提取基本信息
    title = item_data.get('title', '')
    number = item_data.get('number', '')

    # 判断是Issue还是Pull Request
    is_pull_request = 'pull_request' in item_data
    item_type = "PR" if is_pull_request else "Issue"

    # 状态处理
    state = item_data.get('state', '')
    draft = item_data.get('draft', False)

    # 标签处理
    labels = item_data.get('labels', [])
    label_names = [label.get('name', '') for label in labels]
    labels_text = '、'.join(label_names) if label_names else "无标签"

    # 合并状态指示（仅对PR有效）
    merge_status = ""
    if is_pull_request:
        if draft:
            state_icon = '📝草稿PR'
            merge_status = "❌ 不可合并（草稿状态）"
        elif state == 'open':
            state_icon = '🟢进行中PR'
            # 这里可以添加更详细的合并状态检查
            # 基于有限信息，我们假设非草稿的开放PR可能可以合并
            merge_status = "⏳ 可能可合并（需检查CI和冲突）"
        elif state == 'closed':
            # 检查是否已合并
            merged_at = item_data.get('pull_request', {}).get('merged_at')
            if merged_at:
                state_icon = '🟣已合并PR'
                merge_status = "✅ 已合并"
            else:
                state_icon = '❌已关闭PR'
                merge_status = "❌ 未合并"
        else:
            state_icon = f'{state}PR'
    else:
        # Issue状态
        if state == 'open':
            state_icon = '🔴进行中'
        elif state == 'closed':
            state_icon = '✅已关闭'
        else:
            state_icon = state

    user = item_data.get('user', {}).get('login', '')

    # 时间格式化
    created_at = item_data.get('created_at', '')
    try:
        created_time = (datetime.fromisoformat(
            created_at.replace('Z', '+00:00')) + timedelta(hours=8)).strftime("%m-%d %H:%M")
    except:
        created_time = created_at

    # 对于已合并的PR，显示合并时间
    if is_pull_request and state == 'closed' and item_data.get('pull_request', {}).get('merged_at'):
        merged_at = item_data['pull_request']['merged_at']
        try:
            merged_time = (datetime.fromisoformat(
                merged_at.replace('Z', '+00:00')) + timedelta(hours=8)).strftime("%m-%d %H:%M")
            time_info = f"🕒 {created_time} | 🚀 {merged_time}"
        except:
            time_info = f"🕒 {created_time}"
    else:
        time_info = f"🕒 {created_time}"

    # 构建消息
    if is_pull_request:
        # Pull Request的格式 - 添加合并状态信息和标签
        qq_message = f"""🔄 {item_type} #{number} {state_icon}
📌 {title}
🏷️ {labels_text}
👤 {user} | {time_info}
📊 {merge_status}
🔗 {item_data.get('html_url')}"""
    else:
        # Issue的格式 - 提取关键信息
        body = item_data.get('body', '') or ''

        def get_section(name):
            lines = body.split('\n')
            for i, line in enumerate(lines):
                if name in line and i+2 < len(lines):
                    return lines[i+2].strip()
            return "未提供"

        mc_version = get_section("Minecraft Version Details")
        mod_version = get_section("Version Details")

        # 模组加载器信息
        mod_loader = get_section("Mod Loader")
        if mod_loader != "未提供":
            loader_info = f" | ⚙️ {mod_loader}"
        else:
            loader_info = ""

        qq_message = f"""🐛 {item_type} #{number} {state_icon}
📌 {title}
🏷️ {labels_text}
👤 {user} | {time_info}
🎮 {mc_version} | 📦 {mod_version}{loader_info}
🔗 {item_data.get('html_url')}"""

    return qq_message


def generate_msg_of_number(number: int):
    global gh
    print(f"Fetching issue #{number}")
    response = gh.get(
        f"https://api.github.com/repos/{os.getenv('GHHELPER_TARGET_REPO')}/issues/{number}")
    if response.status_code == 200:
        issue = response.json()
        return format_github_item_simple(issue)
    return None

bot = BotClient()


@on_message
async def handle_group_msg(ctx):
    if len(ctx.message.to_list())>1:
        return
    print(ctx.group_id == os.getenv("GHHELPER_TARGET_GROUP"),ctx.group_id,type(ctx.group_id),type(os.getenv("GHHELPER_TARGET_GROUP")),os.getenv("GHHELPER_TARGET_GROUP"))
    if ctx.group_id == os.getenv("GHHELPER_TARGET_GROUP"):
        if ctx.message.to_list()[0]['type']!='text':
            return
        # print(ctx.group_id)
        result = re.findall(r"#[0-9]{1,}", ctx.message.to_list()[0]['data']['text'])
        if result:
            resp=""
            for item in result:
                number=int(item[1:])
                if issue := generate_msg_of_number(number):
                    resp+=f"{str(issue)}\n\n"
            await ctx.reply(text=resp.strip(),at=False)
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

def send_message(message: str):
    api.send_group_msg_sync(group_id=int(
        os.getenv("GHHELPER_TARGET_GROUP")), message=message)
    # print("="*20+"\n"+message+"\n"+"="*20)


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
                message = {'closed': closed_reasoned[event.get('state_reason',None)]+'关闭了',
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
            if event['event'] =="convert_to_draft":
                message = "转换为草稿状态"
            if event['event'] =="ready_for_review":
                message = "标记为准备好Review了"
            if event['event'] =="marked_as_duplicate":
                message = "标记为重复了"
            if event['event']=="renamed":
                message = f'将标题从 "{event["rename"]["from"]}" 改为 "{event["rename"]["to"]}"'
            if message:
                issue_event_map.setdefault(event["issue"]["number"], []).append((event['actor']['login'],message))
            events_local.append(event["id"])
        for issue_number in issue_event_map:
            actor_event_maps = {}
            for actor, message in issue_event_map[issue_number]:
                actor_event_maps.setdefault(actor, []).append(message)
            combined_messages = []
            for actor in actor_event_maps:
                cm = f"被 {event['actor']['login']} " + \
                    "，".join(actor_event_maps[actor])
                combined_messages.append(cm)
            if issue := generate_msg_of_number(issue_number):
            # if issue := "ISSUE":
                send_message(
                    f"#{issue_number} {','.join(combined_messages)}\n\n"+issue)

        with open("./visited_event.json", "w",encoding="utf-8") as f:
            f.write(json.dumps(events_local))
    issues = gh.get(f"https://api.github.com/repos/{os.getenv('GHHELPER_TARGET_REPO')}/issues")
    if issues.status_code == 200:
        issues = issues.json()
        latest_issue_num_local = int(open("./latest_issue_num.txt", "r").read().strip())
        new_latest_issue_num = latest_issue_num_local
        for issue in issues:
            if issue["number"] > latest_issue_num_local:
                new_latest_issue_num = max(new_latest_issue_num, issue["number"])
                if issue := generate_msg_of_number(issue["number"]):
                # if issue := "ISSUE":
                    send_message(message="有新的 Issue/PR \n\n"+issue)
        with open("./latest_issue_num.txt", "w",encoding="utf-8") as f:
            f.write(str(new_latest_issue_num))

    time.sleep(60)
