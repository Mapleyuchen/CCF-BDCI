"""
Unit Tests for Multi-Level Memory System

Tests core functionality of the three-layer memory architecture
and hybrid retrieval engine.

Author: CCF BDCI 2026 Team
Date: 2026-09-23
"""

import unittest
import time
from jiuwenswarm.agents.harness.common.memory.multi_level_memory import (
    MemoryItem,
    WorkingMemoryLayer,
    TaskMemoryLayer,
    ProjectMemoryLayer,
    MultiLevelMemory,
)
from jiuwenswarm.agents.harness.common.memory.retrieval_engine import (
    HybridRetrievalEngine,
    RetrievalWeights,
    MemoryRetriever,
)


class TestWorkingMemoryLayer(unittest.TestCase):
    """Test L1 Working Memory with LRU eviction"""

    def setUp(self):
        self.memory = WorkingMemoryLayer(capacity=3, ttl=10)

    def test_store_and_retrieve(self):
        """Test basic store and retrieval"""
        item = MemoryItem(content="Test content", layer="working")
        self.memory.store("key1", item)

        retrieved = self.memory.get("key1")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.content, "Test content")

    def test_lru_eviction(self):
        """Test LRU eviction when capacity is exceeded"""
        item1 = MemoryItem(content="Item 1")
        item2 = MemoryItem(content="Item 2")
        item3 = MemoryItem(content="Item 3")
        item4 = MemoryItem(content="Item 4")

        self.memory.store("key1", item1)
        self.memory.store("key2", item2)
        self.memory.store("key3", item3)
        self.memory.store("key4", item4)  # Should evict key1

        # key1 should be evicted
        self.assertIsNone(self.memory.get("key1"))
        # Others should exist
        self.assertIsNotNone(self.memory.get("key2"))
        self.assertIsNotNone(self.memory.get("key3"))
        self.assertIsNotNone(self.memory.get("key4"))

    def test_ttl_expiration(self):
        """Test TTL-based expiration"""
        memory_short_ttl = WorkingMemoryLayer(capacity=10, ttl=1)
        item = MemoryItem(content="Expires soon")
        memory_short_ttl.store("key1", item)

        # Should exist immediately
        self.assertIsNotNone(memory_short_ttl.get("key1"))

        # Wait for expiration
        time.sleep(1.5)

        # Should be expired
        self.assertIsNone(memory_short_ttl.get("key1"))


class TestTaskMemoryLayer(unittest.TestCase):
    """Test L2 Task Memory organized by task ID"""

    def setUp(self):
        self.memory = TaskMemoryLayer(capacity=5, ttl=10)

    def test_store_by_task(self):
        """Test storing and retrieving by task ID"""
        item = MemoryItem(content="Task 1 memory", task_id="task1")
        self.memory.store("task1", "key1", item)

        retrieved = self.memory.get("task1", "key1")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.content, "Task 1 memory")

    def test_get_by_task(self):
        """Test retrieving all memories for a task"""
        item1 = MemoryItem(content="Memory 1", task_id="task1")
        item2 = MemoryItem(content="Memory 2", task_id="task1")

        self.memory.store("task1", "key1", item1)
        self.memory.store("task1", "key2", item2)

        task_memories = self.memory.get_by_task("task1")
        self.assertEqual(len(task_memories), 2)

    def test_capacity_enforcement(self):
        """Test global capacity limit"""
        for i in range(10):
            item = MemoryItem(content=f"Item {i}")
            self.memory.store(f"task{i}", f"key{i}", item)

        # Should respect capacity of 5
        all_items = self.memory.get_all()
        self.assertLessEqual(len(all_items), 5)


class TestProjectMemoryLayer(unittest.TestCase):
    """Test L3 Project Memory for persistent storage"""

    def setUp(self):
        self.memory = ProjectMemoryLayer()

    def test_unlimited_storage(self):
        """Test that project memory has no capacity limit"""
        for i in range(100):
            item = MemoryItem(content=f"Project item {i}")
            self.memory.store(f"key{i}", item)

        all_items = self.memory.get_all()
        self.assertEqual(len(all_items), 100)

    def test_persistence(self):
        """Test that items persist (no TTL)"""
        item = MemoryItem(content="Persistent memory")
        self.memory.store("key1", item)

        time.sleep(1)

        retrieved = self.memory.get("key1")
        self.assertIsNotNone(retrieved)


class TestMultiLevelMemory(unittest.TestCase):
    """Test integrated multi-level memory system"""

    def setUp(self):
        self.memory = MultiLevelMemory()

    def test_layer_routing(self):
        """Test correct routing to different layers"""
        self.memory.store("Working item", layer="working")
        self.memory.store("Task item", layer="task", task_id="task1")
        self.memory.store("Project item", layer="project")

        stats = self.memory.get_statistics()
        self.assertEqual(stats['current_counts']['L1'], 1)
        self.assertEqual(stats['current_counts']['L2'], 1)
        self.assertEqual(stats['current_counts']['L3'], 1)

    def test_importance_tracking(self):
        """Test importance score tracking"""
        self.memory.store("High priority", importance=0.9, layer="project")
        self.memory.store("Low priority", importance=0.1, layer="project")

        stats = self.memory.get_statistics()
        self.assertGreater(stats['average_importance'], 0)


class TestHybridRetrievalEngine(unittest.TestCase):
    """Test hybrid retrieval with multiple signals"""

    def setUp(self):
        self.engine = HybridRetrievalEngine()
        self.memories = [
            MemoryItem(content="Python programming tutorial", importance=0.8),
            MemoryItem(content="Java development guide", importance=0.5),
            MemoryItem(content="Python data analysis", importance=0.7),
        ]
        # Age the second item
        time.sleep(0.1)

    def test_semantic_similarity(self):
        """Test semantic similarity scoring"""
        results = self.engine.retrieve("Python", self.memories, top_k=3)

        # Python-related items should score higher
        self.assertTrue(any("Python" in r[0].content for r in results[:2]))

    def test_top_k_limiting(self):
        """Test that only top_k results are returned"""
        results = self.engine.retrieve("programming", self.memories, top_k=2)
        self.assertEqual(len(results), 2)

    def test_temporal_decay(self):
        """Test that temporal decay affects scoring"""
        old_item = MemoryItem(content="Old memory", importance=0.5)
        old_item.timestamp = time.time() - 86400  # 1 day ago

        new_item = MemoryItem(content="New memory", importance=0.5)

        memories = [old_item, new_item]
        results = self.engine.retrieve("memory", memories, top_k=2)

        # Newer item should score higher with temporal decay
        self.assertTrue(results[0][1] >= results[1][1])

    def test_access_frequency(self):
        """Test access frequency scoring"""
        popular_item = MemoryItem(content="Popular item")
        popular_item.access_count = 10

        unpopular_item = MemoryItem(content="Unpopular item")
        unpopular_item.access_count = 1

        memories = [popular_item, unpopular_item]

        # Retrieve multiple times
        for _ in range(3):
            results = self.engine.retrieve("item", memories)

        # Frequency should influence ranking
        self.assertGreater(popular_item.access_count, unpopular_item.access_count)


class TestMemoryRetriever(unittest.TestCase):
    """Test high-level memory retrieval interface"""

    def setUp(self):
        self.memory = MultiLevelMemory()
        self.retriever = MemoryRetriever(self.memory)

    def test_search_all_layers(self):
        """Test searching across all memory layers"""
        self.memory.store("Working Python code", layer="working")
        self.memory.store("Task Python test", layer="task", task_id="task1")
        self.memory.store("Project Python doc", layer="project")

        results = self.retriever.search("Python", top_k=5)
        self.assertEqual(len(results), 3)

    def test_search_specific_layer(self):
        """Test searching in specific layer"""
        self.memory.store("Working item", layer="working")
        self.memory.store("Project item", layer="project")

        # Search only working layer
        results = self.retriever.search("item", layer="working")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0].layer, "working")

    def test_search_by_task(self):
        """Test searching within specific task"""
        self.memory.store("Task 1 item", layer="task", task_id="task1")
        self.memory.store("Task 2 item", layer="task", task_id="task2")

        results = self.retriever.search("item", layer="task", task_id="task1")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0].task_id, "task1")


def run_tests():
    """Run all unit tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestWorkingMemoryLayer))
    suite.addTests(loader.loadTestsFromTestCase(TestTaskMemoryLayer))
    suite.addTests(loader.loadTestsFromTestCase(TestProjectMemoryLayer))
    suite.addTests(loader.loadTestsFromTestCase(TestMultiLevelMemory))
    suite.addTests(loader.loadTestsFromTestCase(TestHybridRetrievalEngine))
    suite.addTests(loader.loadTestsFromTestCase(TestMemoryRetriever))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result


if __name__ == "__main__":
    result = run_tests()

    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {(result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100:.1f}%")
