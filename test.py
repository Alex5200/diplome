import st3215
import serial

try:
    # Попробуем указать скорость явно, если библиотека позволяет
    motor = st3215.ST3215("COM3")

    print("Поиск сервоприводов...")
    servos = motor.ListServos()
    print(f"Найдено: {servos}")

    if 2 in servos:  # Проверяем, есть ли серво с ID 2
        print("Меняем ID...")
        result = motor.ChangeId(2, 8)
        print(f"Результат: {result}")

        print("Повторный поиск...")
        print(motor.ListServos())
    else:
        print("Сервопривод с ID 2 не найден! Проверьте заводской ID (часто это 1).")

except serial.SerialException as e:
    print(f"Ошибка порта: {e}")
except Exception as e:
    print(f"Общая ошибка: {e}")
