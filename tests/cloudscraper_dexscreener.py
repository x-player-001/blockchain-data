#!/usr/bin/env python3
"""
使用 cloudscraper 爬取 DexScreener - 完整版本
可直接替换现有的 Selenium 方案
"""

import cloudscraper
from bs4 import BeautifulSoup
import re
from typing import List, Dict, Any
from datetime import datetime


def parse_value_with_unit(text: str) -> float:
    """
    解析带单位的数值 (K, M, B)

    Args:
        text: 如 "2.3M", "85K", "1.5B"

    Returns:
        浮点数值
    """
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


def parse_token_row(row_element, rank: int) -> Dict[str, Any]:
    """
    解析单个代币行

    Args:
        row_element: BeautifulSoup 元素
        rank: 排名

    Returns:
        代币数据字典
    """
    # 提取 pair address
    href = row_element.get('href', '')
    if '/bsc/0x' not in href:
        return None

    pair_address = href.split('/bsc/')[-1].split('?')[0]

    if len(pair_address) != 42:
        return None

    # 获取完整文本并分割
    full_text = row_element.get_text(separator='|', strip=True)
    parts = full_text.split('|')

    # 初始化代币数据
    token_data = {
        'pair_address': pair_address,
        'url': f"https://dexscreener.com{href}",
        'rank': rank,
        'chain': 'bsc',
    }

    try:
        # 格式分析:
        # #|1|v2|TokenName|/|WBNB|Symbol|holders|$|price|age|volume|$|mcap|...|change%|...|$|liquidity|$|fdv

        # 提取代币名称和符号 (位置 3 和 6)
        if len(parts) > 6:
            token_data['token_name'] = parts[3]
            token_data['base_token'] = parts[5]  # WBNB
            token_data['token_symbol'] = parts[6]

        # 提取价格 (找到第一个 $ 符号后的数值)
        for i, part in enumerate(parts):
            if part == '$' and i + 1 < len(parts):
                try:
                    token_data['price_usd'] = float(parts[i + 1])
                    break
                except:
                    pass

        # 提取百分比变化 (所有 % 结尾的值)
        percentages = []
        for part in parts:
            if '%' in part and part != '%':
                try:
                    val = float(part.replace('%', '').replace('+', ''))
                    percentages.append(val)
                except:
                    pass

        # 假设最后几个百分比分别是: 5m, 1h, 6h, 24h
        if len(percentages) >= 1:
            token_data['price_change_24h'] = percentages[-1]  # 最后一个是24h
        if len(percentages) >= 2:
            token_data['price_change_6h'] = percentages[-2]
        if len(percentages) >= 3:
            token_data['price_change_1h'] = percentages[-3]
        if len(percentages) >= 4:
            token_data['price_change_5m'] = percentages[-4]

        # 提取市值和流动性 (查找 $ 后面带 M/K/B 的值)
        dollar_values = []
        for i, part in enumerate(parts):
            if part == '$' and i + 1 < len(parts):
                next_part = parts[i + 1]
                if any(unit in next_part for unit in ['K', 'M', 'B']):
                    dollar_values.append(parse_value_with_unit(next_part))

        # 通常第一个大数值是市值，后面的是流动性
        if len(dollar_values) >= 1:
            token_data['market_cap'] = dollar_values[0]
        if len(dollar_values) >= 2:
            token_data['liquidity_usd'] = dollar_values[1]
        if len(dollar_values) >= 3:
            token_data['fdv'] = dollar_values[2]

        # 提取交易量 (数字中带逗号的，在价格之后)
        for part in parts[10:15]:  # 通常在10-15位置
            if ',' in part and '$' not in part:
                try:
                    token_data['volume_24h'] = float(part.replace(',', ''))
                    break
                except:
                    pass

    except Exception as e:
        print(f"   ⚠️  解析第 {rank} 行时部分字段失败: {e}")

    return token_data


def scrape_dexscreener_bsc(
    limit: int = 100,
    verbose: bool = True
) -> List[Dict[str, Any]]:
    """
    使用 cloudscraper 爬取 DexScreener BSC 页面

    Args:
        limit: 最多获取多少个代币
        verbose: 是否打印详细信息

    Returns:
        代币列表，每个代币包含:
        - pair_address: 交易对地址
        - url: DexScreener 链接
        - rank: 排名
        - token_name: 代币名称
        - token_symbol: 代币符号
        - price_usd: 价格(USD)
        - price_change_24h: 24小时涨跌幅
        - market_cap: 市值
        - liquidity_usd: 流动性
        - volume_24h: 24小时交易量
    """
    if verbose:
        print(f"\n{'='*80}")
        print(f"使用 cloudscraper 爬取 DexScreener BSC")
        print(f"{'='*80}\n")

    # 创建 scraper（使用成功的配置）
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'darwin',
            'mobile': False,
            'desktop': True
        },
        delay=10,  # 延迟以模拟人类行为
    )

    # 真实浏览器 headers
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
    if verbose:
        print("1. 请求页面...")

    try:
        response = scraper.get("https://dexscreener.com/bsc", headers=headers, timeout=30)
    except Exception as e:
        if verbose:
            print(f"   ❌ 请求失败: {e}")
        return []

    if response.status_code != 200:
        if verbose:
            print(f"   ❌ 状态码: {response.status_code}")
        return []

    if verbose:
        print(f"   ✓ 状态码: {response.status_code}")
        print(f"   ✓ 响应大小: {len(response.text):,} 字符\n")

    # 检查是否被 Cloudflare 拦截
    if '请稍候' in response.text or 'Just a moment' in response.text:
        if verbose:
            print("   ❌ 仍被 Cloudflare 拦截")
        return []

    # 解析 HTML
    if verbose:
        print("2. 解析 HTML...")

    soup = BeautifulSoup(response.text, 'html.parser')

    # 查找所有代币行
    token_rows = soup.select('a.ds-dex-table-row')

    if not token_rows:
        if verbose:
            print("   ❌ 未找到代币行")
        return []

    if verbose:
        print(f"   ✓ 找到 {len(token_rows)} 个代币行\n")
        print("3. 提取代币数据...")

    # 解析每一行
    tokens = []

    for i, row in enumerate(token_rows[:limit], 1):
        token_data = parse_token_row(row, i)

        if token_data:
            tokens.append(token_data)

            if verbose and i <= 10:
                symbol = token_data.get('token_symbol', 'N/A')
                price = token_data.get('price_usd', 0)
                change = token_data.get('price_change_24h', 0)
                mcap = token_data.get('market_cap', 0)

                print(f"   {i:2d}. {symbol:15s} ${price:12.8f} {change:+7.2f}% MCap: ${mcap:,.0f}")

    if verbose:
        print(f"\n✅ 成功提取 {len(tokens)} 个代币\n")

    return tokens


if __name__ == "__main__":
    # 测试爬取
    tokens = scrape_dexscreener_bsc(limit=100, verbose=True)

    if tokens:
        # 显示统计
        print(f"{'='*80}")
        print("数据统计")
        print(f"{'='*80}\n")

        print(f"总数: {len(tokens)}")

        # 统计各字段覆盖率
        fields = ['price_usd', 'price_change_24h', 'market_cap', 'liquidity_usd', 'volume_24h']
        for field in fields:
            count = sum(1 for t in tokens if t.get(field))
            print(f"{field:20s}: {count}/{len(tokens)} ({count/len(tokens)*100:.1f}%)")

        # 保存到 JSON
        import json
        output_file = f"dexscreener_bsc_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(tokens, f, indent=2, ensure_ascii=False)

        print(f"\n已保存到: {output_file}")

        print(f"\n{'='*80}")
        print("✅ cloudscraper 方案可行！")
        print(f"{'='*80}")
        print("\n优势:")
        print("  1. 成功绕过 Cloudflare")
        print("  2. 无需启动浏览器，速度快")
        print("  3. 资源占用少")
        print("  4. 适合服务器定时任务")
        print("\n可以替换现有的 Selenium + undetected-chromedriver 方案")

    else:
        print("\n❌ 爬取失败")
