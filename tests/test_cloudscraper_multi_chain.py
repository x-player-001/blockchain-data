#!/usr/bin/env python3
"""
使用 cloudscraper 爬取 DexScreener - 多链支持
支持 BSC 和 Solana
"""

import cloudscraper
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from datetime import datetime
import json


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
    """
    解析单个代币行

    Args:
        row_element: BeautifulSoup 元素
        rank: 排名
        chain: 链名称 (bsc, solana)
    """
    # 提取 pair address
    href = row_element.get('href', '')

    # 根据链提取 pair address
    chain_prefix = f'/{chain}/'
    if chain_prefix not in href:
        return None

    pair_address = href.split(chain_prefix)[-1].split('?')[0]

    # BSC是42位，Solana是44位
    expected_len = 42 if chain == 'bsc' else 44
    if len(pair_address) != expected_len:
        return None

    # 获取完整文本并分割
    full_text = row_element.get_text(separator='|', strip=True)
    parts = full_text.split('|')

    # 初始化代币数据
    token_data = {
        'pair_address': pair_address,
        'url': f"https://dexscreener.com{href}",
        'rank': rank,
        'chain': chain,
    }

    try:
        # 提取代币名称和符号 (固定位置)
        if len(parts) > 6:
            token_data['token_name'] = parts[3]
            token_data['base_token'] = parts[5]  # WBNB 或 SOL
            token_data['token_symbol'] = parts[6]

        # 提取价格 (找到第一个 $ 后的数字)
        for i, part in enumerate(parts):
            if part == '$' and i + 1 < len(parts):
                try:
                    price_str = parts[i + 1]
                    # 只提取纯数字（不带单位的才是价格）
                    if 'K' not in price_str and 'M' not in price_str and 'B' not in price_str:
                        token_data['price_usd'] = float(price_str)
                        break
                except:
                    pass

        # 精确定位4个百分比的位置 (5m, 1h, 6h, 24h)
        percent_positions = []
        for i, part in enumerate(parts):
            if '%' in part and part != '%':
                try:
                    value = float(part.replace('%', '').replace('+', ''))
                    percent_positions.append((i, value))
                except:
                    pass

        # 找到连续的4个百分比
        if len(percent_positions) >= 4:
            for i in range(len(percent_positions) - 3):
                pos1, val1 = percent_positions[i]
                pos2, val2 = percent_positions[i + 1]
                pos3, val3 = percent_positions[i + 2]
                pos4, val4 = percent_positions[i + 3]

                # 如果这4个位置是连续的或接近的
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

        # 提取交易量
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


def scrape_dexscreener(
    chain: str = 'bsc',
    limit: int = 100,
    verbose: bool = True
) -> List[Dict[str, Any]]:
    """
    使用 cloudscraper 爬取 DexScreener

    Args:
        chain: 链名称 (bsc, solana)
        limit: 最多获取多少个代币
        verbose: 是否打印详细信息
    """

    if verbose:
        print(f"\n{'='*80}")
        print(f"爬取 DexScreener {chain.upper()} 链")
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
        token_data = parse_token_row(row, i, chain)

        if token_data:
            tokens.append(token_data)

    if verbose:
        print(f"   ✓ 成功提取 {len(tokens)} 个代币\n")

    return tokens


def find_specific_pair(tokens: List[Dict], pair_address: str) -> Dict:
    """在代币列表中查找特定的 pair"""
    pair_address = pair_address.lower()
    for token in tokens:
        if token.get('pair_address', '').lower() == pair_address:
            return token
    return None


if __name__ == "__main__":
    print("\n" + "="*80)
    print("DexScreener 多链爬取测试")
    print("="*80)

    # 1. 爬取 BSC 链
    bsc_tokens = scrape_dexscreener(chain='bsc', limit=100, verbose=True)

    # 2. 爬取 Solana 链
    solana_tokens = scrape_dexscreener(chain='solana', limit=100, verbose=True)

    # 3. 按24h涨幅排序，各取前10
    print("\n" + "="*80)
    print("BSC 链 - 按 24h 涨幅排序 Top 10")
    print("="*80)

    bsc_with_24h = [t for t in bsc_tokens if 'price_change_24h' in t]
    bsc_top10 = sorted(bsc_with_24h, key=lambda x: x.get('price_change_24h', 0), reverse=True)[:10]

    for i, token in enumerate(bsc_top10, 1):
        symbol = token.get('token_symbol', 'N/A')[:15]
        price = token.get('price_usd', 0)
        change_24h = token.get('price_change_24h', 0)
        mcap = token.get('market_cap', 0)
        pair = token.get('pair_address', '')[:10]

        print(f"{i:2d}. {symbol:15s} ${price:10.6f} 24h:{change_24h:+7.1f}% MCap:${mcap:10,.0f} {pair}...")

    print("\n" + "="*80)
    print("Solana 链 - 按 24h 涨幅排序 Top 10")
    print("="*80)

    solana_with_24h = [t for t in solana_tokens if 'price_change_24h' in t]
    solana_top10 = sorted(solana_with_24h, key=lambda x: x.get('price_change_24h', 0), reverse=True)[:10]

    for i, token in enumerate(solana_top10, 1):
        symbol = token.get('token_symbol', 'N/A')[:15]
        price = token.get('price_usd', 0)
        change_24h = token.get('price_change_24h', 0)
        mcap = token.get('market_cap', 0)
        pair = token.get('pair_address', '')[:10]

        print(f"{i:2d}. {symbol:15s} ${price:10.6f} 24h:{change_24h:+7.1f}% MCap:${mcap:10,.0f} {pair}...")

    # 4. 查找特定的 BSC pair
    target_pair = '0xd504bcaebad45a1c92b14b14a9ab29a566ed2d42'

    print("\n" + "="*80)
    print(f"查找 BSC 特定 Pair: {target_pair}")
    print("="*80)

    target_token = find_specific_pair(bsc_tokens, target_pair)

    if target_token:
        print("\n✅ 找到该代币！\n")
        print(f"排名:        #{target_token.get('rank', 'N/A')}")
        print(f"代币符号:    {target_token.get('token_symbol', 'N/A')}")
        print(f"代币名称:    {target_token.get('token_name', 'N/A')}")
        print(f"Pair地址:    {target_token.get('pair_address', 'N/A')}")
        print(f"价格(USD):   ${target_token.get('price_usd', 0):.8f}")
        print(f"5分钟涨幅:   {target_token.get('price_change_5m', 0):+.2f}%")
        print(f"1小时涨幅:   {target_token.get('price_change_1h', 0):+.2f}%")
        print(f"6小时涨幅:   {target_token.get('price_change_6h', 0):+.2f}%")
        print(f"24小时涨幅:  {target_token.get('price_change_24h', 0):+.2f}%")
        print(f"市值:        ${target_token.get('market_cap', 0):,.0f}")
        print(f"流动性:      ${target_token.get('liquidity_usd', 0):,.0f}")
        print(f"24h交易量:   {target_token.get('volume_24h', 0):,.0f}")
        print(f"链接:        {target_token.get('url', 'N/A')}")

        # 保存该代币的详细数据
        with open('target_pair_data.json', 'w', encoding='utf-8') as f:
            json.dump(target_token, f, indent=2, ensure_ascii=False)

        print(f"\n已保存详细数据到: target_pair_data.json")
    else:
        print("\n❌ 未找到该 pair")
        print(f"   可能原因:")
        print(f"   1. 该 pair 不在前100个代币中")
        print(f"   2. 该 pair 地址有误")
        print(f"   3. 该代币已下架")

    # 5. 保存所有数据
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    output_data = {
        'timestamp': timestamp,
        'bsc_top10': bsc_top10,
        'solana_top10': solana_top10,
        'bsc_total': len(bsc_tokens),
        'solana_total': len(solana_tokens),
    }

    output_file = f'dexscreener_multi_chain_{timestamp}.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print("\n" + "="*80)
    print("数据统计")
    print("="*80)
    print(f"BSC 链:      爬取 {len(bsc_tokens)} 个，有24h数据 {len(bsc_with_24h)} 个")
    print(f"Solana 链:   爬取 {len(solana_tokens)} 个，有24h数据 {len(solana_with_24h)} 个")
    print(f"\n已保存到: {output_file}")

    print("\n" + "="*80)
    print("✅ 测试完成！")
    print("="*80)
