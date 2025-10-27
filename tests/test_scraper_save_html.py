"""
测试爬虫并保存HTML
"""

import time
import random
from bs4 import BeautifulSoup


def scrape_and_save_html():
    try:
        import undetected_chromedriver as uc
    except ImportError as e:
        print(f"无法导入 undetected-chromedriver: {e}")
        return

    print("="*80)
    print("开始爬取并保存HTML")
    print("="*80)

    driver = None

    try:
        # 配置 Chrome 选项
        options = uc.ChromeOptions()
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-gpu')

        USER_AGENTS = [
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        ]
        options.add_argument(f'--user-agent={random.choice(USER_AGENTS)}')

        # 创建 undetected driver
        print("启动浏览器...")
        driver = uc.Chrome(options=options, version_main=None)

        url = "https://dexscreener.com/bsc"
        print(f"正在访问: {url}")

        driver.get(url)

        # 等待页面加载
        print("等待页面加载...")
        time.sleep(random.uniform(5, 8))

        # 模拟滚动
        print("模拟用户滚动...")
        driver.execute_script("window.scrollTo(0, 500);")
        time.sleep(random.uniform(1, 2))
        driver.execute_script("window.scrollTo(0, 1000);")
        time.sleep(random.uniform(1, 2))

        # 获取页面内容
        page_source = driver.page_source

        # 保存HTML
        html_file = '/tmp/dexscreener_bsc.html'
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(page_source)
        print(f"\n✅ HTML已保存到: {html_file}")
        print(f"   文件大小: {len(page_source):,} 字符")

        # 解析并显示基本信息
        soup = BeautifulSoup(page_source, 'html.parser')
        token_rows = soup.select('a.ds-dex-table-row')
        print(f"   找到代币行数: {len(token_rows)} 个")

        # 分析第一个代币行的结构
        if token_rows:
            print(f"\n第一个代币行的文本内容:")
            first_row = token_rows[0]
            text = first_row.get_text(separator='|', strip=True)
            parts = text.split('|')
            print(f"  总共 {len(parts)} 个字段:")
            for i, part in enumerate(parts[:30], 1):  # 只显示前30个
                print(f"    [{i:2d}] {part}")

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

    finally:
        if driver:
            try:
                driver.quit()
                print("\n浏览器已关闭")
            except:
                pass


if __name__ == "__main__":
    scrape_and_save_html()
