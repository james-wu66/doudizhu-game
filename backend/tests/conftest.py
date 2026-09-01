# conftest.py — pytest 自动加载
import sys, os
# 确保 tests/ 目录本身在 sys.path 中，以便 import helpers
sys.path.insert(0, os.path.dirname(__file__))
