#!/usr/bin/env python3
"""
测试 cloudscraper 绕过 Cloudflare 的效果
"""

import cloudscraper
from bs4 import BeautifulSoup
import time
from datetime import datetime

def test_cloudscraper():
    """测试 cloudscraper 能否成功爬取 DexScreener"""

    print("\n" + "="*80)
    print("测试 cloudscraper 爬取 DexScreener BSC 页面")
    print("="*80 + "\n")

    # 创建 scraper 实例
    print("1. 创建 cloudscraper 实例...")
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'darwin',  # macOS
            'mobile': False
        },
        delay=10  # 延迟10秒模拟人类行为
    )

    url = "https://dexscreener.com/bsc"
    print(f"2. 访问页面: {url}")
    print("   (等待绕过 Cloudflare...)")

    start_time = time.time()

    try:
        # 发送请求
        response = scraper.get(url, timeout=30)

        elapsed = time.time() - start_time
        print(f"\n✓ 请求成功！耗时: {elapsed:.1f}秒")
        print(f"  状态码: {response.status_code}")
        print(f"  响应大小: {len(response.text):,} 字符")

        # 检查是否仍在 Cloudflare 页面
        if "请稍候" in response.text or "Just a moment" in response.text:
            print("\n❌ 仍被 Cloudflare 拦截")
            print(f"   页面标题: {response.text[:200]}")
            return False

        # 解析 HTML
        print("\n3. 解析 HTML...")
        soup = BeautifulSoup(response.text, 'html.parser')

        # 查找代币行元素
        token_rows = soup.select('a.ds-dex-table-row')

        if not token_rows:
            print("❌ 未找到代币行元素 (a.ds-dex-table-row)")

            # 尝试其他选择器
            print("\n尝试其他选择器...")
            alternatives = [
                'a[href*="/bsc/0x"]',
                'div[class*="table"]',
                'div[class*="row"]',
            ]

            for selector in alternatives:
                elements = soup.select(selector)
                print(f"  {selector}: 找到 {len(elements)} 个元素")

            # 保存 HTML 用于调试
            debug_file = "debug_dexscreener.html"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(response.text)
            print(f"\n已保存完整HTML到: {debug_file}")
            return False

        print(f"✓ 找到 {len(token_rows)} 个代币行")

        # 提取前10个代币信息
        print("\n4. 提取代币信息:")
        print("-" * 80)

        tokens = []
        for i, row in enumerate(token_rows[:10], 1):
            try:
                # 提取基本信息
                href = row.get('href', '')
                pair_address = href.split('/bsc/')[-1].split('?')[0] if '/bsc/' in href else ''

                # 提取代币符号 - 尝试多个选择器
                symbol_elem = row.select_one('.ds-dex-table-row-col-token')
                if not symbol_elem:
                    symbol_elem = row.select_one('[class*="token"]')

                symbol = symbol_elem.get_text(strip=True) if symbol_elem else "N/A"

                # 提取价格
                price_elem = row.select_one('.ds-dex-table-row-col-price')
                if not price_elem:
                    price_elem = row.select_one('[class*="price"]')

                price = price_elem.get_text(strip=True) if price_elem else "N/A"

                # 提取24h涨幅
                change_elem = row.select_one('.ds-dex-table-row-col-change')
                if not change_elem:
                    change_elem = row.select_one('[class*="change"]')

                change = change_elem.get_text(strip=True) if change_elem else "N/A"

                tokens.append({
                    'symbol': symbol,
                    'price': price,
                    'change_24h': change,
                    'pair_address': pair_address
                })

                print(f"{i:2d}. {symbol:15s} {price:15s} {change:10s} {pair_address[:10]}...")

            except Exception as e:
                print(f"{i:2d}. 解析失败: {e}")

        print("-" * 80)
        print(f"\n✅ 成功提取 {len(tokens)} 个代币！")

        # 保存成功的HTML用于参考
        success_file = f"success_dexscreener_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        with open(success_file, 'w', encoding='utf-8') as f:
            f.write(response.text)
        print(f"已保存成功的HTML到: {success_file}")

        return True

    except cloudscraper.exceptions.CloudflareChallengeError as e:
        print(f"\n❌ Cloudflare挑战失败: {e}")
        return False

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # 首先检查是否安装了 cloudscraper
    try:
        import cloudscraper
        print("✓ cloudscraper 已安装")
    except ImportError:
        print("❌ 未安装 cloudscraper")
        print("\n请运行: pip install cloudscraper")
        exit(1)

    # 检查 BeautifulSoup
    try:
        from bs4 import BeautifulSoup
        print("✓ beautifulsoup4 已安装")
    except ImportError:
        print("❌ 未安装 beautifulsoup4")
        print("\n请运行: pip install beautifulsoup4")
        exit(1)

    # 运行测试
    success = test_cloudscraper()

    print("\n" + "="*80)
    if success:
        print("测试结果: ✅ 成功")
        print("\n建议:")
        print("1. cloudscraper 可以成功绕过 Cloudflare")
        print("2. 可以替换当前的 Selenium 方案")
        print("3. 速度更快、资源占用更少")
    else:
        print("测试结果: ❌ 失败")
        print("\n可能原因:")
        print("1. Cloudflare 检测到了自动化行为")
        print("2. 需要调整 cloudscraper 参数")
        print("3. DexScreener 的页面结构可能已改变")
    print("="*80 + "\n")
