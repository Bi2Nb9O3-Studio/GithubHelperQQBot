import os
import requests
import selenium
from datetime import datetime, timedelta
import base64

import selenium.common
import selenium.types
import selenium.webdriver
import selenium
import selenium.webdriver.common
import selenium.webdriver.common.by
import selenium.webdriver.edge
import selenium.webdriver.edge.options

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


def ensure_path(path:str):
    """确保路径存在"""
    if not os.path.exists(path):
        os.makedirs(path)

def download_file(url: str, filename:str) -> bool:
    requests.get(url, stream=True)
    with open(filename, "wb") as file:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            for chunk in response.iter_content(1024):
                file.write(chunk)
            return True
    return False
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


options = selenium.webdriver.EdgeOptions()
options.add_argument("--headless=new")  # 新的无头模式
driver = selenium.webdriver.Edge(options=options)

def generate_img_from_html(html_str:str,target_id:str,number:int) -> bool:
    ensure_path("./temp")
    # html_bs64 = base64.b64encode(html_str.encode('utf-8')).decode('utf-8')
    # driver.get("data:text/html;base64," + html_bs64)
    with open(f"./temp/{number}.html","w",encoding="utf-8") as f:
        f.write(html_str)
    driver.get("file:///"+os.path.abspath(f"./temp/{number}.html"))
    width = driver.execute_script(
        "return Math.max(document.body.scrollWidth, document.body.offsetWidth, document.documentElement.clientWidth, document.documentElement.scrollWidth, document.documentElement.offsetWidth);")
    height = driver.execute_script(
        "return Math.max(document.body.scrollHeight, document.body.offsetHeight, document.documentElement.clientHeight, document.documentElement.scrollHeight, document.documentElement.offsetHeight);")
    print(width, height)
    # 将浏览器的宽高设置成刚刚获取的宽高
    driver.set_window_size(width + 100, height + 100)
    element = driver.find_elements(selenium.webdriver.common.by.By.CLASS_NAME, target_id)[0]
    print(f"Taking screenshot for issue #{number}", element)
    return element.screenshot(f'./temp/{number}.png')
