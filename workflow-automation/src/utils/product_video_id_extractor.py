"""
产品页面视频ID抓取脚本
从产品页面中提取 YouTube 和 Bilibili 视频 ID，并输出 CSV 文件，方便后续导入数据库。

主要功能：
1. 从 urls.txt 文件中读取产品URL列表。
2. 对每个URL发起请求，判断页面语言（英文/中文）以决定视频ID填入的字段后缀（_en / _cn）。
3. 提取产品名称（根据语言分别填入 name_en / name_cn）和型号（model）。
4. 通过正则表达式暴力搜索页面HTML，提取 YouTube 视频ID（embed/后11位字符）和 Bilibili 视频ID（aid=数字）。
5. 将结果写入 CSV 文件，字段包含：seo_en, seo_cn, name_en, name_cn, product_link_en, product_link_cn, model, raw_content, picture1, picture2, bilibili_id_1/2/3, youtube_id_1/2/3。
6. 部分字段留空，等待手动填充（如SEO、原始内容、图片等）。
"""

import requests
from bs4 import BeautifulSoup
import csv
import re
import time
import os

# --- 配置区 ---
INPUT_FILE = 'urls.txt'                   # 输入文件，每行一个产品URL
OUTPUT_DIR = 'data'                        # 输出目录
OUTPUT_FILE = 'data/lisun_video_data.csv'  # 输出CSV文件路径

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def extract_video_ids(url):
    """
    从单个产品页面提取视频ID及其他基本信息。

    工作流程：
    1. 根据URL判断语言：若包含 '.com' 或 '/en/' 则视为英文站，否则中文站。
    2. 发送HTTP请求获取页面HTML。
    3. 提取标题（name_en/name_cn）：优先从 <div class="title_info"><h1> 中获取，否则使用 <title> 标签。
    4. 提取型号（model）：优先从 <p class="desc"> 中正则匹配 'Product No:' 等模式，若失败则从标题括号内或URL中提取。
    5. 通过正则搜索整个HTML，查找所有 YouTube 视频ID（embed/后11位）和 Bilibili 视频ID（aid=数字）。
    6. 将视频ID分别填入 youtube_id_1/2/3 和 bilibili_id_1/2/3 字段（最多各3个）。
    7. 其余字段（seo, raw_content, product_link）留空或填入URL。

    Args:
        url (str): 产品页面的完整URL

    Returns:
        dict: 包含以下字段的字典（部分字段可能为空字符串）：
            - name_en / name_cn: 产品名称（根据语言）
            - model: 产品型号
            - youtube_id_1/2/3: YouTube视频ID（最多3个）
            - bilibili_id_1/2/3: Bilibili视频ID（最多3个）
            - seo_en / seo_cn: 空，留待手动填充
            - raw_content: 空，留待手动填充
            - product_link_en / product_link_cn: 当前URL（根据语言分别填入）
        若请求失败则返回None。
    """
    print(f"🕷️ 正在扫描视频: {url} ...")
    
    # 1. 智能判断语言 (决定视频 ID 填哪个语言字段)
    is_english = '.com' in url or '/en/' in url
    lang_suffix = '_en' if is_english else '_cn'
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.encoding = 'utf-8'
        
        if response.status_code != 200:
            print(f"⚠️ 无法访问 (代码 {response.status_code})")
            return None
            
        # 将HTML转换为字符串，便于正则搜索
        html_str = response.text 
        soup = BeautifulSoup(html_str, 'html.parser')
        
        data = {}

        # --- A. 抓取基础信息 ---
        # 标题
        title_div = soup.find('div', class_='title_info')
        if title_div and title_div.h1:
            data[f'name{lang_suffix}'] = title_div.h1.text.strip()
        else:
            # 备用：从页面title标签中提取（取第一个 '-' 之前的部分）
            data[f'name{lang_suffix}'] = soup.title.text.split('-')[0].strip() if soup.title else "未找到标题"

        # 型号 (Model)
        model = ""
        if title_div:
            desc_p = title_div.find('p', class_='desc')
            if desc_p:
                desc_text = desc_p.text
                # 尝试匹配中文或英文的“产品型号：”或“Product No:”
                if '产品型号：' in desc_text:
                    model = desc_text.replace('产品型号：', '').strip()
                elif '产品型号:' in desc_text:
                    model = desc_text.replace('产品型号:', '').strip()
                elif 'Product No:' in desc_text:
                    model = desc_text.replace('Product No:', '').strip()
        if not model:
            # 若从desc中未找到，尝试从标题的括号中提取型号（如：产品名 (SLS-50W)）
            match = re.search(r'[\(\[\（](.*?)[\)\]\）]', data[f'name{lang_suffix}'])
            if match:
                model = match.group(1)
        data['model'] = model

        # --- B. 暴力抓取视频 ID (核心任务) ---
        
        # 1. YouTube ID (英文站重点)：特征 embed/ 后接 11 位字符（字母、数字、下划线、短横）
        y_ids = re.findall(r'embed/([a-zA-Z0-9_-]{11})', html_str)
        y_ids = list(set(y_ids))  # 去重

        # 2. B站 ID (中文站重点)：特征 aid=数字
        b_ids = re.findall(r'aid=(\d+)', html_str)
        b_ids = list(set(b_ids))

        # 填入对应的字段（最多各3个）
        for i in range(3):
            data[f'youtube_id_{i+1}'] = y_ids[i] if i < len(y_ids) else ""
            data[f'bilibili_id_{i+1}'] = b_ids[i] if i < len(b_ids) else ""

        # --- C. 其他字段留空 (等待手动合并) ---
        data[f'seo{lang_suffix}'] = ""      # SEO关键词，留待手动填写
        data['raw_content'] = ""             # 原始内容，留待手动粘贴（可用spider2的结果）
        data[f'product_link{lang_suffix}'] = url
        
        return data

    except Exception as e:
        print(f"❌ 出错: {e}")
        return None

# --- 主程序 ---
if __name__ == "__main__":
    # 创建输出目录（如果不存在）
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    if not os.path.exists(INPUT_FILE):
        print(f"❌ 错误：找不到 {INPUT_FILE}")
        exit()
        
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip()]

    print(f"🚀 开始扫描 {len(urls)} 个页面的视频 ID...")

    # 定义完整的数据库表头，方便后续导入
    fieldnames = [
        'seo_en', 'seo_cn', 
        'name_en', 'name_cn', 
        'product_link_en', 'product_link_cn', 
        'model', 'raw_content', 
        'picture1', 'picture2', 
        'bilibili_id_1', 'bilibili_id_2', 'bilibili_id_3', 
        'youtube_id_1', 'youtube_id_2', 'youtube_id_3'
    ]

    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for i, url in enumerate(urls):
            print(f"[{i+1}/{len(urls)}] ", end="")
            p_data = extract_video_ids(url)
            
            if p_data:
                # 补全所有字段为空，确保CSV格式完整
                row = {k: p_data.get(k, "") for k in fieldnames}
                
                # 统计抓到的视频数（仅用于日志）
                v_count = sum(1 for k,v in p_data.items() if ('youtube_id' in k or 'bilibili_id' in k) and v)
                
                print(f"✅ {p_data.get('model', '未知')} - 抓到 {v_count} 个视频 ID")
                writer.writerow(row)
            else:
                print("❌ 跳过")
            
            time.sleep(0.5)  # 礼貌延迟，避免请求过快

    print(f"\n🎉 视频 ID 采集完成！")
    print(f"📁 请打开 {OUTPUT_FILE}，将你的 SEO 关键词和内容粘贴进去，然后导入数据库！")
