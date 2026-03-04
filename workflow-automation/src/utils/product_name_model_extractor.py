"""
产品名称和型号抓取脚本
专门从产品页面提取产品标题和型号信息，并生成“型号+名称”的组合，方便用于SEO标题或数据整理。

目标HTML结构：
    <div class="title_info">
        <h1>产品名称</h1>
        <p class="desc">Product No: 产品型号</p>
    </div>

主要功能：
1. 从 urls.txt 中读取产品URL列表（每行一个）。
2. 对每个URL发起请求，定位 <div class="title_info"> 区域。
3. 提取产品名称（<h1> 标签内容，若不存在则从 <title> 标签中获取）。
4. 提取产品型号，尝试多种匹配模式：
   - 从 <p class="desc"> 中匹配 "Product No:"、"产品型号："、"Model:" 等关键字后的型号。
   - 若失败，尝试从URL路径中提取（如 /product/clamp-2/ 中的 clamp-2）。
   - 若仍失败，尝试从产品名称的括号中提取（如 "产品名 (SLS-50W)" 中的 SLS-50W）。
5. 生成组合信息："{型号} {名称}"。
6. 将结果（组合信息 + URL）保存到CSV文件。
7. 记录抓取失败的URL，便于后续排查。
"""

import requests
from bs4 import BeautifulSoup
import csv
import time
import os
import re
from typing import List, Dict, Optional
from urllib.parse import urlparse

def extract_product_info(url: str) -> Optional[Dict]:
    """
    从产品页面提取名称和型号信息。

    工作流程：
    1. 发送HTTP请求，获取页面HTML。
    2. 定位 <div class="title_info"> 区域。
    3. 从 <h1> 中提取产品名称，若不存在则从 <title> 标签中提取（取 '-' 之前的部分）。
    4. 从 <p class="desc"> 中提取产品型号，通过多种正则模式匹配。
    5. 若型号未找到，尝试从URL路径中提取（匹配形如 /product/xxxx-xxxx/ 的模式）。
    6. 若仍未找到，尝试从产品名称的括号内提取（如 "名称 (型号)"）。
    7. 生成组合信息："{型号} {名称}"。
    8. 返回包含组合信息、型号、名称和URL的字典。

    Args:
        url (str): 产品页面URL

    Returns:
        Optional[Dict]: 包含以下字段的字典，若抓取失败则返回None
            - 'combined_info': 型号 + 名称的组合字符串
            - 'model': 产品型号
            - 'name': 产品名称
            - 'url': 原始URL
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    }
    
    try:
        print(f"正在抓取: {url[:60]}...")
        
        # 1. 请求页面
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = 'utf-8'
        
        if response.status_code != 200:
            print(f"  ⚠️ 请求失败 (状态码 {response.status_code})")
            return None
        
        # 2. 解析HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 3. 查找标题信息区域
        title_info_div = soup.find('div', class_='title_info')
        
        if not title_info_div:
            print(f"  ⚠️ 未找到标题信息区域")
            return None
        
        # 4. 提取产品名称
        product_name = ""
        h1_tag = title_info_div.find('h1')
        if h1_tag:
            product_name = h1_tag.get_text(strip=True)
        else:
            # 备用：从页面标题提取（取第一个 '-' 之前的部分）
            title_tag = soup.find('title')
            if title_tag:
                product_name = title_tag.get_text(strip=True).split('-')[0].strip()
        
        if not product_name:
            print(f"  ⚠️ 未找到产品名称")
            return None
        
        # 5. 提取产品型号
        product_model = ""
        desc_p = title_info_div.find('p', class_='desc')
        
        if desc_p:
            desc_text = desc_p.get_text(strip=True)
            # 尝试从多种格式中提取型号
            patterns = [
                r'Product No:\s*([A-Za-z0-9-]+)',    # 英文格式
                r'产品型号：\s*([A-Za-z0-9-]+)',      # 中文格式带冒号
                r'产品型号:\s*([A-Za-z0-9-]+)',       # 中文格式带英文冒号
                r'型号：\s*([A-Za-z0-9-]+)',          # 简写中文
                r'型号:\s*([A-Za-z0-9-]+)',           # 简写中文带英文冒号
                r'Model:\s*([A-Za-z0-9-]+)',          # 英文简写
            ]
            
            for pattern in patterns:
                match = re.search(pattern, desc_text)
                if match:
                    product_model = match.group(1)
                    break
        
        # 如果从desc中没有找到，尝试从其他位置查找
        if not product_model:
            # 6. 从URL路径中提取型号，例如 /products/xxxx/型号-xxxx.html
            parsed_url = urlparse(url)
            path = parsed_url.path
            # 匹配路径末尾的类似 "clamp-2" 或 "gngpl-6216d" 的模式
            model_match = re.search(r'/([a-z0-9]+-[a-z0-9]+)/?$', path, re.IGNORECASE)
            if model_match:
                product_model = model_match.group(1).upper()
            
            # 7. 从名称中括号内提取型号，如 "产品名 (SLS-50W)"
            if not product_model:
                name_match = re.search(r'[\(\[\（]([A-Za-z0-9-]+)[\)\]\）]', product_name)
                if name_match:
                    product_model = name_match.group(1)
        
        # 如果还是没有找到型号，使用占位符
        if not product_model:
            product_model = "UNKNOWN"
            print(f"  ⚠️ 未找到产品型号，使用占位符")
        
        # 8. 构建组合信息：型号 + 名称
        combined_info = f"{product_model} {product_name}"
        
        print(f"  ✅ 提取成功: {product_model}")
        
        return {
            'combined_info': combined_info,
            'model': product_model,
            'name': product_name,
            'url': url
        }
        
    except Exception as e:
        print(f"  ❌ 抓取出错: {str(e)[:50]}")
        return None

def batch_crawl_product_info(url_list: List[str], output_file: str = '产品信息.csv') -> None:
    """
    批量抓取产品信息，并保存到CSV文件。

    遍历URL列表，对每个URL调用 extract_product_info()，收集成功的结果。
    将结果写入CSV文件，包含两列：'型号+名字' 和 '链接'。
    同时记录失败的URL到 '抓取失败.txt'。

    Args:
        url_list (List[str]): 产品URL列表
        output_file (str): 输出的CSV文件路径，默认为 '产品信息.csv'
    """
    print(f"🚀 开始批量抓取产品信息，共 {len(url_list)} 个产品页面")
    print("=" * 60)
    
    results = []
    failed_urls = []
    
    for i, url in enumerate(url_list, 1):
        url = url.strip()
        if not url:
            continue
        
        print(f"[{i}/{len(url_list)}] ", end="")
        
        product_info = extract_product_info(url)
        
        if product_info:
            results.append(product_info)
        else:
            failed_urls.append(url)
            print(f"  ❌ 抓取失败")
        
        # 礼貌延迟，避免请求过快
        if i < len(url_list):
            time.sleep(1)
    
    print("\n" + "=" * 60)
    
    # 保存结果到CSV
    if results:
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['型号+名字', '链接'])
            for result in results:
                writer.writerow([result['combined_info'], result['url']])
        
        print(f"🎉 批量抓取完成！")
        print(f"📁 结果保存至: {output_file}")
        print(f"📊 成功: {len(results)}/{len(url_list)} 个页面")
        
        # 显示样本
        if results:
            print(f"\n📄 样本预览:")
            print("-" * 60)
            for i, result in enumerate(results[:3]):
                print(f"{i+1}. {result['combined_info'][:80]}...")
                print(f"   {result['url']}")
        
        # 保存失败记录
        if failed_urls:
            with open('抓取失败.txt', 'w', encoding='utf-8') as f:
                for url in failed_urls:
                    f.write(url + '\n')
            print(f"📝 失败URL列表已保存至: 抓取失败.txt")
    
    else:
        print("❌ 所有页面抓取失败")

def read_urls_from_file(filename: str = 'urls.txt') -> List[str]:
    """
    从文本文件中读取URL列表，忽略空行和以'#'开头的注释行。

    Args:
        filename (str): 文件路径，默认为'urls.txt'

    Returns:
        List[str]: URL列表
    """
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        return urls
    except FileNotFoundError:
        print(f"⚠️ 文件 {filename} 不存在")
        return []

def create_sample_urls_file():
    """
    创建示例 urls.txt 文件（如果不存在）。
    包含几个示例URL和注释说明。
    """
    if not os.path.exists('urls.txt'):
        sample_urls = [
            "# 产品URL列表（每行一个）",
            "# 示例：",
            "https://www.lisungroup.com/products/goniophotometer/lm-79-moving-detector-goniophotometer.html",
            "https://www.lisungroup.com/product/clamp-2/",
            "https://www.lisungroup.com/product/gngpl-6216d/",
            "https://www.lisungroup.com/product/sls-50w/",
        ]
        
        with open('urls.txt', 'w', encoding='utf-8') as f:
            for url in sample_urls:
                f.write(url + '\n')
        
        print("✅ 已创建示例 urls.txt 文件")

def main():
    """
    主程序入口：
        1. 显示工具信息。
        2. 创建示例文件。
        3. 读取URL列表。
        4. 询问用户输出文件名。
        5. 确认后启动批量抓取。
        6. 输出耗时和统计信息。
    """
    print("=" * 60)
    print("产品名称和型号抓取工具")
    print("目标结构: <div class='title_info'><h1>名称</h1><p class='desc'>Product No: 型号</p></div>")
    print("输出格式: CSV文件，包含'型号+名字'和'链接'两列")
    print("=" * 60)
    
    # 检查并创建示例文件
    create_sample_urls_file()
    
    # 从urls.txt读取URL
    url_list = read_urls_from_file('urls.txt')
    
    if not url_list:
        print("请在同目录的 urls.txt 文件中添加产品URL，每行一个")
        input("按Enter键退出...")
        return
    
    # 询问输出文件名
    default_output = '产品信息_' + time.strftime('%Y%m%d_%H%M') + '.csv'
    output_file = input(f"📁 输出文件名 (默认: {default_output}): ").strip()
    if not output_file:
        output_file = default_output
    
    # 确认开始
    print(f"\n即将抓取 {len(url_list)} 个产品页面")
    confirm = input("是否开始？ (y/n): ").strip().lower()
    
    if confirm != 'y':
        print("取消操作")
        return
    
    # 开始批量抓取
    start_time = time.time()
    batch_crawl_product_info(url_list, output_file)
    end_time = time.time()
    
    print(f"\n⏱️ 总耗时: {end_time - start_time:.2f} 秒")
    print(f"📊 平均每个产品: {(end_time - start_time) / len(url_list):.2f} 秒")
    print("\n✨ 任务完成！")
    print("=" * 60)

if __name__ == "__main__":
    main()
