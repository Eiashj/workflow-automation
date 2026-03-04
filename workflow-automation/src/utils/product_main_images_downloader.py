"""
产品主图抓取工具 - 完整重试版
专门从产品页面的主图区抓取所有产品图片（1080×1080原图），并下载到本地文件夹。
主图区结构预期：div.img_info > div.swiper-wrapper > a.switch_item，其中 data-src 属性存放1080×1080原图。

主要功能：
1. 从 urls.txt 中读取产品URL列表。
2. 对每个URL发起请求，定位主图区，提取所有主图的1080×1080原图URL。
3. 根据产品型号生成文件名：
   - 单张：型号.jpg/png
   - 多张：型号_1.jpg/png, 型号_2.jpg/png, ...
4. 下载图片到指定目录（默认 product_main_images），带有重试机制和文件存在性检查。
5. 记录抓取结果到Excel文件（包含成功、失败、跳过记录），并保存失败URL列表。
6. 提供统计信息：总图片数、成功数、失败数、重试次数等。
"""

import requests
from bs4 import BeautifulSoup
import os
import time
import re
from typing import List, Dict, Optional
from urllib.parse import urlparse, urljoin
import hashlib

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
                if classes and ('img' in str(classes) or 'image' in str(classes)):
                    img_info_div = div
                    break
        
        return img_info_div
    except Exception as e:
        print(f"  定位主图区出错: {str(e)[:50]}")
        return None

def extract_main_images_from_area(img_info_div: BeautifulSoup, base_url: str) -> List[str]:
    """
    从主图区提取所有主图的1080×1080原图URL，采用多级策略：
        1. 查找 a.switch_item 的 data-src 属性（1080×1080原图）。
        2. 若未找到，查找 img 的 data-src 属性（768×768预览图）。
        3. 若仍未找到，从缩略图区域 (img_nav) 提取缩略图URL，并尝试转换为大图URL：
           - 将 '-100x100' 替换为 '' 得到原始图
           - 将 '-100x100' 替换为 '-1080x1080' 得到1080×1080版本
        4. 最后对URL进行过滤：排除logo/icon等非产品图片，确保路径包含 'wp-content/uploads' 或 'uploads'。

    Args:
        img_info_div (BeautifulSoup): 主图区标签对象
        base_url (str): 基础URL，用于拼接相对路径

    Returns:
        List[str]: 去重后的主图URL列表
    """
    main_images = []
    seen_urls = set()
    
    if not img_info_div:
        return main_images
    
    try:
        # 策略1：查找 a.switch_item 的 data-src（1080×1080原图）
        for a_tag in img_info_div.find_all('a', class_='switch_item'):
            img_url = a_tag.get('data-src')
            if img_url and not img_url.startswith('data:image'):
                if not img_url.startswith(('http://', 'https://')):
                    img_url = urljoin(base_url, img_url)
                if img_url not in seen_urls:
                    seen_urls.add(img_url)
                    main_images.append(img_url)
        
        # 策略2：如果没找到1080×1080原图，查找 img[data-src]（768×768预览图）
        if not main_images:
            for img_tag in img_info_div.find_all('img'):
                img_url = img_tag.get('data-src')
                if img_url and not img_url.startswith('data:image'):
                    if not img_url.startswith(('http://', 'https://')):
                        img_url = urljoin(base_url, img_url)
                    if img_url not in seen_urls:
                        seen_urls.add(img_url)
                        main_images.append(img_url)
        
        # 策略3：从缩略图区域提取，并转换为大图
        if not main_images:
            img_nav_div = img_info_div.find('div', class_='img_nav')
            if img_nav_div:
                for img_tag in img_nav_div.find_all('img'):
                    img_url = img_tag.get('data-src')
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
                            if large_url not in seen_urls:
                                seen_urls.add(large_url)
                                main_images.append(large_url)
                            elif original_url not in seen_urls:
                                seen_urls.add(original_url)
                                main_images.append(original_url)
        
        # 过滤：确保只保留产品主图（排除logo/icon等，并确保路径包含 'uploads'）
        filtered_images = []
        for img_url in main_images:
            if any(exclude in img_url.lower() for exclude in ['logo', 'icon', 'avatar', 'banner', 'header', 'footer', 'placeholder']):
                continue
            if not any(img_url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                continue
            if 'wp-content/uploads' not in img_url and 'uploads' not in img_url:
                continue
            filtered_images.append(img_url)
        
        return filtered_images
    except Exception as e:
        print(f"  提取主图出错: {str(e)[:50]}")
        return []

def get_image_extension(url: str) -> str:
    """
    从URL路径中提取图片扩展名（.jpg, .png, .gif, .webp），默认返回 .jpg。

    Args:
        url (str): 图片URL

    Returns:
        str: 扩展名，包含点号，如 '.jpg'
    """
    try:
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        if '.jpg' in path or '.jpeg' in path:
            return '.jpg'
        elif '.png' in path:
            return '.png'
        elif '.gif' in path:
            return '.gif'
        elif '.webp' in path:
            return '.webp'
        else:
            return '.jpg'
    except:
        return '.jpg'

def download_image_with_retry(url: str, filepath: str, max_retries: int = 3) -> bool:
    """
    下载图片并保存到指定路径，支持重试和指数退避。
    下载后验证文件大小是否大于1KB，若太小则删除并重试。

    Args:
        url (str): 图片URL
        filepath (str): 本地保存路径
        max_retries (int): 最大重试次数，默认3次

    Returns:
        bool: 下载成功返回 True，否则 False
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.lisungroup.com/'
    }
    
    for retry in range(max_retries):
        try:
            if retry > 0:
                print(f"      第 {retry + 1}/{max_retries} 次重试下载...")
                time.sleep(2 ** retry)  # 指数退避
            
            response = requests.get(url, headers=headers, stream=True, timeout=30)
            response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            # 验证文件大小（至少大于1KB）
            if os.path.getsize(filepath) > 1024:
                return True
            else:
                os.remove(filepath)
                # 文件太小，视为无效，继续重试
                continue
                
        except requests.exceptions.Timeout:
            print(f"      下载超时 (尝试 {retry + 1}/{max_retries})")
            if retry == max_retries - 1:
                print(f"      所有重试均超时")
                return False
            
        except requests.exceptions.ConnectionError:
            print(f"      连接错误 (尝试 {retry + 1}/{max_retries})")
            if retry == max_retries - 1:
                print(f"      所有重试均连接失败")
                return False
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                print(f"      图片不存在 (404)")
                return False
            elif e.response.status_code == 403:
                print(f"      访问被拒绝 (403)")
                return False
            else:
                print(f"      HTTP错误 {e.response.status_code} (尝试 {retry + 1}/{max_retries})")
                if retry == max_retries - 1:
                    return False
        
        except Exception as e:
            print(f"      下载出错: {str(e)[:50]} (尝试 {retry + 1}/{max_retries})")
            if retry == max_retries - 1:
                return False
    
    return False

def fetch_product_main_images_with_retry(url: str, max_retries: int = 3) -> Optional[Dict]:
    """
    抓取产品主图区的所有图片信息，带重试机制。

    工作流程：
    1. 发送HTTP请求获取页面。
    2. 提取产品型号（若未找到则从URL中提取或使用时间戳）。
    3. 定位主图区。
    4. 提取主图URL列表。
    5. 返回包含URL、型号、主图列表、数量、抓取时间和重试次数的字典。

    Args:
        url (str): 产品页面URL
        max_retries (int): 最大重试次数，默认3次

    Returns:
        Optional[Dict]: 包含以下字段的字典，若最终失败则返回None
            - 'URL': 原始URL
            - '产品型号': 产品型号
            - '主图列表': 主图URL列表
            - '图片数量': 主图数量
            - '抓取时间': 抓取完成的时间戳
            - '重试次数': 实际重试次数
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
                    return None
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
                return None
            
            print(f"  ✅ 找到主图区")
            
            # 从主图区提取所有主图
            main_images = extract_main_images_from_area(img_info_div, url)
            
            if not main_images:
                print(f"  ⚠️ 主图区未找到图片")
                return None
            
            print(f"  找到 {len(main_images)} 张主图")
            
            # 预览前几张图片
            for i, img_url in enumerate(main_images[:3], 1):
                filename = os.path.basename(urlparse(img_url).path)
                print(f"    主图{i}: {filename[:40]}...")
            if len(main_images) > 3:
                print(f"    ...还有 {len(main_images)-3} 张")
            
            return {
                'URL': url,
                '产品型号': product_model,
                '主图列表': main_images,
                '图片数量': len(main_images),
                '抓取时间': time.strftime('%Y-%m-%d %H:%M:%S'),
                '重试次数': retry + 1
            }
            
        except requests.exceptions.Timeout:
            print(f"  ⏱️  请求超时 (尝试 {retry + 1}/{max_retries})")
            if retry == max_retries - 1:
                print(f"  ❌ 所有重试均超时")
                return None
            
        except requests.exceptions.ConnectionError:
            print(f"  🔌 连接错误 (尝试 {retry + 1}/{max_retries})")
            if retry == max_retries - 1:
                print(f"  ❌ 所有重试均连接失败")
                return None
            
        except Exception as e:
            error_msg = str(e)[:50]
            print(f"  ❌ 抓取出错: {error_msg} (尝试 {retry + 1}/{max_retries})")
            if retry == max_retries - 1:
                print(f"  ❌ 所有重试均失败")
                return None
    
    return None

def download_product_images_with_retry(product_data: Dict, save_dir: str = 'product_main_images', max_retries: int = 3) -> Dict:
    """
    下载产品所有主图，按照命名规则保存，并返回下载结果统计。

    命名规则：
        - 单张：型号.jpg/png
        - 多张：型号_1.jpg/png, 型号_2.jpg/png, ...

    处理逻辑：
        - 若文件已存在，检查大小是否相似（差异<1KB），若相同则跳过，否则覆盖。
        - 下载失败时记录。

    Args:
        product_data (Dict): 包含 '产品型号' 和 '主图列表' 的字典
        save_dir (str): 图片保存目录
        max_retries (int): 每张图片下载的最大重试次数

    Returns:
        Dict: 包含下载统计的字典：
            - '下载成功': 成功下载的图片数量
            - '下载失败': 失败的图片数量
            - '文件列表': 成功下载的文件名列表
            - '总图片数': 总图片数
            - '下载详情': 每张图片的详细结果（文件名、状态、大小）
    """
    product_model = product_data['产品型号']
    main_images = product_data['主图列表']
    
    # 清理产品型号中的非法字符（Windows文件名不允许的字符）
    clean_model = re.sub(r'[<>:"/\\|?*]', '_', product_model)
    
    # 确保保存目录存在
    os.makedirs(save_dir, exist_ok=True)
    
    print(f"  开始下载 {len(main_images)} 张主图...")
    
    downloaded_files = []
    success_count = 0
    download_details = []
    
    for i, img_url in enumerate(main_images, 1):
        # 获取图片扩展名
        ext = get_image_extension(img_url)
        
        # 严格按照命名规则生成文件名
        if len(main_images) == 1:
            filename = f"{clean_model}{ext}"
        else:
            filename = f"{clean_model}_{i}{ext}"
        
        # 完整文件路径
        filepath = os.path.join(save_dir, filename)
        
        # 检查文件是否已存在（避免重复下载）
        if os.path.exists(filepath):
            # 先下载到临时文件进行比较
            temp_filename = f"{filename}.temp"
            temp_filepath = os.path.join(save_dir, temp_filename)
            
            if download_image_with_retry(img_url, temp_filepath, max_retries=1):
                # 比较文件大小
                existing_size = os.path.getsize(filepath)
                new_size = os.path.getsize(temp_filepath)
                
                if abs(existing_size - new_size) < 1024:  # 允许1KB的差异
                    # 文件基本相同，跳过
                    print(f"    ⚠️ 文件已存在且相同: {filename}")
                    os.remove(temp_filepath)
                    downloaded_files.append(filename)
                    success_count += 1
                    download_details.append({
                        '文件名': filename,
                        '状态': '已存在',
                        '大小': existing_size
                    })
                    continue
                else:
                    # 文件不同，删除临时文件，继续下载新文件
                    os.remove(temp_filepath)
                    print(f"    ⚠️ 文件已存在但不同，将覆盖: {filename}")
        
        # 下载图片（带重试）
        if download_image_with_retry(img_url, filepath, max_retries):
            downloaded_files.append(filename)
            success_count += 1
            file_size = os.path.getsize(filepath)
            print(f"    ✅ 下载成功: {filename} ({file_size:,} bytes)")
            download_details.append({
                '文件名': filename,
                '状态': '下载成功',
                '大小': file_size
            })
        else:
            print(f"    ❌ 下载失败: {filename}")
            download_details.append({
                '文件名': filename,
                '状态': '下载失败',
                '大小': 0
            })
        
        # 避免请求过快（只在成功或最后一次失败后等待）
        time.sleep(1)
    
    return {
        '下载成功': success_count,
        '下载失败': len(main_images) - success_count,
        '文件列表': downloaded_files,
        '总图片数': len(main_images),
        '下载详情': download_details
    }

def batch_crawl_and_download_with_retry(url_list: List[str], 
                                      save_dir: str = 'product_main_images',
                                      output_file: str = '产品主图抓取记录.xlsx',
                                      page_retries: int = 3,
                                      download_retries: int = 3) -> None:
    """
    批量抓取并下载产品所有主图，支持重试机制，并保存记录到Excel。

    Args:
        url_list (List[str]): 产品URL列表
        save_dir (str): 图片保存目录
        output_file (str): 输出的Excel文件路径
        page_retries (int): 页面抓取最大重试次数
        download_retries (int): 图片下载最大重试次数
    """
    print(f"🚀 开始批量抓取产品主图，共 {len(url_list)} 个产品页面")
    print(f"📊 重试配置: 页面抓取 {page_retries} 次, 图片下载 {download_retries} 次")
    print("=" * 60)
    
    results = []
    failed_urls = []
    skipped_urls = []
    
    # 检查已存在的产品型号，避免重复处理
    existing_models = set()
    if os.path.exists(save_dir):
        for filename in os.listdir(save_dir):
            if filename.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                # 提取型号（去掉_1, _2等后缀和扩展名）
                base_name = os.path.splitext(filename)[0]
                model_match = re.match(r'([^_]+)(?:_\d+)?$', base_name)
                if model_match:
                    existing_models.add(model_match.group(1))
    
    if existing_models:
        print(f"⚠️  发现 {len(existing_models)} 个已存在的产品型号，将跳过这些产品")
    
    for i, url in enumerate(url_list, 1):
        url = url.strip()
        if not url:
            continue
        
        print(f"[{i}/{len(url_list)}] ", end="")
        
        # 抓取产品主图信息（带重试）
        product_data = fetch_product_main_images_with_retry(url, max_retries=page_retries)
        
        if product_data:
            try:
                # 检查型号是否已存在
                if product_data['产品型号'] in existing_models:
                    print(f"  ⚠️ 型号已存在: {product_data['产品型号']}，跳过")
                    skipped_urls.append(url)
                    continue
                
                # 下载所有主图（带重试）
                download_result = download_product_images_with_retry(product_data, save_dir, download_retries)
                
                # 更新结果
                product_data.update(download_result)
                results.append(product_data)
                
                print(f"  ✅ 下载完成: {download_result['下载成功']}/{download_result['总图片数']} 张")
                
                # 添加到已存在型号列表，避免后续重复
                existing_models.add(product_data['产品型号'])
                
            except Exception as e:
                print(f"  ❌ 处理失败: {str(e)[:50]}")
                failed_urls.append({
                    'url': url,
                    '原因': str(e)[:100]
                })
        else:
            failed_urls.append({
                'url': url,
                '原因': '页面抓取失败'
            })
            print(f"  ❌ 抓取失败")
        
        # 请求间隔（避免被封）
        if i < len(url_list):
            wait_time = 2 if i % 5 == 0 else 1  # 每5个页面等2秒
            time.sleep(wait_time)
    
    print("\n" + "=" * 60)
    
    # 保存结果到Excel
    if results:
        try:
            import pandas as pd
            
            df_data = []
            for result in results:
                file_list_str = ", ".join(result.get('文件列表', []))
                
                row = {
                    'URL': result['URL'],
                    '产品型号': result['产品型号'],
                    '主图数量': result['图片数量'],
                    '下载成功': result['下载成功'],
                    '下载失败': result['下载失败'],
                    '下载文件列表': file_list_str,
                    '重试次数': result.get('重试次数', 1),
                    '抓取时间': result['抓取时间']
                }
                df_data.append(row)
            
            df = pd.DataFrame(df_data)
            
            # 保存到Excel，包含多个sheet
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                # Sheet1: 抓取结果
                df.to_excel(writer, sheet_name='抓取结果', index=False)
                
                # Sheet2: 下载详情
                detail_data = []
                for result in results:
                    for detail in result.get('下载详情', []):
                        detail_data.append({
                            '产品型号': result['产品型号'],
                            '文件名': detail['文件名'],
                            '状态': detail['状态'],
                            '文件大小': detail['大小']
                        })
                if detail_data:
                    detail_df = pd.DataFrame(detail_data)
                    detail_df.to_excel(writer, sheet_name='下载详情', index=False)
                
                # Sheet3: 失败记录
                if failed_urls:
                    failed_df = pd.DataFrame(failed_urls)
                    failed_df.to_excel(writer, sheet_name='失败记录', index=False)
                
                # Sheet4: 跳过记录
                if skipped_urls:
                    skipped_df = pd.DataFrame({'跳过的URL': skipped_urls})
                    skipped_df.to_excel(writer, sheet_name='跳过记录', index=False)
            
            print(f"📁 抓取记录保存至: {output_file}")
            print(f"📄 包含 {len(df_data)} 个产品的抓取结果")
            
        except ImportError:
            print("⚠️  未安装pandas，跳过Excel保存")
            # 保存为文本文件
            with open('产品主图记录.txt', 'w', encoding='utf-8') as f:
                f.write("产品主图抓取记录\n")
                f.write("=" * 50 + "\n\n")
                for result in results:
                    f.write(f"URL: {result['URL']}\n")
                    f.write(f"产品型号: {result['产品型号']}\n")
                    f.write(f"主图数量: {result['图片数量']} 张\n")
                    f.write(f"下载成功: {result['下载成功']} 张\n")
                    f.write(f"下载文件: {', '.join(result.get('文件列表', []))}\n")
                    f.write(f"重试次数: {result.get('重试次数', 1)} 次\n")
                    f.write("-" * 50 + "\n")
        
        # 保存失败URL列表
        if failed_urls:
            with open('抓取失败.txt', 'w', encoding='utf-8') as f:
                for fail in failed_urls:
                    f.write(f"URL: {fail['url']}\n")
                    f.write(f"原因: {fail['原因']}\n")
                    f.write("-" * 40 + "\n")
            print(f"📝 失败URL列表已保存至: 抓取失败.txt")
        
        # 统计信息
        total_images_found = sum(r['图片数量'] for r in results)
        total_images_downloaded = sum(r['下载成功'] for r in results)
        total_retries = sum(r.get('重试次数', 1)-1 for r in results)
        
        print(f"\n📊 抓取统计:")
        print(f"   成功处理: {len(results)}/{len(url_list)} 个产品")
        print(f"   跳过处理: {len(skipped_urls)} 个产品")
        print(f"   处理失败: {len(failed_urls)} 个产品")
        print(f"   主图总数: {total_images_found} 张")
        print(f"   下载成功: {total_images_downloaded} 张")
        print(f"   总重试次数: {total_retries} 次")
        print(f"   保存目录: {save_dir}/")
        
        # 显示成功下载的文件
        if total_images_downloaded > 0:
            print(f"\n📄 成功下载的主图:")
            for result in results:
                if result['下载成功'] > 0:
                    print(f"    {result['产品型号']}: {', '.join(result.get('文件列表', []))}")
    
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
        4. 询问用户保存目录、重试次数等配置。
        5. 启动批量抓取与下载。
        6. 输出耗时和统计信息。
    """
    print("=" * 60)
    print("产品主图抓取工具 - 完整重试版")
    print("专门抓取主图区的产品图片，带有完整重试机制")
    print("主图区结构: div.img_info > div.swiper-wrapper > a.switch_item")
    print("命名规则:")
    print("  单张: 型号.jpg/png")
    print("  多张: 型号_1.jpg/png, 型号_2.jpg/png, ...")
    print("=" * 60)
    
    create_sample_files()
    
    url_list = read_urls_from_file('urls.txt')
    
    if not url_list:
        print("请在同目录的 urls.txt 文件中添加产品URL，每行一个")
        input("按Enter键退出...")
        return
    
    # 询问保存目录
    save_dir = input(f"📁 图片保存目录 (默认: product_main_images): ").strip()
    if not save_dir:
        save_dir = 'product_main_images'
    
    # 询问重试次数
    try:
        page_retries = int(input(f"🔁 页面抓取重试次数 (默认: 3): ").strip() or "3")
        download_retries = int(input(f"🔁 图片下载重试次数 (默认: 3): ").strip() or "3")
    except ValueError:
        page_retries = 3
        download_retries = 3
    
    print(f"\n即将处理 {len(url_list)} 个产品页面")
    print(f"页面抓取重试: {page_retries} 次")
    print(f"图片下载重试: {download_retries} 次")
    print(f"只抓取主图区图片，忽略详情区")
    print(f"图片将保存到: {save_dir}/")
    confirm = input("是否开始？ (y/n): ").strip().lower()
    
    if confirm != 'y':
        print("取消操作")
        return
    
    start_time = time.time()
    
    # 生成输出文件名
    timestamp = time.strftime("%Y%m%d_%H%M")
    output_file = f'产品主图抓取记录_{timestamp}.xlsx'
    
    batch_crawl_and_download_with_retry(
        url_list, 
        save_dir, 
        output_file,
        page_retries=page_retries,
        download_retries=download_retries
    )
    
    end_time = time.time()
    total_time = end_time - start_time
    
    print(f"\n⏱️  总耗时: {total_time:.2f} 秒")
    print(f"📊 平均每个产品: {total_time / len(url_list):.2f} 秒")
    print("\n✨ 任务完成！")

if __name__ == "__main__":
    main()
