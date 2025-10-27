#!/usr/bin/env python3
"""
K线更新功能测试脚本
测试使用 GeckoTerminal API 拉取K线数据
"""

import asyncio
import sys
from src.services.kline_service import KlineService
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


async def test_single_token():
    """测试单个代币K线更新"""
    print("=" * 80)
    print("测试 1: 单个代币K线更新")
    print("=" * 80)

    service = KlineService()

    try:
        # 使用一个测试代币（WBNB）
        token_address = "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c"
        pair_address = "0x172fcd41e0913e95784454622d1c3724f546f849"  # WBNB/USDT pair

        print(f"\n测试代币: {token_address}")
        print(f"交易对: {pair_address}")
        print(f"拉取 5 分钟 K线，最多 500 根\n")

        # 更新K线
        result = await service.update_token_klines(
            token_address=token_address,
            pair_address=pair_address,
            chain="bsc",
            timeframe="minute",
            aggregate=5,
            max_candles=500
        )

        print("\n" + "=" * 80)
        print("测试结果:")
        print("=" * 80)
        print(f"成功: {result['success']}")
        print(f"拉取K线数: {result['fetched']}")
        print(f"保存K线数: {result['saved']}")
        print(f"跳过K线数: {result['skipped']}")
        print(f"增量更新: {result['is_incremental']}")
        if result['error']:
            print(f"错误: {result['error']}")

        print("\n" + "=" * 80)
        print("✅ 测试完成！")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await service.close()


async def test_monitored_tokens():
    """测试批量更新监控代币K线"""
    print("\n\n" + "=" * 80)
    print("测试 2: 批量更新监控代币K线")
    print("=" * 80)

    service = KlineService()

    try:
        print(f"\n拉取 5 分钟 K线，首次最多 500 根\n")

        # 批量更新监控代币
        result = await service.update_monitored_tokens_klines(
            timeframe="minute",
            aggregate=5,
            max_candles=500,
            delay=0.5  # 每个代币延迟0.5秒
        )

        print("\n" + "=" * 80)
        print("测试结果:")
        print("=" * 80)
        print(f"总代币数: {result['total']}")
        print(f"成功: {result['success']}")
        print(f"失败: {result['failed']}")
        print(f"总拉取K线数: {result['total_fetched']}")
        print(f"总保存K线数: {result['total_saved']}")

        print("\n" + "=" * 80)
        print("✅ 测试完成！")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await service.close()


async def test_potential_tokens():
    """测试批量更新潜力代币K线"""
    print("\n\n" + "=" * 80)
    print("测试 3: 批量更新潜力代币K线")
    print("=" * 80)

    service = KlineService()

    try:
        print(f"\n拉取 5 分钟 K线，首次最多 500 根\n")

        # 批量更新潜力代币
        result = await service.update_potential_tokens_klines(
            timeframe="minute",
            aggregate=5,
            max_candles=500,
            delay=0.5  # 每个代币延迟0.5秒
        )

        print("\n" + "=" * 80)
        print("测试结果:")
        print("=" * 80)
        print(f"总代币数: {result['total']}")
        print(f"成功: {result['success']}")
        print(f"失败: {result['failed']}")
        print(f"总拉取K线数: {result['total_fetched']}")
        print(f"总保存K线数: {result['total_saved']}")

        print("\n" + "=" * 80)
        print("✅ 测试完成！")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await service.close()


async def test_all_tokens():
    """测试统一更新所有代币K线（推荐使用）"""
    print("\n\n" + "=" * 80)
    print("测试 4: 统一更新所有代币K线（内部自动限流）")
    print("=" * 80)

    service = KlineService()

    try:
        print(f"\n拉取 5 分钟 K线，首次最多 500 根")
        print(f"内部自动限流: 2.5秒/请求，确保不超过 30 req/min\n")

        # 统一更新所有代币（监控 + 潜力）
        result = await service.update_all_tokens_klines(
            timeframe="minute",
            aggregate=5,
            max_candles=500
        )

        print("\n" + "=" * 80)
        print("测试结果:")
        print("=" * 80)
        print(f"监控代币: {result['monitored']}")
        print(f"潜力代币: {result['potential']}")
        print(f"总代币数: {result['total']}")
        print(f"成功: {result['success']}")
        print(f"失败: {result['failed']}")
        print(f"总拉取K线数: {result['total_fetched']}")
        print(f"总保存K线数: {result['total_saved']}")

        print("\n" + "=" * 80)
        print("✅ 测试完成！")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await service.close()


async def main():
    """主测试函数"""
    print("\n")
    print("=" * 80)
    print("K线更新功能测试")
    print("使用 GeckoTerminal API")
    print("=" * 80)

    # 选择测试模式
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        if mode == "single":
            await test_single_token()
        elif mode == "monitored":
            await test_monitored_tokens()
        elif mode == "potential":
            await test_potential_tokens()
        elif mode == "all":
            await test_all_tokens()
        else:
            print(f"未知模式: {mode}")
            print("可用模式: single | monitored | potential | all")
    else:
        # 默认运行统一更新测试（推荐）
        await test_all_tokens()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️ 测试被用户中断")
    except Exception as e:
        print(f"\n\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
