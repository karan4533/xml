# 🧹 Automatic Session Cleanup System

## ✅ **PROBLEM SOLVED**
**Question**: "*Is it possible to delete or remove the old session once the session has been completed?*"

**Answer**: **YES!** We've implemented a comprehensive automatic session cleanup system with multiple strategies.

---

## 🎯 **SOLUTION OVERVIEW**

### **What Gets Cleaned Up Automatically:**
- ✅ Old session directories (older than configured age)
- ✅ Excess sessions (beyond configured maximum count)
- ✅ All files within old sessions (XML, images, tables)
- ✅ Automatic size calculation and reporting

### **What Gets Preserved:**
- ✅ Current active session (always kept)
- ✅ Recent sessions within age limit
- ✅ Sessions within maximum count limit

---

## 🔧 **CLEANUP STRATEGIES**

### **1. Time-Based Cleanup**
- **Default**: Sessions older than **24 hours** are removed
- **Configurable**: 1-168 hours (1 week) via UI
- **Logic**: Uses file modification time to determine age

### **2. Count-Based Cleanup**
- **Default**: Keep only **5 newest** sessions
- **Configurable**: 1-20 sessions via UI  
- **Logic**: Sorts by modification time, removes oldest excess

### **3. Combination Strategy**
- Sessions are removed if they meet **either** condition:
  - Older than max age **OR** beyond max count
- Current session is **always preserved**

---

## ⚙️ **CONFIGURATION OPTIONS**

### **Automatic Cleanup (Default: ON)**
```python
# In Streamlit sidebar
auto_cleanup = True  # Enabled by default
max_sessions = 5     # Keep 5 newest sessions
max_age_hours = 24   # Remove sessions older than 24 hours
```

### **Manual Cleanup Controls**
```python
# Optional manual controls
manual_cleanup = False  # Show cleanup buttons
```

---

## 🔄 **HOW IT WORKS**

### **1. Session Creation**
```
output/
├── session_abc123def456/     # Current session
│   ├── combined.xml
│   ├── tables/
│   └── assets/images/
├── session_xyz789uvw012/     # Previous session  
└── manifest.json             # Shared manifest
```

### **2. Automatic Cleanup Trigger**
- **When**: After each PDF processing completes
- **Where**: `_cleanup_old_sessions()` function called automatically
- **Safe**: Never removes current session

### **3. Cleanup Process**
1. **Scan** output directory for session folders
2. **Analyze** each session (age, modification time)
3. **Calculate** size before removal
4. **Remove** sessions meeting cleanup criteria
5. **Report** cleanup statistics

---

## 📊 **CLEANUP STATISTICS**

Each cleanup operation reports:
```json
{
  "sessions_found": 8,
  "sessions_removed": 3,
  "sessions_kept": 5,
  "space_freed_mb": 45.7,
  "cleanup_reason": [
    "session_old123:aged_25.3h",
    "session_old456:excess_count", 
    "session_old789:aged_30.1h"
  ]
}
```

---

## 🎮 **USER INTERFACE**

### **Sidebar Settings**
```
💾 Storage
  📁 Session Management:
    ☑️ Auto-cleanup old sessions
      Max sessions to keep: 5
      Max age (hours): 24
    ☐ Manual cleanup after viewing
```

### **Post-Processing Controls** (if enabled)
```
🧹 Session Management
  💾 Current session size: 12.3 MB
  
  [🗑️ Delete Current Session]  [🧹 Cleanup All Old Sessions]
```

---

## 🚀 **BENEFITS**

| **Benefit** | **Description** |
|-------------|-----------------|
| **🔄 Automatic** | No manual intervention required |
| **🎯 Smart** | Keeps recent sessions, removes old ones |
| **📊 Transparent** | Shows what was cleaned and space freed |
| **⚙️ Configurable** | Adjust limits based on needs |
| **🛡️ Safe** | Never removes current active session |
| **💾 Space Efficient** | Prevents disk space accumulation |

---

## 🔍 **EXAMPLE SCENARIOS**

### **Scenario 1: Daily Usage**
- Process 3 PDFs per day
- **Settings**: Keep 5 sessions, max 24h age
- **Result**: Always have last 5 sessions available, older ones auto-removed

### **Scenario 2: Heavy Usage**
- Process 20 PDFs per day
- **Settings**: Keep 10 sessions, max 12h age  
- **Result**: Keep last 10 sessions, remove anything older than 12 hours

### **Scenario 3: Storage Conscious**
- Limited disk space
- **Settings**: Keep 3 sessions, max 6h age
- **Result**: Very aggressive cleanup, minimal disk usage

---

## 💡 **USAGE RECOMMENDATIONS**

### **For Development**
```
Max sessions: 10
Max age: 48 hours
Manual cleanup: ON
```

### **For Production**
```
Max sessions: 5
Max age: 24 hours  
Manual cleanup: OFF
```

### **For Storage-Limited Systems**
```
Max sessions: 3
Max age: 12 hours
Manual cleanup: ON
```

---

## 🛠️ **TECHNICAL IMPLEMENTATION**

### **Core Functions**
- `_cleanup_old_sessions()` - Main cleanup logic
- `_get_directory_size_mb()` - Calculate directory sizes
- Integration with `process_pdf()` - Automatic trigger

### **Cleanup Logic**
```python
def _cleanup_old_sessions(output_dir, max_sessions=5, max_age_hours=24):
    # 1. Find all session directories
    # 2. Sort by modification time
    # 3. Apply age-based removal
    # 4. Apply count-based removal  
    # 5. Calculate and report statistics
    return cleanup_stats
```

---

## ✅ **SUMMARY**

**Yes, old sessions are automatically deleted!** The system provides:

- **🔄 Automatic cleanup** after each processing
- **⚙️ Configurable limits** (age and count)
- **🛡️ Safe operation** (never removes current session)
- **📊 Detailed reporting** of cleanup actions
- **🎮 Manual controls** for advanced users
- **💾 Space optimization** without losing recent work

**Result**: Your disk space stays clean automatically while preserving recent sessions for reference! 🎉
