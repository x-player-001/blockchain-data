#!/usr/bin/env python3
"""
完整的 cloudscraper 爬取测试 - 提取所有字段
"""

import cloudscraper
from bs4 import BeautifulSoup
import re
from typing import List, Dict, Any

def parse_number(text: str) -> float:
    """解析数字字符串（处理 K, M, B 等单位）"""
    if not text or text == '--':
        return 0.0

    text = text.strip().replace(',', '').replace('$', '')

    multipliers = {
        'K': 1_000,
        'M': 1_000_000,
        'B': 1_000_000_000,
    }

    for suffix, multiplier in multipliers.items():
        if suffix in text:
            try:
                return float(text.replace(suffix, '')) * multiplier
            except:
                return 0.0

    try:
        return float(text)
    except:
        return 0.0


def parse_percentage(text: str) -> float:
    """解析百分比"""
    if not text or text == '--':
        return 0.0

    text = text.strip().replace('%', '').replace('+', '')

    try:
        return float(text)
    except:
        return 0.0


def scrape_dexscreener_bsc(limit: int = 100) -> List[Dict[str, Any]]:
    """
    使用 cloudscraper 爬取 DexScreener BSC 页面

    Args:
        limit: 最多获取多少个代币

    Returns:
        代币列表
    """
    print(f"\n{'='*80}")
    print(f"使用 cloudscraper 爬取 DexScreener BSC (前 {limit} 个)")
    print(f"{'='*80}\n")

    # 创建 scraper（使用成功的配置）
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'darwin',
            'mobile': False,
            'desktop': True
        },
        delay=10,
    )

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

    # 请求页面
    print("1. 请求页面...")
    response = scraper.get("https://dexscreener.com/bsc", headers=headers, timeout=30)

    if response.status_code != 200:
        print(f"   ❌ 请求失败: {response.status_code}")
        return []

    print(f"   ✓ 状态码: {response.status_code}")
    print(f"   ✓ 响应大小: {len(response.text):,} 字符\n")

    # 解析 HTML
    print("2. 解析 HTML...")
    soup = BeautifulSoup(response.text, 'html.parser')

    # 查找所有代币行
    token_rows = soup.select('a.ds-dex-table-row')

    if not token_rows:
        print("   ❌ 未找到代币行")
        return []

    print(f"   ✓ 找到 {len(token_rows)} 个代币行\n")

    # 解析每一行
    print("3. 提取代币数据...")
    tokens = []

    for i, row in enumerate(token_rows[:limit], 1):
        try:
            # 提取 pair address
            href = row.get('href', '')
            if '/bsc/0x' not in href:
                continue

            pair_address = href.split('/bsc/')[-1].split('?')[0]

            if len(pair_address) != 42:
                continue

            # 获取行的完整文本（用于调试）
            full_text = row.get_text(separator='|', strip=True)

            # 尝试提取各个字段
            # DexScreener 的结构可能需要更精确的选择器
            token_data = {
                'pair_address': pair_address,
                'url': f"https://dexscreener.com{href}",
                'rank': i,
                'full_text': full_text[:200],  # 保存前200字符用于调试
            }

            # 尝试从文本中提取信息
            # 格式通常是: #1 v2 TokenName/WBNB TokenSymbol $price 24h volume $mcap holders change% ...

            # 提取价格（$开头的数字）
            price_match = re.search(r'\$([0-9.]+)', full_text)
            if price_match:
                token_data['price_usd'] = float(price_match.group(1))

            # 提取百分比变化
            percent_matches = re.findall(r'([-+]?[0-9.]+)%', full_text)
            if percent_matches:
                # 假设第一个百分比是24h变化
                token_data['price_change_24h'] = float(percent_matches[0])

            tokens.append(token_data)

            if i <= 10:
                print(f"   {i:2d}. {pair_address[:10]}... - {full_text[:80]}...")

        except Exception as e:
            print(f"   ❌ 解析第 {i} 行失败: {e}")
            continue

    print(f"\n✅ 成功提取 {len(tokens)} 个代币\n")

    return tokens


def display_tokens(tokens: List[Dict[str, Any]]):
    """显示代币信息"""
    print(f"{'='*80}")
    print("代币数据详情")
    print(f"{'='*80}\n")

    print(f"{'排名':<6} {'Pair Address':<15} {'价格(USD)':<15} {'24h变化%':<12}")
    print("-" * 80)

    for token in tokens[:20]:
        rank = token.get('rank', 0)
        pair = token.get('pair_address', '')[:12] + '...'
        price = token.get('price_usd', 0)
        change = token.get('price_change_24h', 0)

        print(f"{rank:<6} {pair:<15} ${price:<14.8f} {change:+.2f}%")

    print("-" * 80)
    print(f"\n统计:")
    print(f"  总数: {len(tokens)}")

    prices = [t.get('price_usd', 0) for t in tokens if t.get('price_usd')]
    if prices:
        print(f"  有价格数据: {len(prices)} 个")
        print(f"  价格范围: ${min(prices):.8f} ~ ${max(prices):.8f}")

    changes = [t.get('price_change_24h', 0) for t in tokens if t.get('price_change_24h')]
    if changes:
        print(f"  有涨幅数据: {len(changes)} 个")
        print(f"  涨幅范围: {min(changes):+.2f}% ~ {max(changes):+.2f}%")


if __name__ == "__main__":
    # 爬取数据
    tokens = scrape_dexscreener_bsc(limit=100)

    if tokens:
        # 显示数据
        display_tokens(tokens)

        # 保存到文件
        import json
        output_file = "dexscreener_tokens.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(tokens, f, indent=2, ensure_ascii=False)

        print(f"\n已保存到: {output_file}")

        print(f"\n{'='*80}")
        print("结论")
        print(f"{'='*80}")
        print("✅ cloudscraper 可以成功绕过 Cloudflare")
        print("✅ 可以获取完整的 HTML 内容")
        print("✅ 可以提取 pair address")
        print("")
        print("⚠️  需要进一步优化:")
        print("   1. 更精确的字段提取（代币名称、符号、市值、流动性等）")
        print("   2. 可能需要分析 HTML 结构，使用更准确的 CSS 选择器")
        print("   3. 或者考虑解析页面的 JSON 数据（如果有）")

    else:
        print("\n❌ 爬取失败")
