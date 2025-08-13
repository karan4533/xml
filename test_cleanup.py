#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test script to verify that the cleanup functionality is working correctly.
This script creates fake session directories and tests the cleanup logic.
"""

import os
import time
import json
from pathlib import Path
from pdf_to_universal_xml import _cleanup_old_sessions, _get_directory_size_mb

def create_test_session(output_dir: Path, session_id: str, age_hours: float = 0):
    """Create a test session directory with some files."""
    session_dir = output_dir / f"session_{session_id}"
    session_dir.mkdir(parents=True, exist_ok=True)
    
    # Create some dummy files
    (session_dir / "combined.xml").write_text("<document>test data</document>")
    (session_dir / "tables").mkdir(exist_ok=True)
    (session_dir / "tables" / "page_001_table_001.xml").write_text("<table>test</table>")
    (session_dir / "assets" / "images").mkdir(parents=True, exist_ok=True)
    (session_dir / "assets" / "images" / "page_001_img_001.png").write_bytes(b"fake image data")
    
    # Modify timestamp to simulate age
    if age_hours > 0:
        target_time = time.time() - (age_hours * 3600)
        os.utime(session_dir, (target_time, target_time))
    
    return session_dir

def main():
    print("🧪 Testing Cleanup Functionality")
    print("=" * 50)
    
    # Create test output directory
    test_dir = Path("test_output")
    test_dir.mkdir(exist_ok=True)
    
    try:
        # Clean up any existing test sessions
        if test_dir.exists():
            import shutil
            shutil.rmtree(test_dir)
        test_dir.mkdir()
        
        print("1. Creating test sessions...")
        
        # Create various test sessions
        sessions = [
            ("current", 0),      # Current session
            ("recent1", 12),     # 12 hours old
            ("recent2", 18),     # 18 hours old  
            ("old1", 30),        # 30 hours old (should be cleaned)
            ("old2", 48),        # 48 hours old (should be cleaned)
            ("old3", 72),        # 72 hours old (should be cleaned)
            ("old4", 96),        # 96 hours old (should be cleaned)
        ]
        
        for session_id, age in sessions:
            session_dir = create_test_session(test_dir, session_id, age)
            size_mb = _get_directory_size_mb(session_dir)
            print(f"   Created {session_dir.name} (age: {age}h, size: {size_mb:.3f} MB)")
        
        print(f"\n2. Initial state: {len(sessions)} sessions created")
        
        # Test 1: Cleanup with default settings (5 sessions max, 24h age limit)
        print("\n3. Testing cleanup with default settings (max 5 sessions, 24h age limit)...")
        cleanup_stats = _cleanup_old_sessions(test_dir, max_sessions=5, max_age_hours=24.0)
        
        print("   Cleanup Results:")
        print(f"   - Sessions found: {cleanup_stats['sessions_found']}")
        print(f"   - Sessions removed: {cleanup_stats['sessions_removed']}")
        print(f"   - Sessions kept: {cleanup_stats['sessions_kept']}")
        print(f"   - Space freed: {cleanup_stats['space_freed_mb']:.3f} MB")
        
        if cleanup_stats['cleanup_reason']:
            print("   - Cleanup reasons:")
            for reason in cleanup_stats['cleanup_reason']:
                print(f"     * {reason}")
        
        # Verify results
        remaining_sessions = [d for d in test_dir.iterdir() if d.is_dir() and d.name.startswith('session_')]
        print(f"\n4. Remaining sessions: {len(remaining_sessions)}")
        for session_dir in sorted(remaining_sessions):
            print(f"   - {session_dir.name}")
        
        # Test 2: More aggressive cleanup (3 sessions max, 12h age limit)
        print("\n5. Testing more aggressive cleanup (max 3 sessions, 12h age limit)...")
        cleanup_stats = _cleanup_old_sessions(test_dir, max_sessions=3, max_age_hours=12.0)
        
        print("   Cleanup Results:")
        print(f"   - Sessions found: {cleanup_stats['sessions_found']}")
        print(f"   - Sessions removed: {cleanup_stats['sessions_removed']}")
        print(f"   - Sessions kept: {cleanup_stats['sessions_kept']}")
        print(f"   - Space freed: {cleanup_stats['space_freed_mb']:.3f} MB")
        
        if cleanup_stats['cleanup_reason']:
            print("   - Cleanup reasons:")
            for reason in cleanup_stats['cleanup_reason']:
                print(f"     * {reason}")
        
        # Final state
        remaining_sessions = [d for d in test_dir.iterdir() if d.is_dir() and d.name.startswith('session_')]
        print(f"\n6. Final remaining sessions: {len(remaining_sessions)}")
        for session_dir in sorted(remaining_sessions):
            age_seconds = time.time() - session_dir.stat().st_mtime
            age_hours = age_seconds / 3600
            print(f"   - {session_dir.name} (age: {age_hours:.1f}h)")
        
        print("\n✅ Cleanup functionality test completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up test directory
        if test_dir.exists():
            import shutil
            shutil.rmtree(test_dir)
            print(f"\n🧹 Test directory cleaned up")

if __name__ == "__main__":
    main()
