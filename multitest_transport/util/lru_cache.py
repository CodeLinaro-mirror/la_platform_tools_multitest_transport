"""Least Recently Used (LRU) cache implementation."""

import collections
from typing import Any


class LRUCache:
  """Least Recently Used (LRU) cache implementation.

  This class implements a simple LRU cache with a fixed capacity. It allows
  storing key-value pairs and retrieving them in a least recently used order.
  When the cache reaches its capacity, the least recently used item is evicted.
  """

  def __init__(self, capacity: int):
    """Initialize a new LRUCache instance.

    Args:
      capacity: The maximum number of items that can be stored in the cache.
    """
    self.capacity = capacity
    self.cache = collections.OrderedDict()

  def get(self, key: str) -> Any:
    """Retrieve the value associated with the given key.

    Args:
      key: The key to retrieve the value for.

    Returns:
      The value associated with the key, or None if the key is not found.
    """
    if key not in self.cache:
      return None
    else:
      self.cache.move_to_end(key)
      return self.cache[key]

  def put(self, key: str, value: Any) -> None:
    """Store a key-value pair in the cache.

    Args:
      key: The key to associate with the value.
      value: The value to store.
    """
    if key in self.cache:
      self.cache.move_to_end(key)
    self.cache[key] = value
    if len(self.cache) > self.capacity:
      self.cache.popitem(last=False)
