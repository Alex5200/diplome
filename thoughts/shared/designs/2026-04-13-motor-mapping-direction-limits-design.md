---
date: 2026-04-13
topic: "Motor Mapping Panel — Direction & Position Limits"
status: validated
---

# Motor Mapping Panel — Direction & Position Limits Design

## Problem Statement

Расширить панель настройки моторов для поддержки:
- **Визуальной индикации направления** движения (прямое/инвертированное)
- **Минимальной и максимальной позиции** для каждого сустава
- **Визуальной шкалы** текущей позиции

## Constraints

- Сохранить существующий стиль (пастельная тема FANUC_*)
- Не нарушать текущую табличную структуру
- Мин/макс должны сохраняться в robot_config.json
- Компактное размещение — ширина панели не более 1200px

## Approach

**Выбранный подход: Расширение таблицы**

Добавляем 3 новые колонки в существующую таблицу:
1. **Direction** — toggle-кнопка со стрелкой
2. **Min/Max** — два числовых поля
3. **Position Bar** — визуальная шкала

**Преимущества:**
- Все настройки в одном месте
- Мгновенная визуальная обратная связь
- Минимальные изменения в архитектуре

## Architecture

### Общая структура

```
┌────────────────────────────────────────────────────────────────────────────┐
│ MOTOR MAPPING                              [AUTO DETECT]  [RESET]  [SAVE] │
├────────────────────────────────────────────────────────────────────────────┤
│ Joint │ Motor ID │ Name      │ Dir │ Min   │ Max   │ Position Scale     │
│ J1    │   [1]    │ База [▼]  │ ↕   │ [   0]│ [4095]│ ▓▓▓▓▓░░░░░ 2048   │
│ J2    │   [2]    │ Плечо [▼] │ ↕   │ [   0]│ [4095]│ ░░░▓▓▓▓▓░░ 3000   │
│ ...                                                                       │
└────────────────────────────────────────────────────────────────────────────┘
```

### Компоненты строки

**1. Joint Label (существующий)**
- J1-J6
- Bold, FANUC_GREEN

**2. Motor ID Spinbox (существующий)**
- Диапазон 1-253
- Текущее значение из mapping

**3. Name Entry (существующий)**
- Текстовое поле с именем сустава

**4. Direction Toggle (НОВЫЙ)**
- Кнопка 40x28px
- Иконка: `↕` (прямое) или `↕` с инверсией
- Цвет: FANUC_GREEN (normal) / FANUC_ORANGE (inverted)
- Клик переключает `inverted` булево

**5. Min Position Spinbox (НОВЫЙ)**
- Ширина 60px
- Диапазон: 0-4095
- Значение из `min_pos`
- Валидация: min < max

**6. Max Position Spinbox (НОВЫЙ)**
- Ширина 60px
- Диапазон: 0-4095
- Значение из `max_pos`
- Валидация: max > min

**7. Position Bar (НОВЫЙ)**
- Ширина 120px
- Заполнение пропорционально (position - min) / (max - min)
- Цвет заполнения: FANUC_BLUE
- Числовое значение справа (0-4095)

## Components

### MotorMappingPanel — новые свойства

```python
self.direction_vars: dict[int, tk.BooleanVar]  # inverted state
self.min_pos_vars: dict[int, tk.IntVar]        # min position
self.max_pos_vars: dict[int, tk.IntVar]        # max position
self.position_bars: dict[int, tk.Canvas]       # canvas для шкалы
self.current_positions: dict[int, int]         # текущие позиции от мотора
```

### Direction Toggle Widget

**Состояния:**
| inverted | Иконка | Цвет фона | Tooltip |
|----------|--------|-----------|---------|
| False | `↑` | FANUC_GREEN | "Прямое направление" |
| True | `↓` | FANUC_ORANGE | "Инвертированное направление" |

**Поведение:**
- Клик переключает `inverted`
- Обновляет `self.inverted_vars[i]`
- Перерисовывает иконку и цвет

### Position Bar Widget

**Рендеринг:**
```python
def _update_position_bar(self, joint_index: int, position: int):
    min_pos = self.min_pos_vars[joint_index].get()
    max_pos = self.max_pos_vars[joint_index].get()
    
    # Нормализация 0-1
    ratio = (position - min_pos) / (max_pos - min_pos) if max_pos > min_pos else 0
    ratio = max(0, min(1, ratio))  # clamp
    
    # Ширина заполнения
    fill_width = int(100 * ratio)  # 100px полная ширина
    
    # Обновление canvas
    self.position_bars[joint_index].coords(
        self.fill_rects[joint_index],
        [0, 0, fill_width, 20]
    )
```

### Data Flow

**Загрузка:**
```
_load_current_mapping()
    ↓
Чтение motor_mapping[key]["min_pos"], ["max_pos"], ["inverted"]
    ↓
Установка vars: min_pos_vars[i], max_pos_vars[i], inverted_vars[i]
    ↓
Отрисовка direction toggle и position bar
```

**Сохранение:**
```
_save_mapping()
    ↓
Для каждого joint:
  - motor_id из mapping_vars
  - name из name_vars
  - inverted из inverted_vars (direction toggle)
  - min_pos из min_pos_vars
  - max_pos из max_pos_vars
    ↓
controller.update_motor_mapping() → включает min_pos/max_pos
    ↓
controller.save_config()
```

**Обновление позиций (real-time):**
```
update_positions(data: dict[int, int])
    ↓
Для каждого joint_index:
  - Получить позицию из data
  - _update_position_bar(joint_index, position)
```

## Error Handling

### Валидация Min/Max

**Правила:**
- `min_pos >= 0` и `max_pos <= 4095`
- `min_pos < max_pos` (строго)

**UI реакция на ошибку:**
```python
if min >= max:
    min_entry.config(bg=FANUC_RED)  # красная подсветка
    max_entry.config(bg=FANUC_RED)
    tooltip.show("Min должен быть меньше Max")
    save_button.config(state="disabled")
else:
    min_entry.config(bg=FANUC_BG)
    max_entry.config(bg=FANUC_BG)
    save_button.config(state="normal")
```

### Границы Spinbox

- `from_=0`, `to=4095` на уровне виджета
- При ручном вводе: валидация по потере фокуса
- Авто-коррекция: `max(0, min(4095, value))`

## Testing Strategy

### Ручное тестирование

| Сценарий | Ожидаемый результат |
|----------|---------------------|
| Клик direction toggle | Иконка и цвет меняются |
| Установка min=100, max=200 | Position bar масштабируется |
| min > max | Красная подсветка, save disabled |
| Сохранение и перезагрузка | Значения восстанавливаются |
| update_positions() вызов | Position bar обновляется |

### Автоматическая валидация

```python
def _validate_min_max(self, joint_index: int) -> bool:
    min_val = self.min_pos_vars[joint_index].get()
    max_val = self.max_pos_vars[joint_index].get()
    return min_val < max_val and 0 <= min_val and max_val <= 4095
```

## Open Questions

1. **Формат direction icon** — использовать Unicode (↑↓) или Canvas-рисование?
   - Решение: Unicode для простоты, `text="↑"` / `text="↓"`

2. **Real-time обновление позиций** — нужно ли показывать текущие позиции моторов?
   - Решение: Да, через метод `update_positions()` который вызывается из MotorMonitor

3. **Единицы измерения** — показывать градусы или raw position (0-4095)?
   - Решение: Raw position (0-4095) для консистентности с драйвером

## Implementation Notes

### Изменения в MotorController

Добавить поля в `update_motor_mapping()`:
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
    key = f"joint_{joint_index}"
    self.motor_mapping[key] = {
        "motor_id": motor_id,
        "name": name or default_name,
        "min_pos": min_pos,
        "max_pos": max_pos,
        "inverted": inverted,
    }
```

### Изменения в constants.py

DEFAULT_MOTOR_MAPPING уже содержит `min_pos`, `max_pos`, `inverted` — структура готова.

### Сохранение в конфиг

Формат robot_config.json:
```json
{
  "motor_mapping": {
    "joint_0": {
      "motor_id": 1,
      "name": "База",
      "min_pos": 100,
      "max_pos": 3900,
      "inverted": true
    }
  }
}
```
