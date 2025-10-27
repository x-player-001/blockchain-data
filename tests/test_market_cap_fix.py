#!/usr/bin/env python3
"""
Test script to verify market_cap field fix
"""

from src.services.ave_api_service import ave_api_service

# Test pair address
pair_address = "0x172fcd41e0913e95784454622d1c3724f546f849"
chain = "bsc"

print("=" * 60)
print("Testing AVE API Market Cap Field Fix")
print("=" * 60)

# Get parsed data
parsed_data = ave_api_service.get_pair_detail_parsed(pair_address, chain)

if parsed_data:
    print(f"\n✅ Successfully parsed data:")
    print(f"   Token Symbol: {parsed_data.get('token_symbol')}")
    print(f"   Current Price: ${parsed_data.get('current_price_usd')}")
    print(f"   Current TVL: ${parsed_data.get('current_tvl')}")
    print(f"   Current Market Cap: ${parsed_data.get('current_market_cap')}")

    if parsed_data.get('current_market_cap'):
        print(f"\n✅ Market cap is now correctly populated!")
    else:
        print(f"\n❌ Market cap is still None")
else:
    print(f"\n❌ Failed to get pair data")

print("=" * 60)
