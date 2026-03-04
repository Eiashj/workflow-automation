"""
产品描述抓取脚本 - 免检测版本
直接从产品页面提取描述文本，自动过滤图片注释等噪声，并保存为Excel文件。

主要功能：
1. 从 urls.txt 文件中读取产品URL列表（每行一个）
2. 依次访问每个产品页面，智能提取描述区域（优先定位 <li class="rich_text">）
3. 清洗文本，移除无意义的图片注释和短句
4. 将描述文本合并、去重，保存到Excel文件中
5. 记录抓取失败的URL，便于后续排查
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from typing import List, Dict, Optional

def fetch_product_description(url: str) -> Optional[Dict]:
    """
    抓取单个产品页面的描述文本，并返回结构化数据。

    工作流程：
    1. 发送HTTP请求获取页面HTML
    2. 使用BeautifulSoup解析HTML
    3. 定位描述区域：优先查找 <li class="rich_text">，若不存在则尝试查找包含"Description"文本的标签
    4. 遍历该区域内的所有段落（<p>），提取文本并过滤掉图片注释等噪声
    5. 若提取的段落太少，则回退使用整个区域文本并按行分割
    6. 合并文本，去除多余空行，检查长度是否足够（至少100字符）

    Args:
        url (str): 产品页面的完整URL

    Returns:
        Optional[Dict]: 包含以下字段的字典，若抓取失败则返回None
            - 'URL': 原始URL
            - '产品描述': 清洗后的描述文本（多个段落以两个换行符分隔）
            - '字符数': 描述文本的字符数
            - '抓取时间': 抓取完成的时间戳
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    }
    
    try:
        print(f"  正在抓取: {url[:60]}...")
        
        # 1. 请求页面
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = 'utf-8'
        
        if response.status_code != 200:
            print(f"  ⚠️ 请求失败 (状态码 {response.status_code})")
            return None
        
        # 2. 解析HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 3. 查找描述区域：优先使用精确类名，否则尝试包含“Description”的标签
        description_section = soup.find('li', class_='rich_text')
        if not description_section:
            # 备用查找：遍历所有div/section，检查前100字符是否包含"Description"
            for tag in soup.find_all(['div', 'section']):
                if 'Description' in tag.get_text()[:100]:
                    description_section = tag
                    break
        
        if not description_section:
            print(f"  ⚠️ 未找到描述区域")
            return None
        
        # 4. 智能提取段落文本，过滤图片注释
        all_paragraphs = []
        for p in description_section.find_all('p'):
            # 检查当前段落是否属于图片注释容器
            parent = p.parent
            is_caption = False
            if parent:
                parent_classes = parent.get('class', [])
                parent_id = parent.get('id', '')
                # 如果父元素包含 caption/attachment/image 等类名或id，则视为注释
                if any(keyword in str(parent_classes) + parent_id 
                       for keyword in ['caption', 'attachment', 'image']):
                    is_caption = True
            
            text = p.get_text(strip=True)
            if not text:
                continue
            
            # 处理常见的HTML实体
            text = (text.replace('&#8220;', '"')
                       .replace('&#8221;', '"')
                       .replace('&amp;', '&'))
            
            # 跳过明显的图片注释
            if is_caption:
                continue
            if len(text) < 25 and ('Figure' in text or 'Gauge' in text):
                continue
            # 跳过特定的干扰文本
            if '5 A Withdrawal-Pull Gauge for Effectiveness' in text:
                continue
            
            all_paragraphs.append(text)
        
        # 5. 备选方案：如果通过<p>提取的段落太少，则直接获取整个区域的文本并按行分割
        if len(all_paragraphs) < 3:
            full_text = description_section.get_text(separator='\n', strip=True)
            lines = []
            for line in full_text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                # 同样过滤干扰文本
                if '5 A Withdrawal-Pull Gauge for Effectiveness' in line:
                    continue
                lines.append(line)
            all_paragraphs = lines
        
        # 6. 合并内容，去除多余空行
        if not all_paragraphs:
            return None
        
        final_text = '\n\n'.join(all_paragraphs)
        final_text = re.sub(r'\n{3,}', '\n\n', final_text.strip())
        
        if len(final_text) < 100:
            return None
        
        print(f"  ✅ 成功提取 {len(final_text)} 字符")
        return {
            'URL': url,
            '产品描述': final_text,
            '字符数': len(final_text),
            '抓取时间': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
    except Exception as e:
        print(f"  ❌ 抓取出错: {str(e)[:50]}")
        return None

def batch_crawl(url_list: List[str], output_file: str = '产品描述.xlsx'):
    """
    批量抓取多个产品页面的描述文本，并将结果保存到Excel文件。

    Args:
        url_list (List[str]): 产品URL列表
        output_file (str): 输出Excel文件的路径，默认为'产品描述.xlsx'
    
    Returns:
        pandas.DataFrame or None: 包含成功抓取结果的DataFrame，若全部失败则返回None
    """
    print(f"🚀 开始批量抓取，共 {len(url_list)} 个产品页面")
    print("=" * 60)
    
    results = []
    failed_urls = []
    
    for i, url in enumerate(url_list, 1):
        url = url.strip()
        if not url:
            continue
        
        print(f"[{i}/{len(url_list)}] ", end="")
        
        product_data = fetch_product_description(url)
        
        if product_data:
            results.append(product_data)
        else:
            failed_urls.append(url)
            print(f"  ❌ 抓取失败")
        
        # 礼貌延迟：避免请求频率过高
        if i < len(url_list):
            time.sleep(2)
    
    print("\n" + "=" * 60)
    
    # 保存结果
    if results:
        df = pd.DataFrame(results)
        # 重新排列列的顺序
        df = df[['URL', '产品描述', '字符数', '抓取时间']]
        df.to_excel(output_file, index=False)
        
        print(f"🎉 批量抓取完成！")
        print(f"📁 结果保存至: {output_file}")
        print(f"📊 成功: {len(results)}/{len(url_list)} 个页面")
        
        if failed_urls:
            with open('抓取失败.txt', 'w', encoding='utf-8') as f:
                for url in failed_urls:
                    f.write(url + '\n')
            print(f"📝 失败URL列表已保存至: 抓取失败.txt")
        
        # 显示第一个成功结果的预览
        if results:
            print(f"\n📄 样本预览:")
            print("-" * 40)
            sample = results[0]['产品描述'][:300] + "..."
            print(sample)
        
        return df
    else:
        print("❌ 所有页面抓取失败")
        return None

def read_urls_from_file(filename: str = 'urls.txt'):
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

def main():
    """
    主程序入口：读取URL、询问用户输出文件名、确认后启动批量抓取。
    """
    print("=" * 60)
    print("产品描述抓取工具 - 免检测版")
    print("=" * 60)
    
    # 从urls.txt读取URL
    url_list = read_urls_from_file('urls.txt')
    
    if not url_list:
        print("请在同目录创建 urls.txt 文件，每行一个产品URL")
        input("按Enter键退出...")
        return
    
    # 询问输出文件名
    default_output = '产品描述_' + time.strftime('%Y%m%d_%H%M') + '.xlsx'
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
    batch_crawl(url_list, output_file)
    
    print("\n✨ 任务完成！")

# 直接运行主函数，跳过所有检测
if __name__ == "__main__":
    main()
