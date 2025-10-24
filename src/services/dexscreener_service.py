#!/usr/bin/env python3
"""
DexScreener数据服务
提供统一的接口用于爬取、导入和管理DexScreener代币数据
"""

import time
import json
import asyncio
import requests
import cloudscraper
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from sqlalchemy import select, text

from src.storage.db_manager import DatabaseManager
from src.storage.models import DexScreenerToken
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class DexScreenerService:
    """DexScreener数据服务类"""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """
        初始化服务

        Args:
            db_manager: 数据库管理器实例（可选，如果不提供会自动创建）
        """
        self.db_manager = db_manager
        self._db_created = False

    async def _ensure_db(self):
        """确保数据库管理器已初始化"""
        if self.db_manager is None:
            self.db_manager = DatabaseManager()
            await self.db_manager.init_async_db()
            self._db_created = True

    async def close(self):
        """关闭数据库连接"""
        if self._db_created and self.db_manager:
            await self.db_manager.close()

    # ==================== 爬取功能 ====================

    def setup_chrome_driver(self, headless: bool = False, use_undetected: bool = True) -> webdriver.Chrome:
        """
        设置Chrome驱动

        Args:
            headless: 是否使用无头模式
            use_undetected: 是否使用undetected-chromedriver绕过Cloudflare

        Returns:
            Chrome WebDriver实例
        """
        if use_undetected:
            # 尝试使用undetected-chromedriver绕过Cloudflare
            try:
                import undetected_chromedriver as uc

                # 不使用ChromeOptions，直接用参数
                # 这样更稳定，避免窗口被关闭
                logger.info("正在启动 undetected-chromedriver...")

                # 添加更多选项提高稳定性
                options = uc.ChromeOptions()
                options.add_argument('--disable-blink-features=AutomationControlled')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument('--no-sandbox')

                driver = uc.Chrome(
                    options=options,
                    headless=headless,
                    use_subprocess=True,  # 使用子进程模式更稳定
                    version_main=None,
                    driver_executable_path=None
                )

                logger.info("✓ 使用 undetected-chromedriver")

                # 等待浏览器完全启动和稳定
                import time
                time.sleep(3)  # 增加等待时间到3秒

                try:
                    if not headless:
                        driver.maximize_window()  # 最大化窗口而不是设置固定大小
                        time.sleep(1)  # 窗口操作后再等待
                except Exception as e:
                    logger.debug(f"窗口操作警告: {e}")
                    pass  # 忽略窗口操作错误

                return driver
            except ImportError:
                logger.warning("⚠ undetected-chromedriver 未安装，使用普通Chrome (pip install undetected-chromedriver)")

        # 普通Chrome
        chrome_options = Options()
        if headless:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument(
            'user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )

        logger.info("使用普通 Chrome")
        return webdriver.Chrome(options=chrome_options)

    def scrape_bsc_page(
        self,
        target_count: int = 100,
        headless: bool = False,
        max_scrolls: int = 50
    ) -> List[Dict[str, str]]:
        """
        爬取DexScreener BSC页面的交易对地址

        Args:
            target_count: 目标获取的交易对数量
            headless: 是否使用无头模式
            max_scrolls: 最大滚动次数

        Returns:
            包含交易对信息的列表 [{"pair_address": "0x...", "url": "...", "text": "..."}]
        """
        logger.info(f"开始爬取DexScreener BSC页面，目标: {target_count}个交易对")

        driver = self.setup_chrome_driver(headless=headless)

        try:
            url = "https://dexscreener.com/bsc"
            logger.info(f"访问页面: {url}")
            driver.get(url)

            # 等待页面加载
            time.sleep(5)

            tokens = []
            last_count = 0
            scroll_attempts = 0

            while len(tokens) < target_count and scroll_attempts < max_scrolls:
                # 滚动页面
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)

                # 查找交易对链接
                elements = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/bsc/0x"]')

                if not elements:
                    logger.warning("未找到交易对元素")
                    break

                # 提取唯一的交易对地址
                seen_pairs = set()
                for element in elements:
                    try:
                        href = element.get_attribute('href')
                        if href and '/bsc/0x' in href:
                            pair_address = href.split('/bsc/')[-1].split('?')[0]

                            if (pair_address and
                                pair_address not in seen_pairs and
                                len(pair_address) == 42):
                                seen_pairs.add(pair_address)

                                tokens.append({
                                    'pair_address': pair_address,
                                    'url': href,
                                    'text': element.text[:200] if element.text else ''
                                })
                    except:
                        continue

                current_count = len(tokens)
                if current_count == last_count:
                    scroll_attempts += 1
                    logger.debug(f"滚动 {scroll_attempts}, 代币数: {current_count}")
                else:
                    scroll_attempts = 0
                    logger.info(f"已获取 {current_count}/{target_count} 个交易对")
                    last_count = current_count

            logger.info(f"爬取完成，共获取 {len(tokens)} 个交易对")
            return tokens

        finally:
            driver.quit()

    def fetch_pair_details(
        self,
        pair_addresses: List[str],
        delay: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        使用DexScreener API获取交易对详细信息

        Args:
            pair_addresses: 交易对地址列表
            delay: 请求间隔（秒）

        Returns:
            交易对详细信息列表
        """
        logger.info(f"开始获取 {len(pair_addresses)} 个交易对的详细信息")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json',
        }

        detailed_tokens = []
        total = len(pair_addresses)

        for idx, pair_addr in enumerate(pair_addresses, 1):
            try:
                url = f"https://api.dexscreener.com/latest/dex/pairs/bsc/{pair_addr}"
                response = requests.get(url, headers=headers, timeout=10)

                if response.status_code == 200:
                    data = response.json()

                    # API可能返回 'pair' 或 'pairs'
                    if 'pair' in data:
                        detailed_tokens.append(data['pair'])
                    elif 'pairs' in data and len(data['pairs']) > 0:
                        detailed_tokens.append(data['pairs'][0])

                    if idx % 10 == 0 or idx == total:
                        logger.info(f"进度: {idx}/{total} ({len(detailed_tokens)} 成功)")

                time.sleep(delay)

            except Exception as e:
                logger.error(f"获取交易对 {pair_addr[:10]}... 失败: {e}")

        logger.info(f"获取完成，成功: {len(detailed_tokens)}/{total}")
        return detailed_tokens

    def scrape_and_fetch(
        self,
        target_count: int = 100,
        output_file: Optional[str] = None,
        headless: bool = False,
        filter_old_tokens: bool = False,
        max_age_days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        一键爬取并获取完整数据

        Args:
            target_count: 目标交易对数量
            output_file: 输出JSON文件路径（可选）
            headless: 是否使用无头模式
            filter_old_tokens: 是否过滤掉旧代币（默认False）
            max_age_days: 代币最大年龄（天数），超过此时间的代币会被过滤（默认30天）

        Returns:
            完整的交易对数据列表
        """
        # 第一步：爬取页面获取交易对地址
        pairs = self.scrape_bsc_page(target_count=target_count, headless=headless)

        if not pairs:
            logger.error("未能获取到交易对数据")
            return []

        # 第二步：获取详细信息
        pair_addresses = [p['pair_address'] for p in pairs]
        detailed_data = self.fetch_pair_details(pair_addresses)

        # 第三步：过滤旧代币（如果启用）
        if filter_old_tokens:
            detailed_data = self.filter_tokens_by_age(detailed_data, max_age_days)

        # 保存到文件
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(detailed_data, f, indent=2, ensure_ascii=False)

            logger.info(f"数据已保存到: {output_path}")

        return detailed_data

    # ==================== 从页面解析数据（无需API调用）====================

    def scrape_bsc_page_with_details(
        self,
        target_count: int = 100,
        headless: bool = False,
        max_scrolls: int = 50
    ) -> List[Dict[str, Any]]:
        """
        爬取DexScreener BSC页面并直接从页面解析详细信息（无需调用API）

        Args:
            target_count: 目标获取的交易对数量
            headless: 是否使用无头模式（建议False以绕过Cloudflare）
            max_scrolls: 最大滚动次数

        Returns:
            包含完整代币信息的列表
        """
        logger.info(f"开始爬取DexScreener BSC页面（直接解析HTML），目标: {target_count}个交易对")

        driver = self.setup_chrome_driver(headless=headless, use_undetected=True)

        try:
            url = "https://dexscreener.com/bsc"
            logger.info(f"访问页面: {url}")

            # 给浏览器一点时间稳定
            time.sleep(2)

            driver.get(url)

            # 等待页面加载（等待更长时间以绕过Cloudflare）
            logger.info("等待页面加载（绕过Cloudflare检测）...")

            # 等待Cloudflare检查完成（最多60秒）
            max_wait = 60
            waited = 0
            cloudflare_passed = False

            while waited < max_wait:
                time.sleep(5)
                waited += 5

                try:
                    page_title = driver.title
                    logger.info(f"[{waited}s] 页面标题: {page_title}")

                    # 检查是否还在Cloudflare页面
                    if "请稍候" in page_title or "Just a moment" in page_title:
                        logger.info(f"[{waited}s] 仍在Cloudflare验证中...")
                        continue

                    # 检查是否能找到代币行元素
                    test_elements = driver.find_elements(By.CSS_SELECTOR, 'a.ds-dex-table-row')
                    if len(test_elements) > 0:
                        logger.info(f"✓ [{waited}s] Cloudflare验证通过，找到 {len(test_elements)} 个代币行")
                        cloudflare_passed = True
                        break
                    else:
                        logger.info(f"[{waited}s] 页面已加载但未找到代币行，继续等待...")

                except Exception as e:
                    logger.debug(f"[{waited}s] 检查失败: {e}")

            if not cloudflare_passed:
                logger.warning(f"等待{max_wait}秒后仍未通过Cloudflare验证")

            tokens = []
            seen_pairs = set()
            last_count = 0
            scroll_attempts = 0

            while len(tokens) < target_count and scroll_attempts < max_scrolls:
                # 滚动页面
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)

                # 查找所有代币行元素（使用发现的CSS类名）
                row_elements = driver.find_elements(By.CSS_SELECTOR, 'a.ds-dex-table-row')

                if not row_elements:
                    logger.warning("未找到代币行元素")
                    scroll_attempts += 1
                    continue

                # 解析每一行
                for row in row_elements:
                    try:
                        # 提取pair address
                        href = row.get_attribute('href')
                        if not href or '/bsc/0x' not in href:
                            continue

                        pair_address = href.split('/bsc/')[-1].split('?')[0]

                        if (not pair_address or
                            pair_address in seen_pairs or
                            len(pair_address) != 42):
                            continue

                        seen_pairs.add(pair_address)

                        # 使用CSS选择器提取各个字段
                        token_data = self._parse_row_element(row, pair_address, href)

                        if token_data:
                            tokens.append(token_data)

                    except Exception as e:
                        logger.debug(f"解析行元素失败: {e}")
                        continue

                current_count = len(tokens)
                if current_count == last_count:
                    scroll_attempts += 1
                    logger.debug(f"滚动 {scroll_attempts}, 代币数: {current_count}")
                    # 如果连续3次滚动都没有新数据，说明页面已无更多数据
                    if scroll_attempts >= 3:
                        logger.info(f"页面已无更多数据，停止滚动")
                        break
                else:
                    scroll_attempts = 0
                    logger.info(f"已获取 {current_count}/{target_count} 个交易对")
                    last_count = current_count

            logger.info(f"爬取完成，共获取 {len(tokens)} 个交易对（含完整数据）")
            return tokens

        finally:
            driver.quit()

    def _parse_row_element(self, row_element, pair_address: str, url: str) -> Optional[Dict[str, Any]]:
        """
        使用CSS选择器解析DexScreener表格行元素

        Args:
            row_element: Selenium WebElement (a.ds-dex-table-row)
            pair_address: 交易对地址
            url: 交易对URL

        Returns:
            解析后的代币数据字典，失败返回None
        """
        try:
            # 辅助函数：安全获取文本
            def safe_get_text(selector: str) -> Optional[str]:
                try:
                    elem = row_element.find_element(By.CSS_SELECTOR, selector)
                    text = elem.text.strip()
                    return text if text else None
                except:
                    return None

            # 辅助函数：解析价格字符串（处理$、K、M、B后缀）
            def parse_price_string(s: Optional[str]) -> Optional[float]:
                if not s:
                    return None
                try:
                    s = s.replace('$', '').replace(',', '').strip()
                    if s.endswith('K'):
                        return float(s[:-1]) * 1_000
                    elif s.endswith('M'):
                        return float(s[:-1]) * 1_000_000
                    elif s.endswith('B'):
                        return float(s[:-1]) * 1_000_000_000
                    else:
                        return float(s)
                except:
                    return None

            # 辅助函数：解析百分比
            def parse_percent(s: Optional[str]) -> Optional[float]:
                if not s:
                    return None
                try:
                    return float(s.replace('%', '').strip())
                except:
                    return None

            # 提取各字段
            symbol = safe_get_text('.ds-dex-table-row-base-token-symbol')
            name = safe_get_text('.ds-dex-table-row-base-token-name')
            price_str = safe_get_text('.ds-dex-table-row-col-price')

            # 价格变化（多个时间段）
            change_5m = parse_percent(safe_get_text('.ds-dex-table-row-col-price-change-m5 .ds-change-perc'))
            change_1h = parse_percent(safe_get_text('.ds-dex-table-row-col-price-change-h1 .ds-change-perc'))
            change_6h = parse_percent(safe_get_text('.ds-dex-table-row-col-price-change-h6 .ds-change-perc'))
            change_24h = parse_percent(safe_get_text('.ds-dex-table-row-col-price-change-h24 .ds-change-perc'))

            # 流动性、成交量、市值
            liquidity_str = safe_get_text('.ds-dex-table-row-col-liquidity')
            volume_str = safe_get_text('.ds-dex-table-row-col-volume')
            market_cap_str = safe_get_text('.ds-dex-table-row-col-market-cap')

            # 交易数据
            txns_str = safe_get_text('.ds-dex-table-row-col-txns')

            # 解析数值
            price_usd = parse_price_string(price_str)
            liquidity_usd = parse_price_string(liquidity_str)
            volume_24h = parse_price_string(volume_str)
            market_cap = parse_price_string(market_cap_str)

            # 解析交易数
            txns_24h = None
            if txns_str:
                try:
                    txns_24h = int(txns_str.replace(',', '').strip())
                except:
                    pass

            # 如果缺少关键字段，返回None
            if not symbol or price_usd is None:
                logger.debug(f"缺少关键字段: symbol={symbol}, price={price_usd}")
                return None

            # 构造返回数据（与DexScreener API格式兼容）
            return {
                'chainId': 'bsc',
                'dexId': 'pancakeswap',  # BSC主要是PancakeSwap
                'pairAddress': pair_address,
                'url': url,
                'baseToken': {
                    'address': pair_address,  # 页面上没有token address，用pair address代替
                    'symbol': symbol,
                    'name': name or symbol
                },
                'quoteToken': {
                    'symbol': 'WBNB',  # BSC上大多数配对都是WBNB
                    'address': '0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c'
                },
                'priceUsd': str(price_usd),
                'priceChange': {
                    'm5': change_5m,
                    'h1': change_1h,
                    'h6': change_6h,
                    'h24': change_24h
                },
                'liquidity': {
                    'usd': liquidity_usd
                } if liquidity_usd else None,
                'volume': {
                    'h24': volume_24h
                } if volume_24h else None,
                'fdv': market_cap,  # FDV近似等于市值
                'marketCap': market_cap,
                'txns': {
                    'h24': {
                        'total': txns_24h
                    }
                } if txns_24h else None
            }

        except Exception as e:
            logger.debug(f"解析行元素时出错: {e}")
            return None

    @staticmethod
    def _parse_element_text(text: str, pair_address: str, url: str) -> Dict[str, Any]:
        """
        解析元素文本内容，提取代币信息

        文本格式示例:
        '#1\nV2\nFlōki\n/\nWBNB\nFlōki\n$0.006326\n21h\n109,759\n$44.0M\n17,731\n1.85%\n-3.30%\n-46.37%\n1,788%\n$632K\n$6.3M'

        对应字段:
        0: 排名 (#1)
        1: 标签 (V2)
        2: 代币符号1 (Flōki)
        3: 分隔符 (/)
        4: 配对符号 (WBNB)
        5: 代币名称 (Flōki)
        6: 价格 ($0.006326)
        7: 年龄 (21h)
        8: 交易数 (109,759)
        9: 24h交易量 ($44.0M)
        10: Makers (17,731)
        11: 5m变化 (1.85%)
        12: 1h变化 (-3.30%)
        13: 6h变化 (-46.37%)
        14: 24h变化 (1,788%)
        15: 流动性 ($632K)
        16: 市值 ($6.3M)
        """
        try:
            parts = text.split('\n')
            if len(parts) < 17:
                return None

            # 解析价格（移除$和逗号）
            def parse_price(s):
                return float(s.replace('$', '').replace(',', '').replace('K', '000').replace('M', '000000').replace('B', '000000000'))

            # 解析百分比
            def parse_percent(s):
                return float(s.replace('%', ''))

            # 解析年龄为时间戳（毫秒）
            def parse_age(age_str):
                """将年龄字符串（如21h, 5d, 2m）转换为pairCreatedAt时间戳"""
                from datetime import datetime, timedelta
                import re

                now = datetime.utcnow()
                match = re.match(r'(\d+)([smhd])', age_str)
                if not match:
                    return None

                value = int(match.group(1))
                unit = match.group(2)

                if unit == 's':  # 秒
                    delta = timedelta(seconds=value)
                elif unit == 'm':  # 分钟
                    delta = timedelta(minutes=value)
                elif unit == 'h':  # 小时
                    delta = timedelta(hours=value)
                elif unit == 'd':  # 天
                    delta = timedelta(days=value)
                else:
                    return None

                created_at = now - delta
                return int(created_at.timestamp() * 1000)

            # 使用固定地址作为占位符（页面上没有代币合约地址）
            # WBNB合约地址
            WBNB_ADDRESS = '0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c'

            return {
                'chainId': 'bsc',
                'dexId': 'pancakeswap',  # BSC上主要是PancakeSwap
                'pairAddress': pair_address,
                'url': url,
                'rank': parts[0].replace('#', ''),
                'labels': [parts[1]] if parts[1] else [],
                'baseToken': {
                    'address': pair_address,  # 使用pair_address作为占位符
                    'symbol': parts[2],
                    'name': parts[5]
                },
                'quoteToken': {
                    'address': WBNB_ADDRESS,  # 大多数交易对都是/WBNB
                    'symbol': parts[4]
                },
                'priceUsd': parts[6].replace('$', ''),
                'age': parts[7],
                'pairCreatedAt': parse_age(parts[7]),
                'txns': {
                    'h24': {
                        'total': int(parts[8].replace(',', ''))
                    }
                },
                'volume': {
                    'h24': parse_price(parts[9])
                },
                'makers': int(parts[10].replace(',', '')),
                'priceChange': {
                    'm5': parse_percent(parts[11]),
                    'h1': parse_percent(parts[12]),
                    'h6': parse_percent(parts[13]),
                    'h24': parse_percent(parts[14])
                },
                'liquidity': {
                    'usd': parse_price(parts[15])
                },
                'marketCap': parse_price(parts[16])
            }

        except Exception as e:
            logger.debug(f"解析文本失败: {e}, text={text[:100]}")
            return None

    # ==================== 数据过滤 ====================

    @staticmethod
    def filter_tokens_by_age(
        tokens: List[Dict[str, Any]],
        max_age_days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        按创建时间过滤代币，只保留指定天数内创建的代币

        Args:
            tokens: 代币数据列表
            max_age_days: 最大年龄（天数）

        Returns:
            过滤后的代币列表
        """
        if not tokens:
            return []

        cutoff_time = datetime.now() - timedelta(days=max_age_days)
        cutoff_timestamp = int(cutoff_time.timestamp() * 1000)  # 转换为毫秒

        filtered_tokens = []
        total = len(tokens)
        filtered_count = 0

        for token in tokens:
            pair_created_at = token.get('pairCreatedAt')

            if pair_created_at is None:
                # 没有创建时间的代币也保留
                filtered_tokens.append(token)
                logger.debug(f"代币 {token.get('baseToken', {}).get('symbol', 'N/A')} 没有创建时间，保留")
                continue

            # 比较时间戳
            if pair_created_at >= cutoff_timestamp:
                filtered_tokens.append(token)
            else:
                # 计算代币年龄
                created_time = datetime.fromtimestamp(pair_created_at / 1000)
                age_days = (datetime.now() - created_time).days
                symbol = token.get('baseToken', {}).get('symbol', 'N/A')
                logger.debug(f"过滤掉代币 {symbol}，创建于 {created_time.strftime('%Y-%m-%d')} ({age_days}天前)")
                filtered_count += 1

        logger.info(f"按年龄过滤: 原始 {total} 个 -> 保留 {len(filtered_tokens)} 个 (过滤掉 {filtered_count} 个超过 {max_age_days} 天的代币)")
        return filtered_tokens

    @staticmethod
    def filter_tokens(
        tokens: List[Dict[str, Any]],
        filter_func: Callable[[Dict[str, Any]], bool]
    ) -> List[Dict[str, Any]]:
        """
        使用自定义过滤函数过滤代币

        Args:
            tokens: 代币数据列表
            filter_func: 过滤函数，接受代币数据，返回True表示保留

        Returns:
            过滤后的代币列表
        """
        filtered = [t for t in tokens if filter_func(t)]
        logger.info(f"自定义过滤: {len(tokens)} -> {len(filtered)}")
        return filtered

    # ==================== 数据解析 ====================

    @staticmethod
    def parse_token_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析原始DexScreener代币数据

        Args:
            raw_data: 原始代币数据

        Returns:
            解析后的数据字典
        """
        base_token = raw_data.get("baseToken", {})
        quote_token = raw_data.get("quoteToken", {})
        txns = raw_data.get("txns", {})
        volume = raw_data.get("volume", {})
        price_change = raw_data.get("priceChange", {})
        liquidity = raw_data.get("liquidity", {})
        info = raw_data.get("info", {})

        # 提取社交链接
        websites = info.get("websites", [])
        socials = info.get("socials", [])

        website_url = websites[0].get("url") if websites else None
        twitter_url = None
        telegram_url = None

        for social in socials:
            if social.get("type") == "twitter":
                twitter_url = social.get("url")
            elif social.get("type") == "telegram":
                telegram_url = social.get("url")

        # 解析标签
        labels_list = raw_data.get("labels", [])
        labels_str = ",".join(labels_list) if labels_list else None

        return {
            "chain_id": raw_data.get("chainId"),
            "dex_id": raw_data.get("dexId"),
            "pair_address": raw_data.get("pairAddress"),
            "base_token_address": base_token.get("address"),
            "base_token_name": base_token.get("name"),
            "base_token_symbol": base_token.get("symbol"),
            "quote_token_address": quote_token.get("address"),
            "quote_token_name": quote_token.get("name"),
            "quote_token_symbol": quote_token.get("symbol"),
            "price_native": raw_data.get("priceNative"),
            "price_usd": raw_data.get("priceUsd"),
            "volume_m5": volume.get("m5"),
            "volume_h1": volume.get("h1"),
            "volume_h6": volume.get("h6"),
            "volume_h24": volume.get("h24"),
            "txns_m5_buys": txns.get("m5", {}).get("buys"),
            "txns_m5_sells": txns.get("m5", {}).get("sells"),
            "txns_h1_buys": txns.get("h1", {}).get("buys"),
            "txns_h1_sells": txns.get("h1", {}).get("sells"),
            "txns_h6_buys": txns.get("h6", {}).get("buys"),
            "txns_h6_sells": txns.get("h6", {}).get("sells"),
            "txns_h24_buys": txns.get("h24", {}).get("buys"),
            "txns_h24_sells": txns.get("h24", {}).get("sells"),
            "price_change_h1": price_change.get("h1"),
            "price_change_h6": price_change.get("h6"),
            "price_change_h24": price_change.get("h24"),
            "liquidity_usd": liquidity.get("usd"),
            "liquidity_base": liquidity.get("base"),
            "liquidity_quote": liquidity.get("quote"),
            "fdv": raw_data.get("fdv"),
            "market_cap": raw_data.get("marketCap"),
            "pair_created_at": raw_data.get("pairCreatedAt"),
            "image_url": info.get("imageUrl"),
            "website_url": website_url,
            "twitter_url": twitter_url,
            "telegram_url": telegram_url,
            "dexscreener_url": raw_data.get("url"),
            "labels": labels_str,
        }

    # ==================== 数据库操作 ====================

    async def import_tokens(
        self,
        tokens_data: List[Dict[str, Any]],
        update_existing: bool = True
    ) -> Dict[str, int]:
        """
        导入代币数据到数据库

        Args:
            tokens_data: 代币数据列表
            update_existing: 是否更新已存在的记录

        Returns:
            统计信息字典 {"inserted": int, "updated": int, "errors": int}
        """
        await self._ensure_db()

        logger.info(f"开始导入 {len(tokens_data)} 个代币到数据库")

        inserted_count = 0
        updated_count = 0
        error_count = 0

        async with self.db_manager.get_session() as session:
            for idx, raw_token in enumerate(tokens_data, 1):
                try:
                    # 解析数据
                    parsed_data = self.parse_token_data(raw_token)
                    pair_address = parsed_data.get("pair_address")

                    if not pair_address:
                        logger.warning(f"Token {idx}: 缺少交易对地址，跳过")
                        error_count += 1
                        continue

                    # 检查是否已存在
                    result = await session.execute(
                        select(DexScreenerToken).where(
                            DexScreenerToken.pair_address == pair_address
                        )
                    )
                    existing_token = result.scalar_one_or_none()

                    if existing_token and update_existing:
                        # 更新现有记录
                        for key, value in parsed_data.items():
                            if key != 'pair_address':
                                setattr(existing_token, key, value)
                        existing_token.updated_at = datetime.utcnow()
                        updated_count += 1
                        logger.debug(f"[{idx}/{len(tokens_data)}] 更新: {parsed_data.get('base_token_symbol')}")
                    elif not existing_token:
                        # 插入新记录
                        token = DexScreenerToken(**parsed_data)
                        session.add(token)
                        inserted_count += 1
                        logger.info(f"[{idx}/{len(tokens_data)}] 插入: {parsed_data.get('base_token_symbol')}")

                    # 每10条提交一次
                    if idx % 10 == 0:
                        await session.commit()
                        logger.info(f"进度: {idx}/{len(tokens_data)}")

                except Exception as e:
                    logger.error(f"处理代币 {idx} 时出错: {e}")
                    error_count += 1

            # 最终提交
            await session.commit()

        stats = {
            "inserted": inserted_count,
            "updated": updated_count,
            "errors": error_count
        }

        logger.info(f"导入完成 - 插入: {inserted_count}, 更新: {updated_count}, 错误: {error_count}")
        return stats

    async def import_from_json(
        self,
        json_file_path: str,
        update_existing: bool = True
    ) -> Dict[str, int]:
        """
        从JSON文件导入代币数据

        Args:
            json_file_path: JSON文件路径
            update_existing: 是否更新已存在的记录

        Returns:
            统计信息字典
        """
        logger.info(f"从JSON文件导入: {json_file_path}")

        with open(json_file_path, 'r', encoding='utf-8') as f:
            tokens_data = json.load(f)

        return await self.import_tokens(tokens_data, update_existing)

    async def deduplicate_tokens(
        self,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        去重代币数据，每个代币只保留流动性最大的交易对

        Args:
            dry_run: 如果为True，只返回将要删除的记录，不实际删除

        Returns:
            去重统计信息
        """
        await self._ensure_db()

        logger.info("开始分析重复代币...")

        async with self.db_manager.get_session() as session:
            # 查找重复代币
            find_duplicates_query = text("""
                SELECT
                    base_token_address,
                    base_token_symbol,
                    base_token_name,
                    COUNT(*) as pair_count
                FROM dexscreener_tokens
                GROUP BY base_token_address, base_token_symbol, base_token_name
                HAVING COUNT(*) > 1
            """)

            result = await session.execute(find_duplicates_query)
            duplicate_tokens = result.fetchall()

            logger.info(f"找到 {len(duplicate_tokens)} 个有重复交易对的代币")

            to_delete = []
            duplicate_info = []

            for token_addr, symbol, name, count in duplicate_tokens:
                # 查找该代币的所有交易对
                find_pairs_query = text("""
                    SELECT
                        id,
                        pair_address,
                        dex_id,
                        liquidity_usd,
                        volume_h24
                    FROM dexscreener_tokens
                    WHERE base_token_address = :token_addr
                    ORDER BY
                        COALESCE(liquidity_usd, 0) DESC,
                        COALESCE(volume_h24, 0) DESC
                """)

                result = await session.execute(find_pairs_query, {"token_addr": token_addr})
                pairs = result.fetchall()

                # 保留第一个（流动性最大），删除其余
                keep_pair = pairs[0]
                delete_pairs = pairs[1:]

                duplicate_info.append({
                    "token_symbol": symbol,
                    "token_name": name,
                    "total_pairs": count,
                    "keep": {
                        "pair_address": keep_pair[1],
                        "dex_id": keep_pair[2],
                        "liquidity_usd": float(keep_pair[3]) if keep_pair[3] else 0
                    },
                    "delete": [
                        {
                            "pair_address": p[1],
                            "dex_id": p[2],
                            "liquidity_usd": float(p[3]) if p[3] else 0
                        }
                        for p in delete_pairs
                    ]
                })

                to_delete.extend([p[0] for p in delete_pairs])

            stats = {
                "duplicate_tokens_count": len(duplicate_tokens),
                "pairs_to_delete": len(to_delete),
                "duplicate_info": duplicate_info
            }

            if not dry_run and to_delete:
                # 执行删除
                delete_query = text("""
                    DELETE FROM dexscreener_tokens
                    WHERE id = ANY(:ids)
                """)

                await session.execute(delete_query, {"ids": to_delete})
                await session.commit()

                logger.info(f"✓ 已删除 {len(to_delete)} 条重复记录")

                # 验证结果
                verify_query = text("SELECT COUNT(*) FROM dexscreener_tokens")
                result = await session.execute(verify_query)
                remaining = result.scalar()

                stats["remaining_records"] = remaining
                stats["deleted"] = True
            else:
                logger.info(f"[预览模式] 将删除 {len(to_delete)} 条记录")
                stats["deleted"] = False

            return stats

    async def get_token_count(self) -> int:
        """获取数据库中的代币数量"""
        await self._ensure_db()

        async with self.db_manager.get_session() as session:
            result = await session.execute(
                text("SELECT COUNT(*) FROM dexscreener_tokens")
            )
            return result.scalar()

    # ==================== 一键操作 ====================

    async def scrape_and_import(
        self,
        target_count: int = 100,
        headless: bool = True,
        deduplicate: bool = True,
        save_json: bool = True,
        json_path: str = "/tmp/dexscreener_tokens.json",
        filter_old_tokens: bool = True,
        max_age_days: int = 30
    ) -> Dict[str, Any]:
        """
        一键完成：爬取 -> 过滤 -> 导入 -> 去重

        Args:
            target_count: 目标交易对数量
            headless: 是否使用无头模式
            deduplicate: 是否执行去重
            save_json: 是否保存JSON文件
            json_path: JSON文件保存路径
            filter_old_tokens: 是否过滤掉旧代币（默认True）
            max_age_days: 代币最大年龄（天数），超过此时间的代币会被过滤（默认30天）

        Returns:
            操作统计信息
        """
        logger.info("=" * 80)
        logger.info("开始一键爬取并导入DexScreener数据")
        logger.info("=" * 80)

        result = {
            "success": False,
            "steps": {}
        }

        try:
            # 步骤1: 爬取数据
            logger.info("\n[步骤 1/4] 爬取页面数据...")
            tokens_data = self.scrape_and_fetch(
                target_count=target_count,
                output_file=json_path if save_json else None,
                headless=headless,
                filter_old_tokens=filter_old_tokens,
                max_age_days=max_age_days
            )
            result["steps"]["scrape"] = {
                "tokens_found": len(tokens_data)
            }

            if not tokens_data:
                logger.error("爬取失败，未获取到数据")
                return result

            # 步骤2: 导入数据库
            logger.info("\n[步骤 2/4] 导入到数据库...")
            import_stats = await self.import_tokens(tokens_data)
            result["steps"]["import"] = import_stats

            # 步骤3: 去重（可选）
            if deduplicate:
                logger.info("\n[步骤 3/4] 执行去重...")
                dedup_stats = await self.deduplicate_tokens(dry_run=False)
                result["steps"]["deduplicate"] = dedup_stats
            else:
                logger.info("\n[步骤 3/4] 跳过去重")
                result["steps"]["deduplicate"] = {"skipped": True}

            # 获取最终记录数
            final_count = await self.get_token_count()
            result["final_count"] = final_count
            result["success"] = True

            logger.info("\n" + "=" * 80)
            logger.info("✓ 一键操作完成！")
            logger.info(f"  爬取: {len(tokens_data)} 个交易对")
            if filter_old_tokens:
                logger.info(f"  过滤: 只保留 {max_age_days} 天内创建的代币")
            logger.info(f"  导入: {import_stats['inserted']} 插入, {import_stats['updated']} 更新")
            if deduplicate:
                logger.info(f"  去重: 删除 {dedup_stats.get('pairs_to_delete', 0)} 条重复")
            logger.info(f"  最终: {final_count} 条记录")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"操作失败: {e}")
            result["error"] = str(e)

    # ==================== CloudScraper 方法（新，替代 Selenium）====================

    def _parse_value_with_unit(self, text: str) -> float:
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

    def _parse_token_row(self, row_element, rank: int, chain: str) -> Dict[str, Any]:
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
            percent_positions = []
            for i, part in enumerate(parts):
                if '%' in part and part != '%':
                    try:
                        # 去除 %、+、逗号并转换为浮点数
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
                        dollar_values.append(self._parse_value_with_unit(next_part))

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
            logger.debug(f"解析第 {rank} 行时出错: {e}")

        return token_data

    def scrape_with_cloudscraper(
        self,
        chain: str = 'bsc',
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        使用 cloudscraper 爬取 DexScreener（替代 Selenium）

        优势:
        - 无需启动浏览器，速度快
        - 资源占用少
        - 成功绕过 Cloudflare
        - 适合服务器定时任务

        Args:
            chain: 链名称 (bsc, solana)
            limit: 最多获取多少个代币

        Returns:
            代币列表，每个包含: pair_address, token_symbol, token_name, price_usd,
            price_change_24h, market_cap, liquidity_usd等字段
        """
        logger.info(f"使用 cloudscraper 爬取 {chain.upper()} 链...")

        # 创建 cloudscraper 实例
        scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'darwin', 'mobile': False, 'desktop': True},
            delay=10,
        )

        # 关键：必须包含这些 Sec-Fetch-* 头才能绕过 Cloudflare
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

        try:
            response = scraper.get(url, headers=headers, timeout=30)
        except Exception as e:
            logger.error(f"请求失败: {e}")
            return []

        if response.status_code != 200:
            logger.error(f"状态码: {response.status_code}")
            return []

        if '请稍候' in response.text or 'Just a moment' in response.text:
            logger.error("被 Cloudflare 拦截")
            return []

        logger.debug(f"响应大小: {len(response.text):,} 字符")

        # 解析 HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        token_rows = soup.select('a.ds-dex-table-row')

        if not token_rows:
            logger.warning("未找到代币行")
            return []

        logger.info(f"找到 {len(token_rows)} 个代币行")

        # 提取代币数据
        tokens = []
        for i, row in enumerate(token_rows[:limit], 1):
            token_data = self._parse_token_row(row, i, chain)
            if token_data:
                tokens.append(token_data)

        logger.info(f"成功提取 {len(tokens)} 个代币")

        return tokens


# ==================== 便捷函数 ====================

async def quick_scrape_and_import(
    target_count: int = 100,
    headless: bool = True,
    deduplicate: bool = True,
    filter_old_tokens: bool = True,
    max_age_days: int = 30
) -> Dict[str, Any]:
    """
    快速函数：一键爬取并导入

    Args:
        target_count: 目标数量
        headless: 无头模式
        deduplicate: 是否去重
        filter_old_tokens: 是否过滤掉旧代币（默认True）
        max_age_days: 代币最大年龄（天数），默认30天

    Returns:
        操作结果
    """
    service = DexScreenerService()
    try:
        result = await service.scrape_and_import(
            target_count=target_count,
            headless=headless,
            deduplicate=deduplicate,
            filter_old_tokens=filter_old_tokens,
            max_age_days=max_age_days
        )
        return result
    finally:
        await service.close()


