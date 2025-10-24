#!/usr/bin/env python3
"""
分析DexScreener首页HTML结构，找出需要的字段
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
import json

def analyze_page_structure():
    """分析页面结构"""

    # 设置Chrome
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')

    driver = webdriver.Chrome(options=chrome_options)

    try:
        print("访问 DexScreener BSC 页面...")
        driver.get("https://dexscreener.com/bsc")

        # 等待页面加载
        time.sleep(8)

        print("\n查找代币行元素...")

        # 尝试不同的选择器
        selectors = [
            'a[href*="/bsc/0x"]',  # 包含BSC地址的链接
            'div[class*="token"]', # 包含token的div
            'tr',  # 表格行
            'div[class*="pair"]',  # 包含pair的div
        ]

        for selector in selectors:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            print(f"\n{selector}: 找到 {len(elements)} 个元素")

            if len(elements) > 0:
                # 分析前3个元素
                for i, elem in enumerate(elements[:3], 1):
                    print(f"\n{'='*60}")
                    print(f"元素 {i}:")
                    print(f"{'='*60}")

                    # 获取文本
                    text = elem.text
                    print(f"文本内容:\n{text[:500]}")

                    # 获取HTML
                    html = elem.get_attribute('outerHTML')
                    print(f"\nHTML (前500字符):\n{html[:500]}")

                    # 获取所有属性
                    attrs = driver.execute_script(
                        'var items = {}; '
                        'for (index = 0; index < arguments[0].attributes.length; ++index) { '
                        '    items[arguments[0].attributes[index].name] = arguments[0].attributes[index].value '
                        '}; '
                        'return items;',
                        elem
                    )
                    print(f"\n属性:\n{json.dumps(attrs, indent=2)}")

        # 专门查找包含价格变化的元素
        print("\n" + "="*60)
        print("查找价格变化元素...")
        print("="*60)

        # 查找包含百分比的元素
        percent_elements = driver.find_elements(By.XPATH, "//*[contains(text(), '%')]")
        print(f"\n找到 {len(percent_elements)} 个包含 % 的元素")

        for i, elem in enumerate(percent_elements[:10], 1):
            text = elem.text.strip()
            if text and '%' in text:
                print(f"{i}. {text} | class={elem.get_attribute('class')}")

        # 保存页面源码
        print("\n保存页面源码...")
        with open('dex_page_source.html', 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        print("已保存到 dex_page_source.html")

        # 执行JavaScript获取页面数据
        print("\n尝试获取页面数据对象...")
        try:
            # 尝试查找可能存在的数据对象
            data_scripts = driver.find_elements(By.TAG_NAME, 'script')
            print(f"找到 {len(data_scripts)} 个script标签")

            for i, script in enumerate(data_scripts[:5]):
                content = script.get_attribute('innerHTML')
                if content and len(content) > 100:
                    print(f"\nScript {i} (前300字符):")
                    print(content[:300])
        except Exception as e:
            print(f"获取script失败: {e}")

    finally:
        driver.quit()

if __name__ == '__main__':
    analyze_page_structure()
