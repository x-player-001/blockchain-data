#!/usr/bin/env python3
"""
使用 cloudscraper 爬取 DexScreener - 修正版
正确提取 5m, 1h, 6h, 24h 涨幅
"""

import cloudscraper
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from datetime import datetime


def parse_value_with_unit(text: str) -> float:
    """解析带单位的数值 (K, M, B)"""
    if not text or text == '--':
        return 0.0

    text = text.strip().replace(',', '').replace('$', '')

    multipliers = {'K': 1_000, 'M': 1_000_000, 'B': 1_000_000_000}

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

    文本格式分析:
    #|rank|v2|TokenName|/|WBNB|Symbol|holders|$|price|age|volume|$|mcap|holders|5m%|1h%|6h%|24h%|$|liq|$|fdv

    百分比固定位置（从0开始计数）:
    - 位置14或15: 5m 涨幅
    - 位置15或16: 1h 涨幅
    - 位置16或17: 6h 涨幅
    - 位置17或18: 24h 涨幅
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
        # 提取代币名称和符号 (固定位置)
        if len(parts) > 6:
            token_data['token_name'] = parts[3]
            token_data['base_token'] = parts[5]
            token_data['token_symbol'] = parts[6]

        # 提取价格（处理特殊格式：0.0|零的个数|有效数字）
        for i, part in enumerate(parts):
            if part == '$' and i + 1 < len(parts):
                try:
                    first = parts[i + 1]

                    # 检查是否是特殊格式：0.0|4|9152 = 0.00009152
                    if (first == '0.0' and i + 3 < len(parts) and
                        parts[i + 2].isdigit() and parts[i + 3].isdigit()):
                        zero_count = int(parts[i + 2])
                        significant = parts[i + 3]
                        price_str = '0.' + ('0' * zero_count) + significant
                        token_data['price_usd'] = float(price_str)
                        break

                    # 普通格式
                    if 'K' not in first and 'M' not in first and 'B' not in first:
                        token_data['price_usd'] = float(first)
                        break
                except:
                    pass

        # 关键修正：精确定位4个百分比的位置
        # 先找到所有包含 % 的位置
        percent_positions = []
        for i, part in enumerate(parts):
            if '%' in part and part != '%':
                try:
                    # 去除 %、+、逗号并转换为浮点数
                    value = float(part.replace('%', '').replace('+', '').replace(',', ''))
                    percent_positions.append((i, value))
                except:
                    pass

        # 找到连续的4个百分比（这些应该是 5m, 1h, 6h, 24h）
        if len(percent_positions) >= 4:
            # 查找连续的4个百分比
            for i in range(len(percent_positions) - 3):
                pos1, val1 = percent_positions[i]
                pos2, val2 = percent_positions[i + 1]
                pos3, val3 = percent_positions[i + 2]
                pos4, val4 = percent_positions[i + 3]

                # 如果这4个位置是连续的或接近的（间隔不超过2）
                if (pos2 - pos1 <= 2 and pos3 - pos2 <= 2 and pos4 - pos3 <= 2):
                    token_data['price_change_5m'] = val1
                    token_data['price_change_1h'] = val2
                    token_data['price_change_6h'] = val3
                    token_data['price_change_24h'] = val4
                    break

        # 提取市值和流动性
        dollar_values = []
        for i, part in enumerate(parts):
            if part == '$' and i + 1 < len(parts):
                next_part = parts[i + 1]
                if any(unit in next_part for unit in ['K', 'M', 'B']):
                    dollar_values.append(parse_value_with_unit(next_part))

        if len(dollar_values) >= 1:
            token_data['market_cap'] = dollar_values[0]
        if len(dollar_values) >= 2:
            token_data['liquidity_usd'] = dollar_values[1]
        if len(dollar_values) >= 3:
            token_data['fdv'] = dollar_values[2]

        # 提取交易量 (带逗号的数字)
        for part in parts[10:15]:
            if ',' in part and '$' not in part:
                try:
                    token_data['volume_24h'] = float(part.replace(',', ''))
                    break
                except:
                    pass

    except Exception as e:
        print(f"   ⚠️  解析第 {rank} 行时出错: {e}")

    return token_data


def scrape_dexscreener_bsc(
    limit: int = 100,
    verbose: bool = True
) -> List[Dict[str, Any]]:
    """使用 cloudscraper 爬取 DexScreener BSC 页面"""

    if verbose:
        print(f"\n{'='*80}")
        print(f"使用 cloudscraper 爬取 DexScreener BSC")
        print(f"{'='*80}\n")

    # 创建 scraper
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
    }

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

    # 检查 Cloudflare
    if '请稍候' in response.text or 'Just a moment' in response.text:
        if verbose:
            print("   ❌ 被 Cloudflare 拦截")
        return []

    if verbose:
        print("2. 解析 HTML...")

    soup = BeautifulSoup(response.text, 'html.parser')
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
                symbol = token_data.get('token_symbol', 'N/A')[:15]
                price = token_data.get('price_usd', 0)
                change_24h = token_data.get('price_change_24h', 0)

                print(f"   {i:2d}. {symbol:15s} ${price:12.8f} 24h:{change_24h:+7.2f}%")

    if verbose:
        print(f"\n✅ 成功提取 {len(tokens)} 个代币\n")

    return tokens


if __name__ == "__main__":
    # 测试：从保存的HTML文件爬取（避免重复请求）
    print("测试从保存的HTML文件提取数据...\n")

    from bs4 import BeautifulSoup

    with open('success_page.html', 'r', encoding='utf-8') as f:
        html = f.read()

    soup = BeautifulSoup(html, 'html.parser')
    rows = soup.select('a.ds-dex-table-row')

    print(f"找到 {len(rows)} 个代币行\n")
    print("="*80)
    print("提取前10个代币:")
    print("="*80)

    tokens = []
    for i, row in enumerate(rows[:100], 1):
        token = parse_token_row(row, i)
        if token:
            tokens.append(token)

            if i <= 10:
                symbol = token.get('token_symbol', 'N/A')[:15]
                price = token.get('price_usd', 0)
                change_5m = token.get('price_change_5m', 0)
                change_1h = token.get('price_change_1h', 0)
                change_6h = token.get('price_change_6h', 0)
                change_24h = token.get('price_change_24h', 0)

                print(f"{i:2d}. {symbol:15s} ${price:10.6f} | 5m:{change_5m:+6.1f}% 1h:{change_1h:+6.1f}% 6h:{change_6h:+6.1f}% 24h:{change_24h:+7.1f}%")

    # 按24h涨幅排序，取前10
    print("\n" + "="*80)
    print("按 24h 涨幅排序 - Top 10:")
    print("="*80)

    # 过滤有24h数据的代币
    tokens_with_24h = [t for t in tokens if 'price_change_24h' in t]

    # 按24h涨幅降序排序
    top_10 = sorted(tokens_with_24h, key=lambda x: x.get('price_change_24h', 0), reverse=True)[:10]

    for i, token in enumerate(top_10, 1):
        symbol = token.get('token_symbol', 'N/A')[:15]
        price = token.get('price_usd', 0)
        change_24h = token.get('price_change_24h', 0)
        mcap = token.get('market_cap', 0)

        print(f"{i:2d}. {symbol:15s} ${price:10.6f} 24h:{change_24h:+7.1f}% MCap:${mcap:,.0f}")

    # 保存
    import json
    output_file = f"dexscreener_fixed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(top_10, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Top 10 已保存到: {output_file}")
