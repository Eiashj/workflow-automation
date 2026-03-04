"""
产品详情HTML片段抓取与清洗工具 - 自动化版本
批量抓取产品详情页的 tab_content 区域（通常是描述内容的容器），清洗原始HTML，
并插入到指定的阿里模板中，最终保存为包含多个工作表的Excel文件。

主要流程：
1. 从 urls.txt 中读取产品URL列表，自动补全https://协议头。
2. 对每个URL发起请求，定位 <ul class="tab_content"> 区域（或备选方案），
   提取其中的 <li class="rich_text"> 的原始HTML。
3. 对原始HTML进行清洗：
   - 移除 loading、decoding 等无用属性
   - 将 data-src 替换为 src，并删除 srcset/sizes
   - 添加内联样式替代外部CSS类
   - 删除仅包含 &nbsp; 的空段落
4. 将清洗后的HTML插入到模板文件（插入html模板.txt）的指定位置（第一个 <p>&nbsp;</p> 处）。
5. 将结果（原始HTML、清洗后HTML、完整HTML等）保存到Excel文件，包含四个工作表：
   - 完整数据：所有字段
   - HTML结果：仅URL和完整HTML
   - 原始HTML：仅原始HTML片段
   - 清洗后HTML：仅清洗后的HTML片段
6. 记录失败URL，便于排查。
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import os
from typing import List, Dict, Optional, Tuple
import html

def fetch_product_html_with_retry(url: str, max_retries: int = 3) -> Optional[Dict]:
    """
    抓取单个产品页面的目标HTML片段，带重试机制。
    定位逻辑：
        - 优先级1：<ul class="tab_content">
        - 优先级2：任意 ul 标签，其 class 包含 "tab" 和 "content"
        - 优先级3：找到 <li class="rich_text"> 后向上查找父级 ul

    Args:
        url (str): 产品页面URL
        max_retries (int): 最大重试次数，默认3次

    Returns:
        Optional[Dict]: 包含以下字段的字典，若最终失败则返回None
            - 'URL': 原始URL
            - '原始HTML': 提取到的目标HTML片段（字符串）
            - '字符数': 原始HTML的字符长度
            - '抓取时间': 抓取完成的时间戳
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    }
    
    for retry in range(max_retries):
        try:
            if retry > 0:
                print(f"  第 {retry + 1}/{max_retries} 次重试...")
                time.sleep(2 ** retry)  # 指数退避：2,4,8秒
            print(f"  正在抓取: {url[:60]}...")
            
            # 1. 请求页面
            response = requests.get(url, headers=headers, timeout=15)
            response.encoding = 'utf-8'
            
            if response.status_code != 200:
                print(f"  ⚠️ 请求失败 (状态码 {response.status_code})")
                # 4xx 客户端错误，无需重试
                if 400 <= response.status_code < 500:
                    print(f"  ⚠️ 客户端错误，不再重试")
                    return None
                continue  # 5xx 或其他，继续重试
            
            # 2. 解析HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 3. 定位目标区域：<ul class="tab_content">
            tab_content = soup.find('ul', class_='tab_content')
            
            # 优先级2：如果精确类名未找到，尝试查找 class 中包含 "tab" 和 "content" 的 ul
            if not tab_content:
                for ul in soup.find_all('ul'):
                    class_str = ' '.join(ul.get('class', [])) if ul.get('class') else ''
                    if 'tab' in class_str.lower() and 'content' in class_str.lower():
                        tab_content = ul
                        break
            
            # 优先级3：通过 <li class="rich_text"> 向上找父级 ul
            if not tab_content:
                rich_text_li = soup.find('li', class_='rich_text')
                if rich_text_li:
                    parent_ul = rich_text_li.find_parent('ul')
                    if parent_ul:
                        tab_content = parent_ul
            
            if not tab_content:
                print(f"  ⚠️ 未找到tab_content区域")
                return None
            
            # 4. 提取 <li class="rich_text"> 内容，若不存在则使用整个 tab_content
            rich_text_content = tab_content.find('li', class_='rich_text')
            if not rich_text_content:
                rich_text_content = tab_content
            
            # 5. 将目标HTML转换为字符串
            html_content = str(rich_text_content)
            
            if len(html_content) < 100:
                print(f"  ⚠️ HTML内容太短")
                return None
            
            print(f"  ✅ 成功提取 {len(html_content)} 字符HTML")
            return {
                'URL': url,
                '原始HTML': html_content,
                '字符数': len(html_content),
                '抓取时间': time.strftime('%Y-%m-%d %H:%M:%S')
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

def clean_html_fragment(html_fragment: str) -> str:
    """
    清洗HTML片段，移除动态加载相关的属性，添加内联样式以替代外部CSS类。
    主要处理：
        - 删除 loading, decoding, srcset, sizes 等无用属性
        - 将 data-src 的值赋给 src，并删除 data-src
        - 替换 &nbsp; 为普通空格
        - 为特定标签添加内联样式（ul.tab_content, li.rich_text, div.wp-caption, p, a, img）
        - 删除仅包含空白或 &nbsp; 的 <p> 标签
        - 格式化输出（缩进），移除多余空行

    Args:
        html_fragment (str): 原始HTML片段

    Returns:
        str: 清洗后的HTML字符串
    """
    soup = BeautifulSoup(html_fragment, 'html.parser')
    
    # 1. 清理脚本/动态属性
    for tag in soup.find_all(True):  # 遍历所有标签
        # 移除 loading、decoding 属性
        if tag.has_attr('loading'):
            del tag['loading']
        if tag.has_attr('decoding'):
            del tag['decoding']
        
        # 处理 data-src：将 data-src 的值赋给 src（如果当前 src 是 base64 占位图或不存在 src）
        if tag.has_attr('data-src'):
            data_src = tag['data-src']
            if tag.has_attr('src') and 'base64' in tag['src']:
                tag['src'] = data_src
            elif not tag.has_attr('src'):
                tag['src'] = data_src
            del tag['data-src']
        
        # 移除 srcset 和 sizes 属性（响应式图片，我们不依赖）
        if tag.has_attr('srcset'):
            del tag['srcset']
        if tag.has_attr('sizes'):
            del tag['sizes']
        
        # 将文本内容中的 &nbsp; 替换为普通空格
        if tag.string and '&nbsp;' in tag.string:
            tag.string = tag.string.replace('&nbsp;', ' ')
    
    # 2. 为特定标签添加内联样式（模拟原始CSS效果）
    # 处理 ul.tab_content
    ul_tags = soup.find_all('ul', class_='tab_content')
    if not ul_tags:
        ul_tags = soup.find_all('ul')
    for ul in ul_tags:
        if 'tab_content' in ul.get('class', []):
            ul['style'] = 'list-style: none; padding: 0; margin: 0;'
    
    # 处理 li.rich_text
    li_tags = soup.find_all('li', class_='rich_text')
    for li in li_tags:
        li['style'] = 'padding: 10px; font-family: Arial, sans-serif; line-height: 1.6;'
    
    # 处理 div.wp-caption 以及 aligncenter
    for div in soup.find_all('div', class_='wp-caption'):
        if 'aligncenter' in div.get('class', []):
            div['style'] = 'width: 410px; margin: 0 auto 10px; text-align: center;'
    
    # 处理 p.wp-caption-text
    for p in soup.find_all('p', class_='wp-caption-text'):
        p['style'] = 'margin: 5px 0 0 0; color: #ff0000; font-size: 14px;'
    
    # 处理普通段落 <p>
    for p in soup.find_all('p'):
        if not p.has_attr('class') or 'wp-caption-text' not in p.get('class', []):
            if p.has_attr('style'):
                p['style'] += ' margin: 0 0 15px 0;'
            else:
                p['style'] = 'margin: 0 0 15px 0;'
    
    # 处理链接 <a>
    for a in soup.find_all('a'):
        if a.has_attr('href'):
            if a.has_attr('style'):
                a['style'] += ' color: #0066cc; text-decoration: underline;'
            else:
                a['style'] = 'color: #0066cc; text-decoration: underline;'
    
    # 处理图片 <img>
    for img in soup.find_all('img'):
        if img.has_attr('style'):
            img['style'] += ' border: none; display: block; margin: 0 auto;'
        else:
            img['style'] = 'border: none; display: block; margin: 0 auto;'
    
    # 3. 删除空的 <p>&nbsp;</p> 标签（仅包含空白或无子元素）
    for p in soup.find_all('p'):
        if p.get_text(strip=True) == '' and not p.find_all(True):
            p.decompose()
    
    # 4. 格式化输出（缩进）
    cleaned_html = soup.prettify(formatter='html')
    
    # 5. 移除多余的空白行（只保留非空行）
    lines = []
    for line in cleaned_html.split('\n'):
        stripped = line.strip()
        if stripped:
            lines.append(line)
    
    return '\n'.join(lines)

def load_html_template(template_file: str = '插入html模板.txt') -> str:
    """
    加载HTML模板文件，如果文件不存在则返回默认模板。

    Args:
        template_file (str): 模板文件路径，默认为 '插入html模板.txt'

    Returns:
        str: 模板内容
    """
    try:
        with open(template_file, 'r', encoding='utf-8') as f:
            template = f.read()
        return template
    except FileNotFoundError:
        print(f"⚠️  模板文件 {template_file} 不存在")
        # 提供默认模板（包含 Product Description 和 FAQ 部分）
        return '''<div id="ali-anchor-AliPostDhMb-cfrdt" class="mceSectionContainer" style="padding-top: 8px;" data-section="AliPostDhMb-cfrdt" data-section-title="Product Description">
<div id="ali-title-AliPostDhMb-cfrdt" style="padding: 8px 0; border-bottom: 1px solid #ddd;">
<span style="background-color: #ddd; color: #333; font-weight: bold; padding: 8px 10px; line-height: 12px;">Product Description</span>
</div>
<div style="padding: 10px 0;">
<p>&nbsp;</p>
</div>
</div>
<div id="ali-anchor-AliPostDhMb-z2z5r" class="mceSectionContainer" style="padding-top: 8px;" data-section="AliPostDhMb-z2z5r" data-section-title="FAQ">
<div id="ali-title-AliPostDhMb-z2z5r" style="padding: 8px 0; border-bottom: 1px solid #ddd;">
<span style="background-color: #ddd; color: #333; font-weight: bold; padding: 8px 10px; line-height: 12px;">FAQ</span>
</div>
<div style="padding: 10px 0;">
<p>&nbsp;<strong>1. who are we?</strong><br />
We are based in Shanghai, China, start from 2012,sell to Western Europe(25.00%),North America(20.00%),Eastern Europe(15.00%),South America(10.00%),Domestic Market(5.00%),Northern Europe(5.00%),Southeast Asia(5.00%),Eastern Asia(5.00%),Mid East(5.00%),Oceania(5.00%). There are total about 51-100 people in our office.</p>
</div>
</div>'''

def insert_html_into_template(cleaned_html: str, template: str) -> str:
    """
    将清洗后的HTML插入到模板的指定位置。
    插入点：模板中第一个 <p>&nbsp;</p> 标签的位置（通常用于占位）。
    如果未找到该占位符，则尝试插入到 <div style="padding: 10px 0;"> 内部，
    否则直接附加到模板末尾。

    Args:
        cleaned_html (str): 清洗后的HTML片段
        template (str): 原始模板字符串

    Returns:
        str: 插入后的完整HTML
    """
    # 查找第一个 <p>&nbsp;</p> 的位置
    insert_pattern = re.compile(r'<p>\s*&nbsp;\s*</p>')
    match = insert_pattern.search(template)
    
    if match:
        start, end = match.span()
        full_html = template[:start] + cleaned_html + template[end:]
    else:
        # 尝试在 padding div 内插入
        if '<div style="padding: 10px 0;">' in template:
            template = template.replace(
                '<div style="padding: 10px 0;">',
                f'<div style="padding: 10px 0;">{cleaned_html}'
            )
            full_html = template
        else:
            # 直接附加
            full_html = template + cleaned_html
    
    return full_html

def process_product_html(original_html: str, template: str) -> Tuple[str, str]:
    """
    处理产品HTML：先清洗原始HTML，再插入到模板中。

    Args:
        original_html (str): 原始HTML片段
        template (str): HTML模板

    Returns:
        Tuple[str, str]: (清洗后的HTML片段, 插入模板后的完整HTML)
    """
    cleaned_html = clean_html_fragment(original_html)
    full_html = insert_html_into_template(cleaned_html, template)
    return cleaned_html, full_html

def batch_crawl_and_convert(url_list: List[str], template_file: str = '插入html模板.txt', 
                           output_file: str = '产品HTML_清洗后.xlsx') -> pd.DataFrame:
    """
    批量抓取、清洗并保存结果到Excel文件。

    Args:
        url_list (List[str]): 产品URL列表
        template_file (str): 模板文件路径
        output_file (str): 输出的Excel文件路径

    Returns:
        pd.DataFrame or None: 成功抓取的数据框，若全部失败则返回None
    """
    print(f"🚀 开始批量抓取与清洗，共 {len(url_list)} 个产品页面")
    print("=" * 60)
    
    # 加载HTML模板
    template = load_html_template(template_file)
    if not template:
        print("❌ 无法加载HTML模板")
        return None
    
    results = []
    failed_urls = []
    
    for i, url in enumerate(url_list, 1):
        url = url.strip()
        if not url:
            continue
        
        print(f"[{i}/{len(url_list)}] ", end="")
        
        # 1. 抓取产品HTML片段
        product_data = fetch_product_html_with_retry(url)
        
        if product_data:
            try:
                # 2. 清洗HTML并插入模板
                cleaned_html, full_html = process_product_html(
                    product_data['原始HTML'], 
                    template
                )
                
                # 3. 添加到结果
                product_data['清洗后HTML'] = cleaned_html
                product_data['完整HTML'] = full_html
                product_data['清洗后长度'] = len(cleaned_html)
                product_data['完整HTML长度'] = len(full_html)
                
                results.append(product_data)
                print(f"  ✅ 清洗完成")
                
            except Exception as e:
                print(f"  ❌ 清洗失败: {str(e)[:50]}")
                failed_urls.append(url)
        else:
            failed_urls.append(url)
            print(f"  ❌ 抓取失败")
        
        # 礼貌延迟
        if i < len(url_list):
            time.sleep(2)
    
    print("\n" + "=" * 60)
    
    # 保存结果到Excel
    if results:
        df = pd.DataFrame(results)
        df = df[['URL', '原始HTML', '字符数', '清洗后HTML', '清洗后长度', 
                '完整HTML', '完整HTML长度', '抓取时间']]
        
        # 使用ExcelWriter保存多个sheet
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            # Sheet1: 完整数据
            df.to_excel(writer, sheet_name='完整数据', index=False)
            
            # Sheet2: 简略数据（只包含URL和完整HTML）
            df_simple = df[['URL', '完整HTML']]
            df_simple.to_excel(writer, sheet_name='HTML结果', index=False)
            
            # Sheet3: 原始HTML数据
            df_original = df[['URL', '原始HTML', '字符数', '抓取时间']]
            df_original.to_excel(writer, sheet_name='原始HTML', index=False)
            
            # Sheet4: 清洗后HTML数据
            df_cleaned = df[['URL', '清洗后HTML', '清洗后长度']]
            df_cleaned.to_excel(writer, sheet_name='清洗后HTML', index=False)
        
        print(f"🎉 批量抓取与清洗完成！")
        print(f"📁 结果保存至: {output_file}")
        print(f"📊 成功: {len(results)}/{len(url_list)} 个页面")
        
        if failed_urls:
            with open('抓取失败.txt', 'w', encoding='utf-8') as f:
                for url in failed_urls:
                    f.write(url + '\n')
            print(f"📝 失败URL列表已保存至: 抓取失败.txt")
        
        # 显示样本
        if results:
            print(f"\n📄 样本预览:")
            print("-" * 40)
            sample_url = results[0]['URL']
            sample_html = results[0]['清洗后HTML'][:300]
            print(f"URL: {sample_url[:50]}...")
            print(f"清洗后HTML预览: {sample_html}...")
        
        return df
    else:
        print("❌ 所有页面处理失败")
        return None

def read_urls_from_file(filename: str = 'urls.txt') -> List[str]:
    """
    从文本文件中读取URL列表，自动为没有协议头的URL添加https://。
    忽略空行和以'#'开头的注释行。

    Args:
        filename (str): 文件路径，默认为'urls.txt'

    Returns:
        List[str]: 处理后的URL列表
    """
    try:
        urls = []
        with open(filename, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # 检查URL是否有协议头
                url = line
                if not (url.startswith('http://') or url.startswith('https://')):
                    url = 'https://' + url
                    print(f"第{line_num}行: 添加https://协议头 -> {url}")
                
                urls.append(url)
        
        return urls
    except FileNotFoundError:
        print(f"⚠️  文件 {filename} 不存在")
        return []
    except Exception as e:
        print(f"读取URL文件出错: {e}")
        return []

def create_sample_files():
    """
    创建示例文件 urls.txt 和 插入html模板.txt（如果它们不存在）。
    """
    # 创建示例urls.txt
    if not os.path.exists('urls.txt'):
        with open('urls.txt', 'w', encoding='utf-8') as f:
            f.write("# 请在此处添加产品URL，每行一个\n")
            f.write("# 可以包含或不包含http://或https://协议头\n")
            f.write("# 示例URL:\n")
            f.write("# https://www.example.com/product1\n")
            f.write("# http://www.example.com/product2\n")
            f.write("# www.example.com/product3 (脚本会自动添加https://)\n")
            f.write("# example.com/product4 (脚本会自动添加https://)\n")
        print("✅ 已创建示例 urls.txt 文件")
    
    # 创建示例HTML模板
    if not os.path.exists('插入html模板.txt'):
        default_template = '''<div id="ali-anchor-AliPostDhMb-cfrdt" class="mceSectionContainer" style="padding-top: 8px;" data-section="AliPostDhMb-cfrdt" data-section-title="Product Description">
<div id="ali-title-AliPostDhMb-cfrdt" style="padding: 8px 0; border-bottom: 1px solid #ddd;">
<span style="background-color: #ddd; color: #333; font-weight: bold; padding: 8px 10px; line-height: 12px;">Product Description</span>
</div>
<div style="padding: 10px 0;">
<p>&nbsp;</p>
</div>
</div>
<div id="ali-anchor-AliPostDhMb-z2z5r" class="mceSectionContainer" style="padding-top: 8px;" data-section="AliPostDhMb-z2z5r" data-section-title="FAQ">
<div id="ali-title-AliPostDhMb-z2z5r" style="padding: 8px 0; border-bottom: 1px solid #ddd;">
<span style="background-color: #ddd; color: #333; font-weight: bold; padding: 8px 10px; line-height: 12px;">FAQ</span>
</div>
<div style="padding: 10px 0;">
<p>&nbsp;<strong>1. who are we?</strong><br />
We are based in Shanghai, China, start from 2012,sell to Western Europe(25.00%),North America(20.00%),Eastern Europe(15.00%),South America(10.00%),Domestic Market(5.00%),Northern Europe(5.00%),Southeast Asia(5.00%),Eastern Asia(5.00%),Mid East(5.00%),Oceania(5.00%). There are total about 51-100 people in our office.</p>
</div>
</div>'''
        
        with open('插入html模板.txt', 'w', encoding='utf-8') as f:
            f.write(default_template)
        print("✅ 已创建示例 插入html模板.txt 文件")

def main():
    """
    主程序入口：
        1. 显示工具信息
        2. 创建示例文件（如果不存在）
        3. 读取URL列表
        4. 询问用户输出文件名和确认
        5. 启动批量处理
        6. 输出耗时和统计信息
    """
    print("=" * 60)
    print("产品详情HTML片段抓取与清洗工具")
    print("批量抓取tab_content区域，清洗后插入阿里模板")
    print("=" * 60)
    
    # 检查并创建示例文件
    create_sample_files()
    
    # 从urls.txt读取URL
    url_list = read_urls_from_file('urls.txt')
    
    if not url_list:
        print("请在同目录的 urls.txt 文件中添加产品URL，每行一个")
        input("按Enter键退出...")
        return
    
    # 检查模板文件
    template_file = '插入html模板.txt'
    if not os.path.exists(template_file):
        print(f"⚠️  模板文件 {template_file} 不存在，使用默认模板")
    
    # 询问输出文件名
    default_output = f'产品HTML_{time.strftime("%Y%m%d_%H%M")}.xlsx'
    output_file = input(f"📁 输出文件名 (默认: {default_output}): ").strip()
    if not output_file:
        output_file = default_output
    
    # 确认开始
    print(f"\n即将处理 {len(url_list)} 个产品页面")
    print(f"每个页面最多重试3次")
    print(f"模板文件: {template_file}")
    confirm = input("是否开始？ (y/n): ").strip().lower()
    
    if confirm != 'y':
        print("取消操作")
        return
    
    # 开始批量处理
    start_time = time.time()
    result_df = batch_crawl_and_convert(url_list, template_file, output_file)
    end_time = time.time()
    
    if result_df is not None:
        print(f"\n⏱️  总耗时: {end_time - start_time:.2f} 秒")
        print(f"📊 平均每个页面: {(end_time - start_time) / len(url_list):.2f} 秒")
    
    print("\n✨ 任务完成！")
    print("\n使用说明:")
    print("1. 在 urls.txt 中添加产品URL")
    print("2. 在 插入html模板.txt 中配置HTML模板")
    print("3. 运行此脚本进行批量处理")
    print("4. 结果将保存到Excel文件，包含四个sheet:")
    print("   - 完整数据: 所有字段")
    print("   - HTML结果: 仅URL和完整HTML")
    print("   - 原始HTML: 仅原始HTML片段")
    print("   - 清洗后HTML: 仅清洗后的HTML片段")

# 直接运行主函数
if __name__ == "__main__":
    main()
