/**
 * ============================================================
 *  СБОРЩИК ГЛАВ 2 И 3 ДИПЛОМНОЙ РАБОТЫ
 * ============================================================
 *
 *  Запуск:
 *    cd docs/chapters
 *    node build_chapters.js
 *
 *  Результат:
 *    docs/chapters/diploma_ch2_ch3.docx
 *
 *  Структура:
 *    - ГЛАВА 2. РЕАЛИЗАЦИЯ ПРОГРАММНОГО ОБЕСПЕЧЕНИЯ
 *      2.1 Архитектура и паттерны проектирования
 *      2.2 Реализация управления сервоприводами ST3215
 *      2.3 Реализация кинематического модуля
 *      2.4 Desktop-приложение с графическим интерфейсом
 *      2.5 Web-интерфейс и REST API
 *      2.6 Интеграция с ROS2
 *      2.7 Система высокоуровневых программ-задач
 *      2.8 Симуляция в среде MuJoCo
 *    - ГЛАВА 3. ТЕСТИРОВАНИЕ И РЕЗУЛЬТАТЫ
 *      3.1 Методология и стратегия тестирования
 *      3.2 Модульное тестирование
 *      3.3 Интеграционное тестирование
 *      3.4 Системное тестирование
 *      3.5 Сводные результаты и анализ
 *
 * ============================================================
 */

const fs = require("fs");
const path = require("path");
const h = require("../diploma_helpers.js");

const {
  Document, Packer, Paragraph, TextRun,
  Header, Footer, AlignmentType,
  PageNumber, PageBreak
} = h;

// ========== ЗАГРУЗКА МОДУЛЕЙ ==========
const modules = [
  // Глава 2
  "./ch2_1_architecture.js",
  "./ch2_2_motor_control.js",
  "./ch2_3_kinematics.js",
  "./ch2_4_desktop_gui.js",
  "./ch2_5_web_api.js",
  "./ch2_6_ros2.js",
  "./ch2_7_programs.js",
  "./ch2_8_mujoco.js",
  // Глава 3
  "./ch3_1_methodology.js",
  "./ch3_2_unit_testing.js",
  "./ch3_3_integration_testing.js",
  "./ch3_4_system_testing.js",
  "./ch3_5_results.js",
];

console.log("=== Сборка глав 2 и 3 дипломной работы ===\n");

const children = [];

for (const mod of modules) {
  const name = path.basename(mod, ".js");
  console.log(`  Загрузка: ${name}`);
  try {
    const fn = require(mod);
    const paragraphs = fn(h);
    children.push(...paragraphs);
    console.log(`    -> ${paragraphs.length} элементов`);
  } catch (err) {
    console.error(`  ОШИБКА в ${name}: ${err.message}`);
    process.exit(1);
  }
}

console.log(`\nВсего элементов: ${children.length}`);

// ========== СОЗДАНИЕ ДОКУМЕНТА ==========
const FONT = "Times New Roman";

const doc = new Document({
  styles: {
    default: {
      document: {
        run: { font: FONT, size: 28 }
      }
    },
    paragraphStyles: [
      {
        id: "Heading1", name: "Heading 1",
        basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: FONT },
        paragraph: {
          spacing: { before: 360, after: 240 },
          alignment: AlignmentType.CENTER,
          outlineLevel: 0
        }
      },
      {
        id: "Heading2", name: "Heading 2",
        basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: FONT },
        paragraph: {
          spacing: { before: 280, after: 200 },
          outlineLevel: 1
        }
      },
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 }, // A4
        margin: { top: 1134, bottom: 1134, left: 1701, right: 851 }
        // 2 см верх/низ, 3 см лево, 1.5 см право
      }
    },
    headers: {
      default: new Header({
        children: [new Paragraph({ children: [] })]
      })
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({
            children: [PageNumber.CURRENT],
            font: FONT,
            size: 24
          })]
        })]
      })
    },
    children
  }]
});

// ========== СОХРАНЕНИЕ ==========
const outPath = path.join(__dirname, "diploma_ch2_ch3.docx");

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(outPath, buffer);
  console.log(`\nДокумент создан: ${outPath}`);
  console.log(`Размер: ${(buffer.length / 1024).toFixed(1)} KB`);
  console.log("\n=== Готово ===");
}).catch(err => {
  console.error("Ошибка генерации:", err);
  process.exit(1);
});
