"""
AVE API Service
用于调用AVE API获取详细的代币和交易对信息
"""

import os
import requests
from typing import Dict, Optional, Any
from datetime import datetime
from decimal import Decimal
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


class AveApiService:
    """AVE API服务类"""

    BASE_URL = "https://prod.ave-api.com/v2"

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化AVE API服务

        Args:
            api_key: AVE API密钥，如果不提供则从环境变量AVE_API_KEY读取
        """
        self.api_key = api_key or os.getenv("AVE_API_KEY")

    def _get_headers(self) -> Dict[str, str]:
        """
        获取请求头，并验证API密钥

        Returns:
            包含API密钥的请求头

        Raises:
            ValueError: 如果API密钥未设置
        """
        if not self.api_key:
            raise ValueError(
                "AVE_API_KEY is required. Please set it in .env file or pass as parameter when initializing AveApiService."
            )

        return {
            'X-API-KEY': self.api_key,
            'Content-Type': 'application/json'
        }

    def get_pair_detail(self, pair_address: str, chain: str = "bsc") -> Optional[Dict[str, Any]]:
        """
        获取交易对详细信息

        Args:
            pair_address: 交易对地址
            chain: 链名称，默认bsc

        Returns:
            交易对详细数据，失败返回None
        """
        # AVE API格式: {pair_address}-{chain}
        pair_id = f"{pair_address}-{chain}"
        url = f"{self.BASE_URL}/pairs/{pair_id}"

        try:
            response = requests.get(url, headers=self._get_headers(), timeout=10)

            if response.status_code == 200:
                data = response.json()
                # 不再打印每次成功，由调用方汇总
                return data
            else:
                logger.warning(f"获取交易对详情失败: {pair_address}, 状态码: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"AVE API调用异常: {pair_address}, 错误: {e}")
            return None

    def parse_pair_data(self, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        解析AVE API返回的交易对数据

        Args:
            raw_data: AVE API原始响应数据

        Returns:
            解析后的结构化数据，如果 pair 不存在返回 None
        """
        if not raw_data or 'data' not in raw_data:
            return None

        data = raw_data.get('data', {})

        # 检查 data 是否为空（pair not found）
        if not data or not data.get('pair'):
            logger.warning("Pair not found or data is empty")
            return None

        # 获取链类型，判断是否需要转小写
        # EVM 链（bsc, eth, polygon 等）地址不区分大小写，统一转小写
        # Solana 链地址使用 Base58 编码，区分大小写，不能转小写
        chain = data.get('chain', 'bsc').lower()
        is_evm_chain = chain in ['bsc', 'eth', 'ethereum', 'polygon', 'matic', 'arbitrum', 'optimism', 'avalanche', 'base']

        # 判断哪个是目标代币（使用target_token字段）
        # 只对 EVM 链转小写，Solana 保持原样
        if is_evm_chain:
            target_token = data.get('target_token', '').lower()
            token0_address = data.get('token0_address', '').lower()
            token1_address = data.get('token1_address', '').lower()
        else:
            target_token = data.get('target_token', '')
            token0_address = data.get('token0_address', '')
            token1_address = data.get('token1_address', '')

        # 根据target_token确定使用哪个价格
        if target_token == token0_address:
            # 目标代币是token0
            token_address = token0_address
            token_price_usd = data.get('token0_price_usd')
            quote_token_address = token1_address
        else:
            # 目标代币是token1（默认情况）
            token_address = token1_address
            token_price_usd = data.get('token1_price_usd')
            quote_token_address = token0_address

        # 根据target_token确定代币名称和符号
        if target_token == token0_address:
            token_symbol = data.get('token0_symbol')
            token_name = data.get('token0_name') or data.get('token0_symbol')  # fallback to symbol
            quote_token_symbol = data.get('token1_symbol')
        else:
            token_symbol = data.get('token1_symbol')
            token_name = data.get('token1_name') or data.get('token1_symbol')  # fallback to symbol
            quote_token_symbol = data.get('token0_symbol')

        # 提取基础信息
        parsed = {
            # Token地址
            'token_address': token_address,
            'quote_token_address': quote_token_address,

            # Token信息
            'token_symbol': token_symbol,
            'token_name': token_name,
            'quote_token_symbol': quote_token_symbol,

            # AMM类型
            'amm': data.get('amm'),  # cakev2, etc.

            # 当前价格（目标代币的USD价格）
            'current_price_usd': self._safe_decimal(token_price_usd),

            # 历史最高价 (从区块链历史数据)
            'price_ath_usd': self._safe_decimal(data.get('price_ath_u')),

            # 市场数据
            'current_tvl': self._safe_decimal(data.get('tvl')),
            'current_market_cap': self._safe_decimal(data.get('market_cap') or data.get('fdv')),

            # Token创建信息
            'token_created_at': self._parse_timestamp(data.get('first_trade_at')),
            'first_trade_at': self._parse_timestamp(data.get('first_trade_at')),
            'creation_block_number': data.get('creation_block_number'),
            'creation_tx_hash': data.get('creation_tx_hash'),
        }

        # 提取价格变化数据 (AVE API直接提供字段)
        parsed['price_change_1m'] = self._safe_decimal(data.get('price_change_1m'))
        parsed['price_change_5m'] = self._safe_decimal(data.get('price_change_5m'))
        parsed['price_change_15m'] = self._safe_decimal(data.get('price_change_15m'))
        parsed['price_change_30m'] = self._safe_decimal(data.get('price_change_30m'))
        parsed['price_change_1h'] = self._safe_decimal(data.get('price_change_1h'))
        parsed['price_change_4h'] = self._safe_decimal(data.get('price_change_4h'))
        parsed['price_change_24h'] = self._safe_decimal(data.get('price_change_1d'))  # Note: AVE uses 1d for 24h

        # 提取交易量数据 (AVE API格式: volume_u_1m, volume_u_5m, etc.)
        parsed['volume_1m'] = self._safe_decimal(data.get('volume_u_1m'))
        parsed['volume_5m'] = self._safe_decimal(data.get('volume_u_5m'))
        parsed['volume_15m'] = self._safe_decimal(data.get('volume_u_15m'))
        parsed['volume_30m'] = self._safe_decimal(data.get('volume_u_30m'))
        parsed['volume_1h'] = self._safe_decimal(data.get('volume_u_1h'))
        parsed['volume_4h'] = self._safe_decimal(data.get('volume_u_4h'))
        parsed['volume_24h'] = self._safe_decimal(data.get('volume_u_24h'))

        # 提取交易次数数据 (AVE API格式: tx_1m_count, tx_5m_count, etc.)
        parsed['tx_count_1m'] = data.get('tx_1m_count')
        parsed['tx_count_5m'] = data.get('tx_5m_count')
        parsed['tx_count_15m'] = data.get('tx_15m_count')
        parsed['tx_count_30m'] = data.get('tx_30m_count')
        parsed['tx_count_1h'] = data.get('tx_1h_count')
        parsed['tx_count_4h'] = data.get('tx_4h_count')
        parsed['tx_count_24h'] = data.get('tx_24h_count')

        # 24小时买卖数据
        parsed['buys_24h'] = data.get('buys_tx_24h_count')
        parsed['sells_24h'] = data.get('sells_tx_24h_count')

        # 交易者数据
        parsed['makers_24h'] = data.get('makers_24h')
        parsed['buyers_24h'] = data.get('buyers_24h')
        parsed['sellers_24h'] = data.get('sellers_24h')

        # 24小时价格范围
        parsed['price_24h_high'] = self._safe_decimal(data.get('high_u'))
        parsed['price_24h_low'] = self._safe_decimal(data.get('low_u'))
        parsed['open_price_24h'] = self._safe_decimal(data.get('open_price'))

        # LP信息
        parsed['lp_holders'] = data.get('lp_holders')
        parsed['lp_locked_percent'] = self._safe_decimal(data.get('lp_locked_percent'))
        parsed['lp_lock_platform'] = data.get('lp_lock_platform')

        # 早期交易指标
        parsed['rusher_tx_count'] = data.get('rusher_tx_count')
        parsed['sniper_tx_count'] = data.get('sniper_tx_count')

        return parsed

    def _safe_decimal(self, value) -> Optional[Decimal]:
        """安全转换为Decimal"""
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except:
            return None

    def _parse_timestamp(self, timestamp) -> Optional[datetime]:
        """解析时间戳"""
        if not timestamp:
            return None
        try:
            # AVE API返回的是Unix时间戳（秒）
            return datetime.fromtimestamp(int(timestamp))
        except:
            return None

    def get_pair_detail_parsed(self, pair_address: str, chain: str = "bsc") -> Optional[Dict[str, Any]]:
        """
        获取并解析交易对详细信息（一步到位）

        Args:
            pair_address: 交易对地址
            chain: 链名称，默认bsc

        Returns:
            解析后的结构化数据，失败返回None
        """
        raw_data = self.get_pair_detail(pair_address, chain)
        if not raw_data:
            return None

        return self.parse_pair_data(raw_data)


# 单例实例
ave_api_service = AveApiService()
