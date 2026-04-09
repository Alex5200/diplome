# STL Models Directory

Положите сюда свои STL файлы для робота и объектов.

## Структура

```
stl_models/
├── robot/           # STL файлы робота
│   ├── base.stl
│   ├── link1.stl
│   ├── link2.stl
│   ├── link3.stl
│   ├── link4.stl
│   ├── link5.stl
│   └── gripper.stl
└── objects/         # STL файлы объектов
    ├── cube.stl
    ├── cylinder.stl
    └── target.stl
```

## Требования к STL

- **Формат**: Binary STL (предпочтительнее) или ASCII STL
- **Единицы**: метры (MuJoCo стандарт)
- **Нормали**: должны быть корректными для правильной визуализации
- **Количество треугольников**: не более 10,000 для производительности

## Конвертация

Если у вас файлы в других форматах:

```bash
# OBJ → STL (используя Blender)
blender -b -P convert_obj_to_stl.py -- input.obj output.stl

# STEP → STL (используя FreeCAD)
freecadcmd convert_step.py input.step output.stl
```

## Масштабирование

В XML можно указать масштаб:
```xml
<mesh file="base.stl" name="base_mesh" scale="0.001 0.001 0.001"/>
<!-- scale="0.001" если STL в мм, MuJoCo ожидает метры -->
```
