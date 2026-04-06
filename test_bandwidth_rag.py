"""Test script for bandwidth RAG implementation.

This script tests the bandwidth policy RAG without needing to run
the full DeerFlow stack.

Usage:
    cd /Users/matthewyin/Coding/docker/deer-flow
    PYTHONPATH=backend/packages/harness python test_bandwidth_rag.py
"""

import asyncio
import sys
from pathlib import Path

# Add the backend package to path
sys.path.insert(0, str(Path(__file__).parent / "backend" / "packages" / "harness"))

def test_imports():
    """Test that all modules can be imported."""
    print("=" * 60)
    print("Test 0: Module Imports")
    print("=" * 60)
    
    try:
        from deerflow.rag import BandwidthRAG, get_bandwidth_rag
        print("✓ Successfully imported BandwidthRAG")
        
        from deerflow.tools.bandwidth_tool import bandwidth_policy_query
        print("✓ Successfully imported bandwidth_policy_query")
        
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_rag_initialization():
    """Test RAG initialization."""
    print("=" * 60)
    print("Test 1: RAG Initialization")
    print("=" * 60)

    from deerflow.rag import BandwidthRAG
    
    rag = BandwidthRAG()
    rag.initialize()

    print(f"✓ Vector store initialized at: {rag.persist_dir}")
    print(f"✓ Ollama base URL: {rag.ollama_base_url}")
    print()


def test_bandwidth_query():
    """Test bandwidth policy query."""
    print("=" * 60)
    print("Test 2: Bandwidth Policy Query")
    print("=" * 60)

    from deerflow.rag import BandwidthRAG
    
    rag = BandwidthRAG()
    rag.initialize()

    # Test queries
    test_cases = [
        {"current_bw": "10 Mbps", "current_traffic": 5.0, "desc": "10M带宽，5Mbps流量（应扩容）"},
        {"current_bw": "10 Mbps", "current_traffic": 2.0, "desc": "10M带宽，2Mbps流量（应维持）"},
        {"current_bw": "4 Mbps", "current_traffic": 0.5, "desc": "4M带宽，0.5Mbps流量（应缩容）"},
        {"current_bw": "20 Mbps", "current_traffic": 9.0, "desc": "20M带宽，9Mbps流量（应扩容）"},
    ]

    for case in test_cases:
        print(f"\n测试: {case['desc']}")
        print(f"  输入: 当前带宽={case['current_bw']}, 流量={case['current_traffic']} Mbps")

        result = rag.get_recommendation(case["current_bw"], case["current_traffic"])

        print(f"  结果:")
        print(f"    - 建议操作: {result['action']}")
        print(f"    - 目标带宽: {result.get('target_bw', 'N/A')}")
        print(f"    - 说明: {result['reasoning']}")

    print()


def test_semantic_search():
    """Test semantic search."""
    print("=" * 60)
    print("Test 3: Semantic Search")
    print("=" * 60)

    from deerflow.rag import BandwidthRAG
    
    rag = BandwidthRAG()
    rag.initialize()

    # Test natural language queries
    queries = [
        "我当前10M带宽，流量很高应该怎么办",
        "4兆带宽流量很低需要降级吗",
        "什么时候需要从20M扩容到30M",
    ]

    for query in queries:
        print(f"\n查询: {query}")
        results = rag.query(query_text=query, k=2)

        print(f"  检索到 {len(results)} 条相关策略:")
        for i, r in enumerate(results, 1):
            print(f"    {i}. {r['current_bw']} (相关度: {r['relevance_score']})")
            print(f"       {r['description'][:60]}...")

    print()


async def test_tool():
    """Test the bandwidth policy tool."""
    print("=" * 60)
    print("Test 4: Bandwidth Policy Tool")
    print("=" * 60)

    from deerflow.tools.bandwidth_tool import bandwidth_policy_query

    # Test with structured params
    print("\n测试结构化参数:")
    result = await bandwidth_policy_query("10 Mbps", 5.0)
    print(f"  输入: 10 Mbps, 5.0 Mbps流量")
    print(f"  输出: action={result.action}, target={result.target_bw}")
    print(f"  说明: {result.reasoning}")

    # Test with natural language query
    print("\n测试自然语言查询:")
    result = await bandwidth_policy_query(query="当前20M带宽流量9Mbps应该怎么办")
    print(f"  输入: '当前20M带宽流量9Mbps应该怎么办'")
    print(f"  输出: action={result.action}, target={result.target_bw}")
    print(f"  说明: {result.reasoning}")

    print()


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Bandwidth RAG Test Suite")
    print("=" * 60 + "\n")

    try:
        # Test 0: Imports
        if not test_imports():
            sys.exit(1)

        # Test 1: Initialization
        test_rag_initialization()

        # Test 2: Query with recommendations
        test_bandwidth_query()

        # Test 3: Semantic search
        test_semantic_search()

        # Test 4: Tool integration (async)
        asyncio.run(test_tool())

        print("=" * 60)
        print("All tests passed! ✓")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
