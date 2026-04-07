/**
 * ============================================================
 *  DIPLOMA HELPERS — общий модуль форматирования
 * ============================================================
 *
 *  ПРАВИЛА ДЛЯ ВСЕХ МОДУЛЕЙ (ОБЯЗАТЕЛЬНО К СОБЛЮДЕНИЮ):
 *
 *  ШРИФТЫ:
 *    - Основной текст: Times New Roman, 14pt (size: 28 в half-points)
 *    - Заголовок главы (heading1): Times New Roman, 16pt (size: 32), bold, CENTER
 *    - Заголовок раздела (heading2): Times New Roman, 14pt (size: 28), bold, LEFT
 *    - Заголовок подраздела (heading3): Times New Roman, 14pt (size: 28), bold+italic, LEFT
 *    - Код (codeBlock): Courier New, 11pt (size: 22), LEFT, отступ слева 360
 *    - Подпись таблицы (tableCaption): Times New Roman, 14pt, italic, CENTER
 *    - Ячейки таблицы: Times New Roman, 12pt (size: 24)
 *    - Формулы (formula): Times New Roman, 14pt, italic, CENTER
 *
 *  ИНТЕРВАЛЫ:
 *    - Межстрочный: 1.5 (line: 360 в twentieths of a point)
 *    - После абзаца: 120 twips (по умолчанию)
 *    - Абзацный отступ: 1.25 см (firstLine: 709 twips)
 *
 *  СТРАНИЦА (A4):
 *    - Размер: 210×297 мм (11906×16838 twips)
 *    - Поля: верх/низ 2 см (1134), лево 3 см (1701), право 1.5 см (851)
 *
 *  НУМЕРАЦИЯ:
 *    - Таблицы: «Таблица X.Y — Название» (X = номер главы, Y = порядковый)
 *    - Рисунки: «Рисунок X.Y — Название» (X = номер главы, Y = порядковый)
 *    - Формулы: (X.Y) справа от формулы
 *    - Листинги кода: «Листинг X.Y — Название»
 *
 *  СТИЛЬ ТЕКСТА:
 *    - Научный стиль, без разговорных оборотов
 *    - Абзацы по 4-8 строк минимум
 *    - Каждый раздел начинается с вводного абзаца
 *    - Ссылки на таблицы/рисунки в тексте обязательны
 *    - Код оформляется через codeBlock() с подписью через codeCaption()
 *    - Перед PageBreak всегда завершающий абзац раздела
 *
 *  СТРУКТУРА МОДУЛЯ:
 *    Каждый модуль экспортирует функцию:
 *      module.exports = function(h) { return [...paragraphs]; }
 *    где h — этот объект хелперов (h.p, h.heading2, h.codeBlock и т.д.)
 *
 * ============================================================
 */

const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat,
  HeadingLevel, BorderStyle, WidthType, ShadingType,
  PageNumber, PageBreak, TabStopType, TabStopPosition,
  ImageRun
} = require("docx");

// ========== CONSTANTS ==========
const FONT = "Times New Roman";
const CODE_FONT = "Courier New";

// ========== PARAGRAPH ==========
function p(text, opts = {}) {
  const runs = [];
  if (typeof text === "string") {
    runs.push(new TextRun({
      text,
      font: opts.codeFont || FONT,
      size: opts.size || 28,
      bold: !!opts.bold,
      italics: !!opts.italics
    }));
  } else if (Array.isArray(text)) {
    text.forEach(t => {
      if (typeof t === "string") runs.push(new TextRun({ text: t, font: FONT, size: opts.size || 28 }));
      else runs.push(new TextRun({ font: FONT, size: 28, ...t }));
    });
  }
  return new Paragraph({
    spacing: { line: 360, after: opts.afterSpacing !== undefined ? opts.afterSpacing : 120 },
    alignment: opts.alignment || AlignmentType.JUSTIFIED,
    indent: opts.noIndent ? undefined : { firstLine: 709 },
    ...opts.paragraphOpts,
    children: runs
  });
}

// ========== HEADINGS ==========
function heading1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 360, after: 240, line: 360 },
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text, font: FONT, size: 32, bold: true })]
  });
}

function heading2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 280, after: 200, line: 360 },
    alignment: AlignmentType.LEFT,
    children: [new TextRun({ text, font: FONT, size: 28, bold: true })]
  });
}

function heading3(text) {
  return new Paragraph({
    spacing: { before: 200, after: 160, line: 360 },
    alignment: AlignmentType.LEFT,
    children: [new TextRun({ text, font: FONT, size: 28, bold: true, italics: true })]
  });
}

// ========== FORMULA ==========
function formula(text, number) {
  return new Paragraph({
    spacing: { before: 120, after: 120, line: 360 },
    alignment: AlignmentType.CENTER,
    children: [
      new TextRun({ text, font: FONT, size: 28, italics: true }),
      new TextRun({ text: `    (${number})`, font: FONT, size: 28 })
    ]
  });
}

// ========== CODE BLOCK ==========
function codeBlock(lines) {
  return lines.map((line, i) => new Paragraph({
    spacing: { line: 276, after: 0 },
    alignment: AlignmentType.LEFT,
    indent: { left: 360 },
    ...(i === 0 ? { border: { top: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" } } } : {}),
    children: [new TextRun({ text: line, font: CODE_FONT, size: 22 })]
  }));
}

/**
 * Подпись листинга кода — ставится ПЕРЕД codeBlock
 * Пример: codeCaption("Листинг 2.1 — Инициализация DH-параметров")
 */
function codeCaption(text) {
  return new Paragraph({
    spacing: { before: 200, after: 100, line: 360 },
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text, font: FONT, size: 28, italics: true })]
  });
}

// ========== TABLES ==========
const border = { style: BorderStyle.SINGLE, size: 1, color: "999999" };
const borders = { top: border, bottom: border, left: border, right: border };
const cellMargins = { top: 60, bottom: 60, left: 100, right: 100 };

function tableCaption(text) {
  return new Paragraph({
    spacing: { before: 200, after: 100, line: 360 },
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text, font: FONT, size: 28, italics: true })]
  });
}

function makeCell(text, opts = {}) {
  return new TableCell({
    borders,
    width: { size: opts.width || 2000, type: WidthType.DXA },
    margins: cellMargins,
    shading: opts.header ? { fill: "D5E8F0", type: ShadingType.CLEAR } : undefined,
    children: [new Paragraph({
      spacing: { line: 276, after: 0 },
      alignment: opts.center ? AlignmentType.CENTER : AlignmentType.LEFT,
      children: [new TextRun({ text: String(text), font: FONT, size: opts.size || 24, bold: !!opts.header })]
    })]
  });
}

function makeTable(headers, rows, colWidths) {
  const totalW = colWidths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: totalW, type: WidthType.DXA },
    columnWidths: colWidths,
    rows: [
      new TableRow({ children: headers.map((h, i) => makeCell(h, { width: colWidths[i], header: true, center: true })) }),
      ...rows.map(row => new TableRow({
        children: row.map((c, i) => makeCell(c, { width: colWidths[i], center: i > 0 }))
      }))
    ]
  });
}

// ========== FIGURE (placeholder) ==========
/**
 * Заглушка для рисунка — место для вставки скриншота/диаграммы
 * Пример: figureCaption("Рисунок 2.1 — Архитектура системы")
 */
function figureCaption(text) {
  return new Paragraph({
    spacing: { before: 200, after: 100, line: 360 },
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text, font: FONT, size: 28, italics: true })]
  });
}

function figurePlaceholder(caption) {
  return [
    new Paragraph({
      spacing: { before: 200, after: 100, line: 360 },
      alignment: AlignmentType.CENTER,
      children: [new TextRun({
        text: "[МЕСТО ДЛЯ РИСУНКА — вставить изображение вручную или через ImageRun]",
        font: FONT, size: 24, italics: true, color: "999999"
      })]
    }),
    figureCaption(caption)
  ];
}

// ========== UTILITY ==========
function emptyLine() {
  return new Paragraph({ spacing: { after: 0, line: 360 }, children: [] });
}

function pageBreak() {
  return new Paragraph({ children: [new PageBreak()] });
}

/**
 * Маркированный список (дефис + текст)
 */
function bulletDash(text, opts = {}) {
  return p("— " + text, { noIndent: true, ...opts });
}

/**
 * Нумерованный элемент (число + текст)
 */
function numberedItem(num, text, opts = {}) {
  return p(`${num}. ${text}`, { noIndent: false, ...opts });
}

// ========== EXPORTS ==========
module.exports = {
  // docx re-exports (для удобства в модулях)
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, HeadingLevel, BorderStyle,
  WidthType, ShadingType, PageNumber, PageBreak, ImageRun,

  // constants
  FONT, CODE_FONT,

  // functions
  p,
  heading1,
  heading2,
  heading3,
  formula,
  codeBlock,
  codeCaption,
  tableCaption,
  makeCell,
  makeTable,
  figureCaption,
  figurePlaceholder,
  emptyLine,
  pageBreak,
  bulletDash,
  numberedItem
};
