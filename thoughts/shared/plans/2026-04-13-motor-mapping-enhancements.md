---
date: 2026-04-13
topic: "Motor Mapping Enhancements Implementation"
status: ready
---

# Implementation Plan: Motor Mapping Direction & Position Limits

## Task 1: Update MotorController.update_motor_mapping()

**File:** `app/controllers/motor_controller.py`

**Changes:**
- Add `min_pos` and `max_pos` parameters to `update_motor_mapping()` method
- Store these values in the motor_mapping dictionary

**Implementation:**
```python
def update_motor_mapping(
    self, 
    joint_index: int, 
    motor_id: int, 
    name: str = "", 
    inverted: bool = False,
    min_pos: int = 0,
    max_pos: int = MAX_POSITION,
):
```

## Task 2: Update MotorMappingPanel - Add New Variables

**File:** `app/views/motor_mapping_panel.py`

**Add to `__init__`:**
- `self.min_pos_vars: dict[int, tk.IntVar]`
- `self.max_pos_vars: dict[int, tk.IntVar]`
- `self.position_bars: dict[int, tk.Canvas]`
- `self.fill_rects: dict[int, int]` (canvas item ids)
- `self.current_positions: dict[int, int]`

## Task 3: Update MotorMappingPanel._create_widgets()

**Add new columns to table header:**
- "Dir" (40px)
- "Min" (60px)
- "Max" (60px)
- "Position" (140px)

**Add to each row:**
1. Direction toggle button (↑/↓)
2. Min position spinbox (0-4095)
3. Max position spinbox (0-4095)
4. Canvas-based position bar (100px + label)

## Task 4: Update MotorMappingPanel._load_current_mapping()

Read min_pos, max_pos from motor_mapping and set the corresponding vars.

## Task 5: Update MotorMappingPanel._save_mapping()

Include min_pos and max_pos when calling `controller.update_motor_mapping()`.

## Task 6: Implement update_positions() method

Accept position data and update position bars visually.

## Testing Steps

1. Launch application
2. Navigate to Motor Mapping tab
3. Verify new columns are visible
4. Toggle direction - check icon changes
5. Set min=100, max=3900 - verify position bar scales
6. Try min > max - verify validation (red highlight)
7. Save configuration
8. Restart application - verify values persist
