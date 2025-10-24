#!/usr/bin/env python3
"""
DexScreener 爬虫 - 最终版本
支持 BSC 和 Solana 链
按 24h 涨幅排序取前10
"""

import cloudscraper
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from datetime import datetime
import json
import time


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


def parse_token_row(row_element, rank: int, chain: str) -> Dict[str, Any]:
    """解析单个代币行"""
    href = row_element.get('href', '')
    chain_prefix = f'/{chain}/'

    if chain_prefix not in href:
        return None

    pair_address = href.split(chain_prefix)[-1].split('?')[0]

    # BSC是42位，Solana是44位
    expected_len = 42 if chain == 'bsc' else 44
    if len(pair_address) != expected_len:
        return None

    full_text = row_element.get_text(separator='|', strip=True)
    parts = full_text.split('|')

    token_data = {
        'pair_address': pair_address,
        'url': f"https://dexscreener.com{href}",
        'rank': rank,
        'chain': chain,
    }

    try:
        # 提取基本信息 (BSC 和 Solana 结构不同)
        if chain == 'bsc':
            # BSC: parts[3]=名称, parts[5]=WBNB, parts[6]=符号
            if len(parts) > 6:
                token_data['token_name'] = parts[3]
                token_data['base_token'] = parts[5]
                token_data['token_symbol'] = parts[6]
        else:  # solana
            # Solana 有多种格式，需要检测 DEX 类型标记
            # 标准: #|rank|symbol|/|SOL|name|...
            # CPMM: #|rank|CPMM|symbol|/|SOL|name|...
            # DLMM: #|rank|DLMM|symbol|/|SOL|name|...

            dex_types = ['CPMM', 'CLMM', 'DLMM', 'DYN', 'DYN2', 'wp', 'v2', 'v3']
            offset = 0

            # 检查 parts[2] 是否是 DEX 类型标记
            if len(parts) > 2 and parts[2] in dex_types:
                offset = 1  # 字段位置后移1位
                token_data['dex_type'] = parts[2]

            # 根据偏移提取字段
            symbol_idx = 2 + offset
            base_idx = 4 + offset
            name_idx = 5 + offset

            if len(parts) > name_idx:
                token_data['token_symbol'] = parts[symbol_idx]
                token_data['base_token'] = parts[base_idx]
                token_data['token_name'] = parts[name_idx]

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

        # 提取百分比 (5m, 1h, 6h, 24h)
        # 关键：去除逗号！
        percent_positions = []
        for i, part in enumerate(parts):
            if '%' in part and part != '%':
                try:
                    value = float(part.replace('%', '').replace('+', '').replace(',', ''))
                    percent_positions.append((i, value))
                except:
                    pass

        # 找连续的4个百分比
        if len(percent_positions) >= 4:
            for i in range(len(percent_positions) - 3):
                pos1, val1 = percent_positions[i]
                pos2, val2 = percent_positions[i + 1]
                pos3, val3 = percent_positions[i + 2]
                pos4, val4 = percent_positions[i + 3]

                if (pos2 - pos1 <= 2 and pos3 - pos2 <= 2 and pos4 - pos3 <= 2):
                    token_data['price_change_5m'] = val1
                    token_data['price_change_1h'] = val2
                    token_data['price_change_6h'] = val3
                    token_data['price_change_24h'] = val4
                    break

        # 提取市值、流动性、FDV
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

        # 提取交易量
        for part in parts[10:15]:
            if ',' in part and '$' not in part:
                try:
                    token_data['volume_24h'] = float(part.replace(',', ''))
                    break
                except:
                    pass

    except Exception as e:
        pass

    return token_data


def scrape_dexscreener(chain: str = 'bsc', limit: int = 100, verbose: bool = True) -> List[Dict[str, Any]]:
    """
    爬取 DexScreener

    Args:
        chain: bsc 或 solana
        limit: 最多获取多少个代币
        verbose: 是否打印详细信息
    """
    if verbose:
        print(f"\n{'='*80}")
        print(f"爬取 DexScreener {chain.upper()} 链")
        print(f"{'='*80}\n")

    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'darwin', 'mobile': False, 'desktop': True},
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

    url = f"https://dexscreener.com/{chain}"

    if verbose:
        print(f"1. 请求页面: {url}")

    try:
        response = scraper.get(url, headers=headers, timeout=30)
    except Exception as e:
        if verbose:
            print(f"   ❌ 请求失败: {e}")
        return []

    if response.status_code != 200:
        if verbose:
            print(f"   ❌ 状态码: {response.status_code}")
            print(f"   提示: Cloudflare 可能暂时拦截，请等待几分钟后重试")
        return []

    if '请稍候' in response.text or 'Just a moment' in response.text:
        if verbose:
            print("   ❌ 被 Cloudflare 拦截")
        return []

    if verbose:
        print(f"   ✓ 状态码: {response.status_code}")
        print(f"   ✓ 响应大小: {len(response.text):,} 字符\n")
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

    tokens = []
    for i, row in enumerate(token_rows[:limit], 1):
        token_data = parse_token_row(row, i, chain)
        if token_data:
            tokens.append(token_data)

    if verbose:
        print(f"   ✓ 成功提取 {len(tokens)} 个代币\n")

    return tokens


def get_top_gainers(chain: str = 'bsc', top_n: int = 10) -> List[Dict[str, Any]]:
    """
    获取指定链的 Top N 涨幅代币

    Args:
        chain: bsc 或 solana
        top_n: 前N个

    Returns:
        按24h涨幅排序的代币列表
    """
    tokens = scrape_dexscreener(chain=chain, limit=100, verbose=True)

    # 过滤有24h数据的代币
    tokens_with_24h = [t for t in tokens if 'price_change_24h' in t]

    # 按24h涨幅降序排序
    top_tokens = sorted(tokens_with_24h, key=lambda x: x.get('price_change_24h', 0), reverse=True)[:top_n]

    return top_tokens


def find_specific_pair(chain: str, pair_address: str) -> Dict:
    """查找特定的 pair"""
    tokens = scrape_dexscreener(chain=chain, limit=100, verbose=True)

    pair_address = pair_address.lower()
    for token in tokens:
        if token.get('pair_address', '').lower() == pair_address:
            return token

    return None


if __name__ == "__main__":
    print("\n" + "="*80)
    print("DexScreener 爬虫 - 最终版本")
    print("="*80)

    # 1. 爬取 BSC Top 10
    print("\n🔹 BSC 链")
    bsc_top10 = get_top_gainers(chain='bsc', top_n=10)

    print("="*80)
    print("BSC - Top 10 涨幅代币")
    print("="*80)
    for i, token in enumerate(bsc_top10, 1):
        symbol = token.get('token_symbol', 'N/A')[:15]
        change_24h = token.get('price_change_24h', 0)
        price = token.get('price_usd', 0)
        mcap = token.get('market_cap', 0)

        print(f"{i:2d}. {symbol:15s} ${price:12.8f} 24h:{change_24h:+8.1f}% MCap:${mcap:12,.0f}")

    # 等待一下，避免请求太快
    print("\n⏳ 等待5秒后请求 Solana...")
    time.sleep(5)

    # 2. 爬取 Solana Top 10
    print("\n🔹 Solana 链")
    solana_top10 = get_top_gainers(chain='solana', top_n=10)

    print("="*80)
    print("Solana - Top 10 涨幅代币")
    print("="*80)
    for i, token in enumerate(solana_top10, 1):
        symbol = token.get('token_symbol', 'N/A')[:15]
        change_24h = token.get('price_change_24h', 0)
        price = token.get('price_usd', 0)
        mcap = token.get('market_cap', 0)

        print(f"{i:2d}. {symbol:15s} ${price:12.8f} 24h:{change_24h:+8.1f}% MCap:${mcap:12,.0f}")

    # 3. 查找特定 BSC pair
    target_pair = '0xd504bcaebad45a1c92b14b14a9ab29a566ed2d42'

    print("\n⏳ 等待5秒后查找特定 pair...")
    time.sleep(5)

    print(f"\n🔹 查找 BSC Pair: {target_pair}")
    target_token = find_specific_pair('bsc', target_pair)

    if target_token:
        print("\n" + "="*80)
        print(f"找到 DRAGON 代币 (Pair: {target_pair})")
        print("="*80)
        print(f"\n排名:        #{target_token.get('rank', 'N/A')}")
        print(f"代币:        {target_token.get('token_symbol', 'N/A')}")
        print(f"价格:        ${target_token.get('price_usd', 0):.8f}")
        print(f"5m涨幅:      {target_token.get('price_change_5m', 0):+.2f}%")
        print(f"1h涨幅:      {target_token.get('price_change_1h', 0):+.2f}%")
        print(f"6h涨幅:      {target_token.get('price_change_6h', 0):+.2f}%")
        print(f"24h涨幅:     {target_token.get('price_change_24h', 0):+.2f}%")
        print(f"市值:        ${target_token.get('market_cap', 0):,.0f}")
        print(f"流动性:      ${target_token.get('liquidity_usd', 0):,.0f}")
        print(f"链接:        {target_token.get('url', 'N/A')}")
    else:
        print("\n❌ 未找到该 pair (可能不在前100名)")

    # 4. 保存结果
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    result = {
        'timestamp': timestamp,
        'bsc_top10': bsc_top10,
        'solana_top10': solana_top10,
        'target_pair': target_token if target_token else None,
    }

    output_file = f'dexscreener_result_{timestamp}.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print("\n" + "="*80)
    print(f"✅ 完成！数据已保存到: {output_file}")
    print("="*80)
