"""Tests for LRUCache.

These tests cover the basic functionality of the LRUCache class.
"""

import unittest
from multitest_transport.util import lru_cache


class TestLRUCache(unittest.TestCase):

  def test_empty_cache(self):
    cache = lru_cache.LRUCache(3)
    self.assertIsNone(cache.get("a"))

  def test_put_and_get(self):
    cache = lru_cache.LRUCache(3)
    cache.put("a", "apple")
    cache.put("b", "banana")
    self.assertEqual(cache.get("a"), "apple")
    self.assertEqual(cache.get("b"), "banana")

  def test_capacity_limit(self):
    cache = lru_cache.LRUCache(2)
    cache.put("a", "apple")
    cache.put("b", "banana")
    cache.put("c", "cherry")  # Exceeds capacity, should evict "a"
    self.assertIsNone(cache.get("a"))
    self.assertEqual(cache.get("b"), "banana")
    self.assertEqual(cache.get("c"), "cherry")

  def test_lru_eviction(self):
    cache = lru_cache.LRUCache(3)
    cache.put("a", "apple")
    cache.put("b", "banana")
    cache.put("c", "cherry")
    cache.get("a")  # Access "a", making it most recently used
    cache.put("d", "date")  # Exceeds capacity, should evict "b"
    self.assertEqual(cache.get("a"), "apple")
    self.assertIsNone(cache.get("b"))
    self.assertEqual(cache.get("c"), "cherry")
    self.assertEqual(cache.get("d"), "date")

  def test_update_value(self):
    cache = lru_cache.LRUCache(3)
    cache.put("a", "apple")
    cache.put("b", "banana")
    cache.put("a", "apricot")  # Update value for "a"
    self.assertEqual(cache.get("a"), "apricot")
    self.assertEqual(cache.get("b"), "banana")

  def test_get_nonexistent_key(self):
    cache = lru_cache.LRUCache(3)
    cache.put("a", "apple")
    self.assertIsNone(cache.get("z"))

  def test_capacity_one(self):
    cache = lru_cache.LRUCache(1)
    cache.put("a", "apple")
    cache.put("b", "banana")
    self.assertIsNone(cache.get("a"))
    self.assertEqual(cache.get("b"), "banana")

  def test_capacity_zero(self):
    cache = lru_cache.LRUCache(0)
    cache.put("a", "apple")
    self.assertIsNone(cache.get("a"))
