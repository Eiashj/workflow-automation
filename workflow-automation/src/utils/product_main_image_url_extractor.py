"""
产品第一张主图URL抓取工具
专门抓取主图区的第一张图片URL，输出到Excel，不下载图片。
主图区结构预期：
    div.img_info
    ├─ div.swiper-wrapper         ← 主图容器（大图）
    │   └─ a.switch_item          ← 单张或多张，data-src 存 1080×1080 原图
    │        img[data-src]        ← 768×768 预览图（备选）
    └─ div.img_nav                ← 缩略图导航（小图）
        └─ a > img[data-src]      ← 100×100 缩略图

只获取代码顺序中首次在主图区出现的图片的对应大图URL（优先使用1080×1080版本）。

主要功能：
1. 从 urls.txt 中读取产品URL列表。
2. 对每个URL发起请求，定位主图区。
3. 采用多级策略提取第一张主图的URL：
   - 优先从 a.switch_item 的 data-src 获取1080×1080原图。
   - 若不存在，则从 img[data-src] 获取768×768预览图。
   - 若仍不存在，从缩略图区域 (img_nav) 提取第一个缩略图URL，并尝试转换为大图URL（去掉尺寸后缀或替换为1080×1080版本）。
4. 验证URL有效性（扩展名、路径特征、排除logo等）。
5. 记录抓取结果（页面URL、产品型号、第一张主图URL、文件名、状态等）到Excel文件，包含成功和失败记录。
6. 提供重试机制和统计信息。
"""

import requests
from bs4 import BeautifulSoup
import os
import time
import re
from typing import List, Dict, Optional
from urllib.parse import urlparse, urljoin
import pandas as pd

def extract_product_model(soup: BeautifulSoup) -> Optional[str]:
    """
    从页面中提取产品型号，尝试多种来源：
        1. 查找包含 'Product No:' 的 <p> 标签，通过正则提取型号。
        2. 查找 class='desc' 的元素，从中提取型号。
        3. 若均失败，返回 None。

    Args:
        soup (BeautifulSoup): 解析后的页面对象

    Returns:
        Optional[str]: 产品型号字符串，未找到则返回 None
    """
    try:
        # 查找包含"Product No:"的段落
        for p_tag in soup.find_all('p'):
            text = p_tag.get_text(strip=True)
            if 'Product No:' in text:
                match = re.search(r'Product No:\s*([A-Za-z0-9-]+)', text)
                if match:
                    return match.group(1)
        
        # 备用查找方式：通过 class='desc' 查找
        desc_element = soup.find(class_='desc')
        if desc_element:
            text = desc_element.get_text(strip=True)
            match = re.search(r'Product No:\s*([A-Za-z0-9-]+)', text)
            if match:
                return match.group(1)
        
        return None
    except Exception as e:
        print(f"  型号提取出错: {str(e)[:50]}")
        return None

def extract_main_image_area(soup: BeautifulSoup) -> Optional[BeautifulSoup]:
    """
    定位主图区 div.img_info，若未找到则尝试备用方案：
        - 查找 class 包含 'swiper' 的 div
        - 查找任何 class 包含 'img'、'image' 或 'product' 的 div

    Args:
        soup (BeautifulSoup): 解析后的页面对象

    Returns:
        Optional[BeautifulSoup]: 主图区对应的 BeautifulSoup 标签对象，未找到则返回 None
    """
    try:
        # 查找主图区容器
        img_info_div = soup.find('div', class_='img_info')
        
        if not img_info_div:
            # 备用：查找包含主图的swiper容器
            img_info_div = soup.find('div', class_=re.compile(r'swiper.*'))
            
        if not img_info_div:
            # 再备用：查找产品图片相关的容器
            for div in soup.find_all('div'):
                classes = div.get('class', [])
                if classes and ('img' in str(classes) or 'image' in str(classes) or 'product' in str(classes)):
                    img_info_div = div
                    break
        
        return img_info_div
    except Exception as e:
        print(f"  定位主图区出错: {str(e)[:50]}")
        return None

def extract_first_main_image_url(img_info_div: BeautifulSoup, base_url: str) -> Optional[str]:
    """
    从主图区提取第一张主图的URL，采用多级策略：
        1. 查找第一个 a.switch_item 的 data-src 属性（1080×1080原图）。
        2. 若未找到，查找第一个 img 的 data-src 属性（768×768预览图）。
        3. 若仍未找到，从缩略图区域 (img_nav) 提取第一个缩略图的 data-src，并尝试转换为大图URL：
           - 将 '-100x100' 替换为 '' 得到原始图
           - 将 '-100x100' 替换为 '-1080x1080' 得到1080×1080版本
        4. 返回处理后的URL（优先使用1080×1080版本）。

    Args:
        img_info_div (BeautifulSoup): 主图区标签对象
        base_url (str): 基础URL，用于拼接相对路径

    Returns:
        Optional[str]: 第一张主图的URL，未找到则返回 None
    """
    if not img_info_div:
        return None
    
    try:
        # 策略1：查找第一个 a.switch_item 的 data-src（1080×1080原图）
        first_switch_item = img_info_div.find('a', class_='switch_item')
        if first_switch_item:
            img_url = first_switch_item.get('data-src')
            if img_url and not img_url.startswith('data:image'):
                if not img_url.startswith(('http://', 'https://')):
                    img_url = urljoin(base_url, img_url)
                return img_url
        
        # 策略2：查找第一个 img[data-src]（768×768预览图）
        first_img = img_info_div.find('img')
        if first_img:
            img_url = first_img.get('data-src')
            if img_url and not img_url.startswith('data:image'):
                if not img_url.startswith(('http://', 'https://')):
                    img_url = urljoin(base_url, img_url)
                return img_url
        
        # 策略3：从缩略图区域提取第一个缩略图，并转换为大图URL
        img_nav_div = img_info_div.find('div', class_='img_nav')
        if img_nav_div:
            first_thumbnail_img = img_nav_div.find('img')
            if first_thumbnail_img:
                img_url = first_thumbnail_img.get('data-src')
                if img_url and not img_url.startswith('data:image'):
                    if not img_url.startswith(('http://', 'https://')):
                        img_url = urljoin(base_url, img_url)
                    
                    # 将100×100缩略图URL转换为大图URL
                    if '-100x100' in img_url:
                        # 尝试获取原始大图（去掉尺寸后缀）
                        original_url = re.sub(r'-100x100(?=\.\w+$)', '', img_url)
                        # 尝试获取1080×1080版本
                        large_url = re.sub(r'-\d+x\d+(?=\.\w+$)', '-1080x1080', img_url)
                        
                        # 优先使用1080×1080版本
                        return large_url if '1080x1080' in large_url else original_url
        
        return None
    except Exception as e:
        print(f"  提取第一张主图出错: {str(e)[:50]}")
        return None

def validate_image_url(url: str) -> bool:
    """
    验证图片URL是否有效（符合产品主图特征）：
        - 必须是常见的图片扩展名（.jpg, .jpeg, .png, .gif, .webp）
        - 不能包含 logo/icon/avatar 等非产品图片关键词
        - 路径中应包含 'wp-content/uploads' 或 'uploads'（基于目标网站结构）

    Args:
        url (str): 图片URL

    Returns:
        bool: 有效返回 True，否则 False
    """
    if not url:
        return False
    
    # 检查是否是图片文件
    if not any(url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
        return False
    
    # 排除明显不是产品主图的图片
    if any(exclude in url.lower() for exclude in ['logo', 'icon', 'avatar', 'banner', 'header', 'footer', 'placeholder']):
        return False
    
    # 检查是否在主图区常见的目录中（如wp-content/uploads）
    if 'wp-content/uploads' not in url and 'uploads' not in url:
        return False
    
    return True

def fetch_first_main_image_url_with_retry(url: str, max_retries: int = 3) -> Optional[Dict]:
    """
    抓取产品主图区的第一张主图URL，带重试机制。

    工作流程：
    1. 发送HTTP请求获取页面，支持重试和指数退避。
    2. 提取产品型号（若未找到则从URL中提取或使用时间戳）。
    3. 定位主图区。
    4. 提取第一张主图URL，并进行有效性验证。
    5. 返回包含页面URL、产品型号、主图URL、文件名、抓取时间和状态的字典。
       即使失败也返回一个包含状态信息的字典（方便记录）。

    Args:
        url (str): 产品页面URL
        max_retries (int): 最大重试次数，默认3次

    Returns:
        Optional[Dict]: 包含以下字段的字典（即使失败也返回部分信息）：
            - '页面URL': 原始URL
            - '产品型号': 产品型号
            - '第一张主图URL': 图片URL（若成功则为有效URL，否则为空字符串）
            - '图片文件名': 从URL中提取的文件名（若成功）
            - '抓取时间': 抓取完成的时间戳
            - '重试次数': 实际重试次数
            - '状态': 状态描述（'成功'、'超时'、'连接错误'、'错误: xxx' 等）
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    }
    
    for retry in range(max_retries):
        try:
            if retry > 0:
                print(f"  第 {retry + 1}/{max_retries} 次重试抓取页面...")
                time.sleep(2 ** retry)  # 指数退避
            
            print(f"  正在抓取: {url[:60]}...")
            
            response = requests.get(url, headers=headers, timeout=15)
            response.encoding = 'utf-8'
            
            if response.status_code != 200:
                print(f"  ⚠️ 请求失败 (状态码 {response.status_code})")
                if 400 <= response.status_code < 500:
                    print(f"  ⚠️ 客户端错误，不再重试")
                    return {
                        '页面URL': url,
                        '产品型号': '未知',
                        '第一张主图URL': '',
                        '图片文件名': '',
                        '抓取时间': time.strftime('%Y-%m-%d %H:%M:%S'),
                        '重试次数': retry + 1,
                        '状态': f'HTTP {response.status_code}'
                    }
                continue
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 提取产品型号
            product_model = extract_product_model(soup)
            
            if not product_model:
                # 尝试从URL中提取（例如 /product/clamp-2/ -> CLAMP-2）
                parsed_url = urlparse(url)
                path = parsed_url.path
                model_match = re.search(r'/([a-z0-9]+-[a-z0-9]+)/?$', path, re.IGNORECASE)
                if model_match:
                    product_model = model_match.group(1).upper()
                else:
                    # 使用时间戳作为默认型号
                    product_model = f"PRODUCT_{int(time.time())}"
            
            print(f"  产品型号: {product_model}")
            
            # 定位主图区
            img_info_div = extract_main_image_area(soup)
            
            if not img_info_div:
                print(f"  ⚠️ 未找到主图区")
                return {
                    '页面URL': url,
                    '产品型号': product_model,
                    '第一张主图URL': '',
                    '图片文件名': '',
                    '抓取时间': time.strftime('%Y-%m-%d %H:%M:%S'),
                    '重试次数': retry + 1,
                    '状态': '未找到主图区'
                }
            
            print(f"  ✅ 找到主图区")
            
            # 从主图区提取第一张主图URL
            first_image_url = extract_first_main_image_url(img_info_div, url)
            
            if not first_image_url:
                print(f"  ⚠️ 主图区未找到第一张主图")
                return {
                    '页面URL': url,
                    '产品型号': product_model,
                    '第一张主图URL': '',
                    '图片文件名': '',
                    '抓取时间': time.strftime('%Y-%m-%d %H:%M:%S'),
                    '重试次数': retry + 1,
                    '状态': '未找到图片'
                }
            
            # 验证图片URL
            if not validate_image_url(first_image_url):
                print(f"  ⚠️ 第一张主图URL无效: {first_image_url[:50]}...")
                return {
                    '页面URL': url,
                    '产品型号': product_model,
                    '第一张主图URL': first_image_url,
                    '图片文件名': '',
                    '抓取时间': time.strftime('%Y-%m-%d %H:%M:%S'),
                    '重试次数': retry + 1,
                    '状态': 'URL无效'
                }
            
            # 提取文件名
            parsed_url_obj = urlparse(first_image_url)
            filename = os.path.basename(parsed_url_obj.path)
            
            print(f"  ✅ 找到第一张主图URL")
            print(f"    图片URL: {first_image_url[:80]}...")
            
            return {
                '页面URL': url,
                '产品型号': product_model,
                '第一张主图URL': first_image_url,
                '图片文件名': filename,
                '抓取时间': time.strftime('%Y-%m-%d %H:%M:%S'),
                '重试次数': retry + 1,
                '状态': '成功'
            }
            
        except requests.exceptions.Timeout:
            print(f"  ⏱️  请求超时 (尝试 {retry + 1}/{max_retries})")
            if retry == max_retries - 1:
                print(f"  ❌ 所有重试均超时")
                return {
                    '页面URL': url,
                    '产品型号': '未知',
                    '第一张主图URL': '',
                    '图片文件名': '',
                    '抓取时间': time.strftime('%Y-%m-%d %H:%M:%S'),
                    '重试次数': retry + 1,
                    '状态': '超时'
                }
            
        except requests.exceptions.ConnectionError:
            print(f"  🔌 连接错误 (尝试 {retry + 1}/{max_retries})")
            if retry == max_retries - 1:
                print(f"  ❌ 所有重试均连接失败")
                return {
                    '页面URL': url,
                    '产品型号': '未知',
                    '第一张主图URL': '',
                    '图片文件名': '',
                    '抓取时间': time.strftime('%Y-%m-%d %H:%M:%S'),
                    '重试次数': retry + 1,
                    '状态': '连接错误'
                }
            
        except Exception as e:
            error_msg = str(e)[:50]
            print(f"  ❌ 抓取出错: {error_msg} (尝试 {retry + 1}/{max_retries})")
            if retry == max_retries - 1:
                print(f"  ❌ 所有重试均失败")
                return {
                    '页面URL': url,
                    '产品型号': '未知',
                    '第一张主图URL': '',
                    '图片文件名': '',
                    '抓取时间': time.strftime('%Y-%m-%d %H:%M:%S'),
                    '重试次数': retry + 1,
                    '状态': f'错误: {error_msg}'
                }
    
    return {
        '页面URL': url,
        '产品型号': '未知',
        '第一张主图URL': '',
        '图片文件名': '',
        '抓取时间': time.strftime('%Y-%m-%d %H:%M:%S'),
        '重试次数': max_retries,
        '状态': '所有重试失败'
    }

def batch_fetch_first_image_urls(url_list: List[str], 
                                output_file: str = '第一张主图URL抓取记录.xlsx',
                                max_retries: int = 3) -> None:
    """
    批量抓取产品第一张主图URL，输出到Excel文件。

    工作流程：
    1. 遍历URL列表，对每个URL调用 fetch_first_main_image_url_with_retry。
    2. 收集结果，统计成功/失败数量。
    3. 将结果保存到Excel文件，包含四个工作表：
       - 所有记录：全部抓取结果
       - 成功记录：状态为“成功”的记录
       - 失败记录：状态不为“成功”的记录
       - URL摘要：仅包含页面URL、主图URL和状态
    4. 若缺少pandas，则保存为文本文件。

    Args:
        url_list (List[str]): 产品URL列表
        output_file (str): 输出的Excel文件路径
        max_retries (int): 页面抓取最大重试次数
    """
    print(f"🚀 开始批量抓取产品第一张主图URL，共 {len(url_list)} 个产品页面")
    print(f"📊 重试配置: 页面抓取最多重试 {max_retries} 次")
    print("=" * 60)
    
    results = []
    success_count = 0
    fail_count = 0
    
    for i, url in enumerate(url_list, 1):
        url = url.strip()
        if not url:
            continue
        
        print(f"[{i}/{len(url_list)}] ", end="")
        
        # 抓取产品第一张主图URL（带重试）
        result_data = fetch_first_main_image_url_with_retry(url, max_retries=max_retries)
        
        if result_data:
            results.append(result_data)
            
            if result_data['状态'] == '成功':
                success_count += 1
                print(f"  ✅ 抓取成功")
            else:
                fail_count += 1
                print(f"  ❌ 抓取失败: {result_data['状态']}")
        else:
            fail_count += 1
            print(f"  ❌ 抓取失败")
        
        # 请求间隔（避免被封）
        if i < len(url_list):
            wait_time = 2 if i % 10 == 0 else 1  # 每10个页面等2秒
            time.sleep(wait_time)
    
    print("\n" + "=" * 60)
    
    # 保存结果到Excel
    if results:
        try:
            # 创建DataFrame
            df = pd.DataFrame(results)
            
            # 重新排列列的顺序
            column_order = ['页面URL', '产品型号', '第一张主图URL', '图片文件名', '抓取时间', '重试次数', '状态']
            df = df[column_order]
            
            # 保存到Excel，包含多个sheet
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                # Sheet1: 所有数据
                df.to_excel(writer, sheet_name='所有记录', index=False)
                
                # Sheet2: 成功记录
                success_df = df[df['状态'] == '成功'].copy()
                if not success_df.empty:
                    success_df.to_excel(writer, sheet_name='成功记录', index=False)
                
                # Sheet3: 失败记录
                fail_df = df[df['状态'] != '成功'].copy()
                if not fail_df.empty:
                    fail_df.to_excel(writer, sheet_name='失败记录', index=False)
                
                # Sheet4: URL摘要（只包含页面URL和主图URL）
                url_summary = df[['页面URL', '第一张主图URL', '状态']].copy()
                url_summary.to_excel(writer, sheet_name='URL摘要', index=False)
            
            print(f"📁 抓取记录保存至: {output_file}")
            print(f"📄 文件包含 {len(results)} 条记录")
            print(f"   成功: {success_count} 条")
            print(f"   失败: {fail_count} 条")
            
            # 显示成功抓取的URL示例
            if success_count > 0:
                print(f"\n📄 成功抓取的URL示例:")
                for i, row in enumerate(success_df.head(3).itertuples(), 1):
                    print(f"   示例{i}:")
                    print(f"     产品型号: {row.产品型号}")
                    print(f"     主图URL: {row.第一张主图URL[:60]}...")
                if success_count > 3:
                    print(f"   ...还有 {success_count-3} 个成功记录")
            
            # 显示失败统计
            if fail_count > 0:
                print(f"\n⚠️  失败统计:")
                status_counts = df[df['状态'] != '成功']['状态'].value_counts()
                for status, count in status_counts.items():
                    print(f"   {status}: {count} 个")
        
        except Exception as e:
            print(f"❌ 保存Excel文件出错: {str(e)}")
            # 尝试保存为CSV作为备用
            try:
                csv_file = output_file.replace('.xlsx', '.csv')
                df.to_csv(csv_file, index=False, encoding='utf-8-sig')
                print(f"📁 数据已保存为CSV文件: {csv_file}")
            except Exception as e2:
                print(f"❌ 保存CSV文件也失败: {str(e2)}")
                # 保存为文本文件
                with open('第一张主图URL记录.txt', 'w', encoding='utf-8') as f:
                    f.write("第一张主图URL抓取记录\n")
                    f.write("=" * 50 + "\n\n")
                    for result in results:
                        f.write(f"页面URL: {result['页面URL']}\n")
                        f.write(f"产品型号: {result['产品型号']}\n")
                        f.write(f"第一张主图URL: {result['第一张主图URL']}\n")
                        f.write(f"图片文件名: {result['图片文件名']}\n")
                        f.write(f"状态: {result['状态']}\n")
                        f.write(f"重试次数: {result['重试次数']}\n")
                        f.write(f"抓取时间: {result['抓取时间']}\n")
                        f.write("-" * 50 + "\n")
                print(f"📁 数据已保存为文本文件: 第一张主图URL记录.txt")
    
    else:
        print("❌ 所有页面处理失败")

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
        print(f"⚠️  文件 {filename} 不存在")
        return []

def create_sample_files():
    """
    创建示例 urls.txt 文件（如果不存在）。
    """
    if not os.path.exists('urls.txt'):
        with open('urls.txt', 'w', encoding='utf-8') as f:
            f.write("# 产品URL列表（每行一个）\n")
            f.write("# 示例（来自lisungroup.com）:\n")
            f.write("# https://www.lisungroup.com/product/clamp-2/\n")
            f.write("# https://www.lisungroup.com/product/gngpl-6216d/\n")
            f.write("# https://www.lisungroup.com/product/sls-50w/\n")
        print("✅ 已创建示例 urls.txt 文件")

def main():
    """
    主程序入口：
        1. 显示工具信息。
        2. 创建示例文件。
        3. 读取URL列表。
        4. 询问用户重试次数和输出文件名。
        5. 启动批量抓取。
        6. 输出耗时和统计信息。
    """
    print("=" * 60)
    print("产品第一张主图URL抓取工具")
    print("专门抓取主图区的第一张图片URL，输出到Excel，不下载图片")
    print("主图区结构: div.img_info > div.swiper-wrapper > a.switch_item")
    print("只获取代码顺序中首次在主图区出现的图片URL")
    print("=" * 60)
    
    create_sample_files()
    
    url_list = read_urls_from_file('urls.txt')
    
    if not url_list:
        print("请在同目录的 urls.txt 文件中添加产品URL，每行一个")
        input("按Enter键退出...")
        return
    
    # 询问重试次数
    try:
        max_retries = int(input(f"🔁 页面抓取重试次数 (默认: 3): ").strip() or "3")
    except ValueError:
        max_retries = 3
    
    # 询问输出文件名
    timestamp = time.strftime("%Y%m%d_%H%M")
    default_output = f'第一张主图URL抓取记录_{timestamp}.xlsx'
    output_file = input(f"📁 输出文件名 (默认: {default_output}): ").strip()
    if not output_file:
        output_file = default_output
    
    print(f"\n即将处理 {len(url_list)} 个产品页面")
    print(f"页面抓取重试: 最多 {max_retries} 次")
    print(f"只抓取主图区第一张图片URL，不下载图片")
    print(f"结果将保存到: {output_file}")
    confirm = input("是否开始？ (y/n): ").strip().lower()
    
    if confirm != 'y':
        print("取消操作")
        return
    
    start_time = time.time()
    
    batch_fetch_first_image_urls(url_list, output_file, max_retries)
    
    end_time = time.time()
    total_time = end_time - start_time
    
    print(f"\n⏱️  总耗时: {total_time:.2f} 秒")
    print(f"📊 平均每个产品: {total_time / len(url_list):.2f} 秒")
    print("\n✨ 任务完成！")

if __name__ == "__main__":
    main()
