import os
import time
import datetime
import pandas as pd
from playwright.sync_api import sync_playwright

# --- 你的配置 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_NAME = "test_alibaba_260206.csv"
CSV_PATH = os.path.join(BASE_DIR, CSV_NAME)
IMAGE_BASE_PATH = r"\\192.168.2.185\User Folder\Lisun-009\Ally\spider\product_main_images"

def get_timestamp():
    """获取当前时间戳"""
    return datetime.datetime.now().strftime("%H:%M:%S")

def get_images(model_name):
    """找图片逻辑"""
    if not os.path.exists(IMAGE_BASE_PATH): return []
    try:
        all_files = os.listdir(IMAGE_BASE_PATH)
        matched = [
            os.path.join(IMAGE_BASE_PATH, f) for f in all_files 
            if f.lower().startswith(model_name.lower()) and 
            (f.lower() == f"{model_name.lower()}.jpg" or "_" in f)
        ]
        return sorted(matched)
    except: return []

def run():
    with sync_playwright() as p:
        print(f"[{get_timestamp()}] 🔗 正在连接你的 Chrome (9222)...")
        try:
            # 1. 连接浏览器
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            page = context.pages[0] 

            # 读取表格
            df = pd.read_csv(CSV_PATH)

            for index, row in df.iterrows():
                model = str(row['型号']).strip()
                print(f"\n[{get_timestamp()}] 🚀 [{index+1}/{len(df)}] 准备发布: {model}")

                # --- 步骤 1: 前往后台 ---
                page.goto("https://i.alibaba.com/index.htm")
                page.wait_for_load_state("domcontentloaded")

                # 登录检查
                if "login" in page.url:
                    print(f"[{get_timestamp()}] 👀 还没登录？我在等你...")
                    while "login" in page.url:
                        time.sleep(1)
                    print(f"[{get_timestamp()}] ✅ 登录成功！")

                # --- 步骤 2: 关键！悬停并点击【商品发布】 ---
                print(f"[{get_timestamp()}] 2️⃣ 触发菜单悬停进入【商品发布】...")
                with context.expect_page() as new_page_info:
                    try:
                        # 悬停在侧边栏“商品管理”项
                        product_manage_menu = page.get_by_text("商品管理", exact=True).first
                        product_manage_menu.hover()
                        time.sleep(1) # 等待动画
                        
                        # 点击子菜单“商品发布”
                        page.get_by_role("link", name="商品发布").click()
                        print(f"[{get_timestamp()}] ✅ 侧边栏跳转成功")
                    except:
                        print(f"[{get_timestamp()}] ⚠️ 悬停失败，尝试暴力直接跳转...")
                        page.evaluate("window.open('https://post.alibaba.com/product/publish.htm?itemId=0')")

                page4 = new_page_info.value
                page4.wait_for_load_state("domcontentloaded")

                # --- 步骤 3: 选类目 ---
                time.sleep(1.5)
                if page4.get_by_text("搜索类目").is_visible() or page4.get_by_text("我已阅读如上规则").is_visible():
                    print(f"[{get_timestamp()}] 🎯 正在选择类目: {row['发品类目']}")
                    categories = str(row['发品类目']).split('>')
                    if page4.get_by_text("搜索类目").is_visible():
                        page4.get_by_text("搜索类目").click()
                        time.sleep(0.3)
                    for cat in categories:
                        try:
                            page4.get_by_text(cat.strip(), exact=True).click()
                        except:
                            page4.get_by_text(cat.strip()).first.click()
                        time.sleep(0.3)
                    read_btn = page4.get_by_role("button", name="我已阅读如上规则")
                    if read_btn.is_visible(): read_btn.click()
                    page4.wait_for_load_state("domcontentloaded")
                    time.sleep(1)

                # --- 步骤 4: 填内容 & 解决弹窗图片上传 ---
                print(f"[{get_timestamp()}] ✍️ 填写商品信息...")
                
                # 屏蔽干扰
                try: page4.get_by_role("button", name="我知道了").click(timeout=1500)
                except: pass

                # 标题
                page4.locator("#struct-productTitle").get_by_role("textbox").fill(str(row['商品名称']))

                # 【重点：解决弹窗问题的图片上传】
                imgs = get_images(model)
                if imgs:
                    print(f"[{get_timestamp()}] 📸 拦截系统弹窗，正在上传图片...")
                    try:
                        # 1. 悬停出现“本地上传”按钮
                        page4.get_by_text("上传图片").first.hover()
                        time.sleep(0.8)
                        
                        # 2. 使用 expect_file_chooser 接管点击动作，防止真实弹窗弹出
                        with page4.expect_file_chooser() as fc_info:
                            page4.get_by_role("button", name="本地上传").first.click()
                        
                        file_chooser = fc_info.value
                        file_chooser.set_files(imgs[:6]) # 自动填入图片
                        print(f"[{get_timestamp()}] ✅ 图片已通过底层注入，无弹窗骚扰")
                        time.sleep(2) 
                    except Exception as e:
                        print(f"[{get_timestamp()}] ⚠️ 图片上传还是有点小脾气: {e}")

                # --- 填写商品属性 (全量不省略版) ---
                
                # 类型
                try:
                    page4.get_by_role("gridcell", name="*类型").get_by_placeholder("请输入或者选择").click()
                    page4.get_by_text(str(row['商品属性—类型']).strip(), exact=True).click()
                    print(f"[{get_timestamp()}] ✅ 类型已填")
                except: pass

                # 功率
                try:
                    page4.get_by_role("gridcell", name="*功率").get_by_placeholder("请输入").fill(str(row['商品属性—功率']).strip())
                    print(f"[{get_timestamp()}] ✅ 功率已填")
                except: pass

                # 防护等级
                try:
                    page4.get_by_role("gridcell", name="*防护等级").get_by_placeholder("请输入或者选择").click()
                    protection_value = str(row['商品属性—防护等级']).strip()
                    page4.get_by_text(protection_value, exact=True).click()
                    print(f"[{get_timestamp()}] ✅ 防护等级已填")
                except: pass

                # 电压 (多选逻辑优化版)
                try:
                    # 1. 点击展开下拉框
                    voltage_trigger = page4.locator("span").filter(has_text="请输入或选择").nth(2)
                    voltage_trigger.click()
                    time.sleep(0.5)
                    
                    # 2. 依次勾选
                    voltage_values = str(row['商品属性—电压']).split(';')
                    for v in voltage_values:
                        v = v.strip()
                        if v:
                            try:
                                # 这里用 exact=True 确保不会点错
                                page4.get_by_text(v, exact=True).click()
                                print(f"[{get_timestamp()}] ✅ 勾选了: {v}")
                                time.sleep(0.2)
                            except:
                                pass
                    
                    # 3. 【关键动作】选完后按 Esc 键关闭下拉框，防止遮挡后续元素
                    page4.keyboard.press("Escape") 
                    print(f"[{get_timestamp()}] 🔒 电压多选框已闭合")
                except Exception as e:
                    print(f"[{get_timestamp()}] ⚠️ 电压填写出错: {e}")

                # 精度等级
                try:
                    page4.get_by_role("gridcell", name="*精度等级").get_by_placeholder("请选择").click()
                    accuracy_class = str(row['商品属性—精度等级']).strip()
                    page4.get_by_text(accuracy_class, exact=True).click()
                    print(f"[{get_timestamp()}] ✅ 精度等级已填")
                except: pass

                # 精度
                try:
                    page4.get_by_role("gridcell", name="*精度", exact=True).get_by_placeholder("请输入或者选择").click()
                    accuracy_val = str(row['商品属性—精度']).strip()
                    page4.get_by_text(accuracy_val, exact=True).click()
                    print(f"[{get_timestamp()}] ✅ 精度已填")
                except: pass

                # 原产地 (输入后按 Esc 关闭下拉建议，再点击商品属性标题)
                try:
                    origin_input = page4.get_by_role("gridcell", name="*原产地").get_by_placeholder("请输入或者选择")
                    origin_input.click()
                    origin_val = str(row['商品属性—原产地']).strip()
                    origin_input.fill(origin_val)
                    time.sleep(0.5)
                    page4.keyboard.press("Escape")
                    page4.get_by_text("商品属性", exact=True).click()
                    print(f"[{get_timestamp()}] ✅ 原产地填写完成，下拉框已关闭")
                except Exception as e:
                    print(f"[{get_timestamp()}] ⚠️ 原产地填写出错: {e}")

                # ========== 支持定做 (JS 暴力点击版) ==========
                try:
                    print(f"[{get_timestamp()}] 🛠️ 正在处理支持定做...")
                    # 1. 增加等待，确保元素加载
                    custom_trigger = page4.get_by_role("gridcell", name="*支持定做").locator("input, .next-select-trigger")
                    custom_trigger.first.wait_for(state="attached", timeout=5000)
                    
                    # 2. 用 JS 触发点击，无视“不可见”报错
                    custom_trigger.first.dispatch_event("click")
                    time.sleep(0.5)
                    
                    # 3. 勾选
                    cv = str(row['商品属性—支持定做']).strip()
                    target_text = "OEM/ODM/OBM" if "OBM" in cv.upper() else cv
                    page4.get_by_text(target_text).first.click()
                    
                    # 4. 闭合
                    page4.keyboard.press("Escape")
                    page4.get_by_text("商品属性", exact=True).click()
                    print(f"[{get_timestamp()}] ✅ 支持定做锁定")
                except Exception as e:
                    print(f"[{get_timestamp()}] ⚠️ 支持定做还是没点到: {e}")

                # 品牌
                try:
                    brand_cell = page4.get_by_role("gridcell", name="品牌").get_by_placeholder("请输入")
                    brand_cell.fill(str(row['商品属性—品牌']))
                    print(f"[{get_timestamp()}] ✅ 品牌已填")
                except: pass

                # 保修期
                try:
                    page4.get_by_role("gridcell", name="保修期").get_by_placeholder("请输入或者选择").click()
                    warranty_val = str(row['商品属性—保修期']).strip()
                    page4.get_by_text(warranty_val, exact=True).click()
                    print(f"[{get_timestamp()}] ✅ 保修期已填")
                except: pass

                # ========== 计量单位 (滚动+强制等待版) ==========
                try:
                    print(f"[{get_timestamp()}] 📏 正在设置计量单位...")
                    unit_trigger = page4.locator("#priceUnit").get_by_placeholder("请选择")
                    # 滚动到视图中，防止被遮挡
                    unit_trigger.scroll_into_view_if_needed()
                    unit_trigger.click()
                    time.sleep(1)  # 给下拉菜单 1 秒反应时间
                    
                    uv = str(row['售卖单位—计量单位']).strip()
                    search = page4.locator(".next-select-menu-search input")
                    
                    if search.first.is_visible():
                        search.first.fill(uv)
                        time.sleep(0.8)  # 等待搜索结果过滤
                        
                    # 关键：先等文字出现，再点它
                    target_option = page4.get_by_text(uv, exact=True).first
                    target_option.wait_for(state="visible", timeout=5000)
                    target_option.click()
                    
                    print(f"[{get_timestamp()}] ✅ 计量单位已填")
                except Exception as e:
                    print(f"[{get_timestamp()}] ⚠️ 计量单位失败: {e}")

                # 价格与库存
                try:
                    min_order = str(row['价格与库存—最小起订量']).strip()
                    if min_order:
                        page4.get_by_role("gridcell", name="* 最小起订量 (件) * 单件价格 (Set/Sets").get_by_placeholder("请输入", exact=True).fill(min_order)
                    
                    price = str(row['价格与库存—单件价格']).strip()
                    if price and price.lower() != 'nan':
                        page4.get_by_role("textbox", name="输入价格").fill(price)
                    
                    page4.get_by_role("textbox", name="请输入", exact=True).nth(3).fill("1") # 库存默认为1
                    print(f"[{get_timestamp()}] ✅ 价格与库存已填")
                except: pass

                # 物流信息 (重量尺寸)
                try:
                    page4.locator("input[name=\"pkgWeight\"]").fill(str(row['物流信息—毛重']))
                    page4.locator("#pkgMeasure input").first.fill(str(row['物流信息—长']))
                    page4.locator("#pkgMeasure input").nth(1).fill(str(row['物流信息—宽']))
                    page4.locator("#pkgMeasure input").nth(2).fill(str(row['物流信息—高']))
                    print(f"[{get_timestamp()}] ✅ 物流尺寸已填")
                except: pass

                # 物流属性
                try:
                    page4.get_by_role("button", name="添加", exact=True).click()
                    time.sleep(0.5)
                    logistics_type = str(row['物流信息—物流属性']).strip()
                    page4.get_by_text(logistics_type).first.click()
                    page4.get_by_role("button", name="确认").click()
                    print(f"[{get_timestamp()}] ✅ 物流属性已填")
                except: pass

                # 公司介绍模板
                try:
                    template_selector = page4.locator("#detail-company-introduction-card-title .next-select-values")
                    if template_selector.is_visible():
                        template_selector.click()
                        time.sleep(0.5)
                        page4.get_by_text("通用").click()
                        page4.get_by_role("button", name="确认").click()
                        print(f"[{get_timestamp()}] ✅ 公司介绍模板已选")
                except: pass

                print(f"[{get_timestamp()}] ✨ {model} 填表完毕！")
                print(f"[{get_timestamp()}] 💡 请在浏览器检查内容，并【手动点击提交】。")
                input(f"[{get_timestamp()}] 👉 发布成功后，按【回车】发下一个...")
                
                page4.close()

        except Exception as e:
            print(f"[{get_timestamp()}] ❌ 全局错误: {e}")

if __name__ == "__main__":
    run()
