#!/usr/bin/env python3
"""
测试 cloudscraper 的高级选项
"""

import cloudscraper
from bs4 import BeautifulSoup
import time

def test_basic():
    """基础方法"""
    print("\n" + "="*80)
    print("测试 1: 基础 cloudscraper")
    print("="*80)

    scraper = cloudscraper.create_scraper()
    response = scraper.get("https://dexscreener.com/bsc", timeout=30)

    print(f"状态码: {response.status_code}")
    print(f"是否被拦截: {'是' if '请稍候' in response.text or 'Just a moment' in response.text else '否'}")

    return response.status_code == 200


def test_with_interpreter():
    """使用 JS 解释器"""
    print("\n" + "="*80)
    print("测试 2: 使用 nodejs 解释器")
    print("="*80)

    try:
        scraper = cloudscraper.create_scraper(
            interpreter='nodejs',
            browser={
                'browser': 'chrome',
                'platform': 'darwin',
                'desktop': True
            }
        )
        response = scraper.get("https://dexscreener.com/bsc", timeout=30)

        print(f"状态码: {response.status_code}")
        print(f"是否被拦截: {'是' if '请稍候' in response.text or 'Just a moment' in response.text else '否'}")

        return response.status_code == 200

    except Exception as e:
        print(f"错误: {e}")
        print("提示: 可能需要安装 nodejs")
        return False


def test_with_delay():
    """使用延迟和更真实的浏览器配置"""
    print("\n" + "="*80)
    print("测试 3: 添加延迟和真实浏览器配置")
    print("="*80)

    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'darwin',
            'mobile': False,
            'desktop': True
        },
        delay=10,  # 10秒延迟
    )

    # 添加更真实的 headers
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
    }

    response = scraper.get("https://dexscreener.com/bsc", headers=headers, timeout=30)

    print(f"状态码: {response.status_code}")
    print(f"是否被拦截: {'是' if '请稍候' in response.text or 'Just a moment' in response.text else '否'}")

    return response.status_code == 200


def test_session():
    """使用 session 保持连接"""
    print("\n" + "="*80)
    print("测试 4: 使用 Session")
    print("="*80)

    # 创建一个 requests session
    session = cloudscraper.create_scraper()

    # 先访问首页
    print("先访问首页...")
    response1 = session.get("https://dexscreener.com", timeout=30)
    print(f"首页状态码: {response1.status_code}")

    # 再访问 BSC 页面
    time.sleep(2)
    print("再访问 BSC 页面...")
    response2 = session.get("https://dexscreener.com/bsc", timeout=30)

    print(f"BSC页面状态码: {response2.status_code}")
    print(f"是否被拦截: {'是' if '请稍候' in response2.text or 'Just a moment' in response2.text else '否'}")

    return response2.status_code == 200


def analyze_cloudflare_type():
    """分析 Cloudflare 类型"""
    print("\n" + "="*80)
    print("分析 Cloudflare 保护类型")
    print("="*80)

    scraper = cloudscraper.create_scraper()
    response = scraper.get("https://dexscreener.com/bsc", timeout=30)

    html = response.text

    # 检查关键词
    checks = {
        'Cloudflare Turnstile': 'turnstile' in html.lower(),
        'Cloudflare Challenge': 'challenge-platform' in html.lower(),
        'JavaScript Challenge': 'jschl' in html.lower(),
        'Captcha': 'captcha' in html.lower(),
        'Rate Limiting': 'rate limit' in html.lower(),
        'Bot Protection': 'bot' in html.lower(),
    }

    print("\n检测结果:")
    for check_name, found in checks.items():
        print(f"  {check_name}: {'✓ 发现' if found else '✗ 未发现'}")

    # 保存 HTML 用于手动检查
    with open('cloudflare_response.html', 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"\n完整 HTML 已保存到: cloudflare_response.html")
    print(f"HTML 前 500 字符:")
    print("-" * 80)
    print(html[:500])
    print("-" * 80)


if __name__ == "__main__":
    # 首先分析 Cloudflare 类型
    analyze_cloudflare_type()

    # 运行所有测试
    tests = [
        ("基础方法", test_basic),
        ("NodeJS 解释器", test_with_interpreter),
        ("延迟+Headers", test_with_delay),
        ("Session", test_session),
    ]

    print("\n\n" + "="*80)
    print("测试总结")
    print("="*80)

    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n{name} 测试异常: {e}")
            results.append((name, False))

    print("\n" + "="*80)
    print("最终结果:")
    print("="*80)
    for name, success in results:
        status = "✅ 成功" if success else "❌ 失败"
        print(f"{name:20s}: {status}")

    if any(success for _, success in results):
        print("\n✅ 至少有一种方法成功！")
    else:
        print("\n❌ 所有方法都失败了")
        print("\n建议:")
        print("1. 查看 cloudflare_response.html 了解具体的保护类型")
        print("2. 考虑继续使用 undetected-chromedriver（已有方案）")
        print("3. 考虑使用 Playwright + stealth 插件")
        print("4. 或者直接在服务器上测试（Cloudflare可能对数据中心IP更宽容）")
