import pandas as pd

# ============================================
# 功能说明：图片填充工具
# 用途：将图片库中的产品图按型号分组，自动填充至10张图
# 规则：
#   1. 每个型号的产品图如果不足5张，用公司介绍图补齐到5张
#   2. 总共需要10张图，剩余5张循环使用公司介绍图填充
# 输出：Excel文件，包含型号 + 10张图片URL
# ============================================

# 1. 读取图片库（输入文件：图片库.xlsx）
# 格式要求：A列=序号, B列=型号, C列=图片URL
df_pics = pd.read_excel('图片库.xlsx')

# 2. 定义5张公司介绍图（用于填充不足的图片位）
company_imgs = [
    "https://b2b-material.cdn.bcebos.com/-VDOmVMd6KC17m6YX5RXlxAFAh4.jpg",
    "https://b2b-material.cdn.bcebos.com/b1AKhptMWCQCpSi5qLHxxBAFKVQ.jpg",
    "https://b2b-material.cdn.bcebos.com/exMn5WEuCAs0hmBjMtNJRxAGUD0.jpg",
    "https://b2b-material.cdn.bcebos.com/k0GfCGPSrnI9A2-TjjNr0xADPK0.jpg",
    "https://b2b-material.cdn.bcebos.com/V-x0AF2_kZlQzHVNULPC6BAIXTI.jpg"
]


def get_clean_model(name):
    """
    清洗型号名称：去掉末尾的数字后缀
    例如："ABC_123" -> "ABC"，"ABC" -> "ABC"
    用于将同一型号的不同变体归类到一起
    """
    name = str(name).strip()
    if '_' in name:
        parts = name.rsplit('_', 1)      # 从右边分割，只分割一次
        if parts[1].isdigit():           # 如果后缀是纯数字
            return parts[0]              # 返回前缀部分
    return name


# 自动识别列名（防止繁简体或列名变动导致错误）
# 假设列顺序固定：第1列=序号, 第2列=型号, 第3列=URL
model_col = df_pics.columns[1]   # 型号所在列（第2列，索引1）
url_col = df_pics.columns[2]     # URL所在列（第3列，索引2）

# 为每条记录计算"根型号"（去掉数字后缀后的型号）
df_pics['根型号'] = df_pics[model_col].apply(get_clean_model)

result_rows = []

# 3. 按根型号分组处理
for model, group in df_pics.groupby('根型号'):
    
    # 跳过"公司介绍"这个特殊型号（它本身就是填充用的素材）
    if "公司介紹" in str(model):
        continue
    
    # 获取该型号下的所有产品图URL
    p_urls = group[url_col].tolist()
    final_10 = list(p_urls)
    num_p = len(final_10)
    
    # 填充逻辑 Step 1：如果产品图少于5张，用公司图补齐到5张
    if num_p < 5:
        final_10.extend(company_imgs[:(5 - num_p)])
    
    # 填充逻辑 Step 2：继续用公司图循环填充，直到凑够10张
    # 使用模运算实现循环取图（第6张取company_imgs[0]，第7张取[1]...）
    while len(final_10) < 10:
        idx = (len(final_10) - num_p) % 5   # 计算当前应该取公司图的第几张
        final_10.append(company_imgs[idx])
    
    # 组装结果行：[型号, 图1, 图2, ..., 图10]
    result_rows.append([model] + final_10[:10])

# 4. 生成输出Excel
# 表头格式：第1列是型号，后面10列是图片URL
cols = ['產品型號', '主圖1', '主圖2', '主圖3', '主圖4', '主圖5', 
        '主圖6', '主圖7', '主圖8', '主圖9', '主圖10']

final_df = pd.DataFrame(result_rows, columns=cols)
final_df.to_excel('Allie_愛採購填充修復版.xlsx', index=False)

print("🎉 完成！输出文件：Allie_愛採購填充修復版.xlsx")
