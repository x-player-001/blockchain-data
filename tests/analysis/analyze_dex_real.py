#!/usr/bin/env python3
"""
使用 undetected-chromedriver 分析 DexScreener 真实页面结构
"""

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import time
import json

def analyze_real_page():
    """分析真实页面结构"""

    print("启动 undetected Chrome...")

    # 设置选项 - 不使用无头模式，undetected-chromedriver在无头模式下可能有问题
    options = uc.ChromeOptions()
    # options.add_argument('--headless=new')  # 暂时禁用无头模式
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')

    driver = uc.Chrome(options=options, version_main=None)

    try:
        print("\n访问 DexScreener BSC 页面...")
        driver.get("https://dexscreener.com/bsc")

        # 等待页面完全加载
        print("等待页面加载...")
        time.sleep(10)

        # 保存页面源码
        with open('dex_real_page.html', 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        print("✓ 页面源码已保存到 dex_real_page.html")

        # 查找包含数据的元素
        print("\n分析页面结构...")

        # 尝试查找表格行
        print("\n1. 查找表格元素...")
        tables = driver.find_elements(By.TAG_NAME, 'table')
        print(f"   找到 {len(tables)} 个 table")

        # 查找所有链接
        print("\n2. 查找交易对链接...")
        links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/bsc/0x"]')
        print(f"   找到 {len(links)} 个 BSC 交易对链接")

        if links:
            print("\n   前5个链接示例:")
            for i, link in enumerate(links[:5], 1):
                href = link.get_attribute('href')
                text = link.text
                parent_html = link.find_element(By.XPATH, '..').get_attribute('outerHTML')
                print(f"\n   {i}. {href}")
                print(f"      文本: {text[:100]}")
                print(f"      父元素HTML(前200字符): {parent_html[:200]}")

        # 查找包含百分比的元素（涨跌幅）
        print("\n3. 查找涨跌幅元素...")
        percent_elems = driver.find_elements(By.XPATH, "//*[contains(text(), '%')]")
        print(f"   找到 {len(percent_elems)} 个包含 % 的元素")

        if percent_elems:
            print("\n   前10个示例:")
            for i, elem in enumerate(percent_elems[:10], 1):
                text = elem.text.strip()
                class_name = elem.get_attribute('class')
                tag = elem.tag_name
                print(f"   {i}. [{tag}] {text} (class={class_name})")

        # 尝试找到代币列表的容器
        print("\n4. 查找可能的代币列表容器...")

        # 常见的容器选择器
        selectors = [
            'div[class*="table"]',
            'div[class*="list"]',
            'div[class*="row"]',
            'div[class*="token"]',
            'div[class*="pair"]',
        ]

        for selector in selectors:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                print(f"\n   {selector}: {len(elements)} 个")

                # 查看第一个元素
                if len(elements) > 0:
                    first = elements[0]
                    html = first.get_attribute('outerHTML')
                    print(f"   第一个元素HTML(前300字符):\n   {html[:300]}")

        # 尝试执行JavaScript获取React数据
        print("\n5. 尝试获取页面数据对象...")
        try:
            # 尝试查找 window 对象中的数据
            script = """
            var data = {};
            if (window.__NEXT_DATA__) data.nextData = window.__NEXT_DATA__;
            if (window.__remixContext) data.remixContext = window.__remixContext;
            return JSON.stringify(data);
            """
            result = driver.execute_script(script)
            if result and result != '{}':
                print("   ✓ 找到数据对象！")
                with open('dex_data.json', 'w', encoding='utf-8') as f:
                    f.write(result)
                print("   已保存到 dex_data.json")

                # 解析并显示结构
                data_obj = json.loads(result)
                print(f"   数据键: {list(data_obj.keys())}")
            else:
                print("   未找到标准数据对象")
        except Exception as e:
            print(f"   执行脚本失败: {e}")

        # 截图
        print("\n6. 截图保存...")
        driver.save_screenshot('dex_screenshot.png')
        print("   ✓ 截图已保存到 dex_screenshot.png")

        print("\n" + "="*60)
        print("分析完成！请检查以下文件:")
        print("  - dex_real_page.html (页面源码)")
        print("  - dex_screenshot.png (截图)")
        print("  - dex_data.json (如果找到数据对象)")
        print("="*60)

    finally:
        driver.quit()

if __name__ == '__main__':
    analyze_real_page()
