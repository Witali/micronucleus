#!/usr/bin/env python3
"""Compatibility entry point for the independent EP0 request/descriptor oracle."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tests35.test_ep0_standard import test as test_standard

if __name__=='__main__':test_standard()
