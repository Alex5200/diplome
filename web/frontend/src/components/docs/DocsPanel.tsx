export function DocsPanel() {
  return (
    <div className="flex-1 overflow-auto p-6 bg-gray-50">
      <div className="max-w-3xl mx-auto space-y-6">
        <h1 className="text-2xl font-bold text-gray-800">
          ST3215 Robot Control — Документация
        </h1>

        <section className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <h2 className="text-lg font-semibold text-gray-700 mb-2">
            Подключение
          </h2>
          <ul className="text-sm text-gray-600 space-y-1">
            <li>1. Выберите COM-порт (например, COM3 на Windows)</li>
            <li>2. Нажмите Connect для подключения к роботу</li>
            <li>3. После подключения доступно управление</li>
            <li>4. Scan — пересканировать подключённые моторы</li>
          </ul>
        </section>

        <section className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <h2 className="text-lg font-semibold text-gray-700 mb-2">
            Управление суставами
          </h2>
          <ul className="text-sm text-gray-600 space-y-1">
            <li>• Переместите ползунок для выбора угла сустава</li>
            <li>• Нажмите Go для отправки команды на мотор</li>
            <li>• Скорость (100-3400) влияет на скорость движения</li>
          </ul>
        </section>

        <section className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <h2 className="text-lg font-semibold text-gray-700 mb-2">
            Пресеты положений
          </h2>
          <ul className="text-sm text-gray-600 space-y-1">
            <li><strong>Home</strong> — все суставы в 0°</li>
            <li><strong>Up</strong> — робот поднят вверх</li>
            <li><strong>Fold</strong> — сложенное положение</li>
            <li><strong>Reach</strong> — вытянутое положение</li>
          </ul>
        </section>

        <section className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <h2 className="text-lg font-semibold text-gray-700 mb-2">
            3D визуализация
          </h2>
          <p className="text-sm text-gray-600">
            Справа отображается 3D модель робота. Суставы синхронизированы
            с ползунками управления. Конечная точка (T) показывает положение
            инструмента в пространстве.
          </p>
        </section>

        <section className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <h2 className="text-lg font-semibold text-gray-700 mb-2">
            Программирование (Blockly)
          </h2>
          <ul className="text-sm text-gray-600 space-y-1">
            <li>• Используйте Blockly для создания программ</li>
            <li>• Доступны команды: движение, ожидание, повтор</li>
            <li>• Сохраняйте и загружайте программы</li>
          </ul>
        </section>

        <section className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <h2 className="text-lg font-semibold text-gray-700 mb-2">
            Телеметрия
          </h2>
          <ul className="text-sm text-gray-600 space-y-1">
            <li>• Position: текущая позиция мотора (0-4095)</li>
            <li>• T°C: температура мотора</li>
            <li>• V: напряжение питания</li>
            <li>• mA: ток потребления</li>
            <li>• Load: нагрузка мотора</li>
          </ul>
        </section>

        <section className="bg-red-50 rounded-lg border border-red-200 p-4">
          <h2 className="text-lg font-semibold text-red-800 mb-2">
            ⚠️ Техника безопасности
          </h2>
          <ul className="text-sm text-red-700 space-y-1">
            <li>• Всегда следите за движущимся роботом</li>
            <li>• Не касайтесь частей робота во время движения</li>
            <li>• Используйте E-STOP для аварийной остановки</li>
            <li>• Начинайте с низкой скорости (500-1000)</li>
            <li>• Проверьте диапазоны движения перед запуском</li>
          </ul>
        </section>

        <section className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <h2 className="text-lg font-semibold text-gray-700 mb-2">
            Горячие клавиши
          </h2>
          <ul className="text-sm text-gray-600 space-y-1">
            <li><kbd className="px-1 py-0.5 bg-gray-100 rounded">Esc</kbd> — аварийная остановка</li>
          </ul>
        </section>
      </div>
    </div>
  );
}
