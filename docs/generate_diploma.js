const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat,
  HeadingLevel, BorderStyle, WidthType, ShadingType,
  PageNumber, PageBreak, TabStopType, TabStopPosition
} = require("docx");

// ========== HELPERS ==========
const FONT = "Times New Roman";
const CODE_FONT = "Courier New";

function p(text, opts = {}) {
  const runs = [];
  if (typeof text === "string") {
    runs.push(new TextRun({ text, font: opts.codeFont || FONT, size: opts.size || 28, bold: !!opts.bold, italics: !!opts.italics }));
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

function codeBlock(lines) {
  return lines.map((line, i) => new Paragraph({
    spacing: { line: 276, after: 0 },
    alignment: AlignmentType.LEFT,
    indent: { left: 360 },
    ...(i === 0 ? { border: { top: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" } } } : {}),
    children: [new TextRun({ text: line, font: CODE_FONT, size: 22 })]
  }));
}

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
  const totalW = colWidths.reduce((a,b) => a+b, 0);
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

function emptyLine() {
  return new Paragraph({ spacing: { after: 0, line: 360 }, children: [] });
}

// ========== DOCUMENT CONTENT ==========
const children = [];

// ===== ТИТУЛЬНАЯ СТРАНИЦА =====
children.push(
  emptyLine(), emptyLine(), emptyLine(), emptyLine(),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 600, line: 360 },
    children: [new TextRun({ text: "ДИПЛОМНАЯ РАБОТА", font: FONT, size: 36, bold: true })] }),
  emptyLine(),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200, line: 360 },
    children: [new TextRun({ text: "Разработка программного обеспечения для управления", font: FONT, size: 32, bold: true })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 600, line: 360 },
    children: [new TextRun({ text: "6-осевым роботом-манипулятором на базе сервоприводов ST3215", font: FONT, size: 32, bold: true })] }),
  emptyLine(), emptyLine(), emptyLine(), emptyLine(),
  new Paragraph({ alignment: AlignmentType.RIGHT, spacing: { after: 100, line: 360 },
    children: [new TextRun({ text: "Выполнил: Ляхов Александр", font: FONT, size: 28 })] }),
  emptyLine(), emptyLine(), emptyLine(), emptyLine(), emptyLine(), emptyLine(),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 0, line: 360 },
    children: [new TextRun({ text: "2026", font: FONT, size: 28 })] }),
  new Paragraph({ children: [new PageBreak()] })
);

// ===== СОДЕРЖАНИЕ =====
children.push(
  heading1("СОДЕРЖАНИЕ"),
  p("ВВЕДЕНИЕ", { noIndent: true, afterSpacing: 60 }),
  p("ГЛАВА 1. ТЕОРЕТИЧЕСКИЕ ОСНОВЫ", { noIndent: true, afterSpacing: 60 }),
  p("  1.1 Кинематика робота-манипулятора", { noIndent: true, afterSpacing: 40 }),
  p("  1.2 Обратная кинематика", { noIndent: true, afterSpacing: 40 }),
  p("  1.3 Сервоприводы ST3215", { noIndent: true, afterSpacing: 40 }),
  p("  1.4 Симуляция в MuJoCo", { noIndent: true, afterSpacing: 60 }),
  p("ГЛАВА 2. АРХИТЕКТУРА ПРОГРАММНОГО ОБЕСПЕЧЕНИЯ", { noIndent: true, afterSpacing: 60 }),
  p("  2.1 Многоплатформенная архитектура системы", { noIndent: true, afterSpacing: 40 }),
  p("  2.2 Общий слой (shared)", { noIndent: true, afterSpacing: 40 }),
  p("  2.3 Desktop приложение", { noIndent: true, afterSpacing: 40 }),
  p("  2.4 Web интерфейс", { noIndent: true, afterSpacing: 40 }),
  p("  2.5 ROS2 интеграция", { noIndent: true, afterSpacing: 40 }),
  p("  2.6 Система программ для задач", { noIndent: true, afterSpacing: 60 }),
  p("ГЛАВА 3. РЕАЛИЗАЦИЯ КЛЮЧЕВЫХ АЛГОРИТМОВ", { noIndent: true, afterSpacing: 60 }),
  p("  3.1 Реализация прямой кинематики", { noIndent: true, afterSpacing: 40 }),
  p("  3.2 Реализация обратной кинематики", { noIndent: true, afterSpacing: 40 }),
  p("  3.3 Управление моторами ST3215", { noIndent: true, afterSpacing: 40 }),
  p("  3.4 Безопасный визуализатор", { noIndent: true, afterSpacing: 40 }),
  p("  3.5 Симуляция в MuJoCo", { noIndent: true, afterSpacing: 60 }),
  p("ГЛАВА 4. РЕЗУЛЬТАТЫ И ТЕСТИРОВАНИЕ", { noIndent: true, afterSpacing: 60 }),
  p("  4.1 Тестирование прямой кинематики", { noIndent: true, afterSpacing: 40 }),
  p("  4.2 Тестирование обратной кинематики", { noIndent: true, afterSpacing: 40 }),
  p("  4.3 Комплексное тестирование системы", { noIndent: true, afterSpacing: 60 }),
  p("ЗАКЛЮЧЕНИЕ", { noIndent: true, afterSpacing: 60 }),
  p("СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ", { noIndent: true, afterSpacing: 60 }),
  new Paragraph({ children: [new PageBreak()] })
);

// ===== ВВЕДЕНИЕ =====
children.push(
  heading1("ВВЕДЕНИЕ"),

  p("Современная промышленность переживает период активной роботизации производственных процессов. По данным Международной федерации робототехники (IFR), мировой рынок промышленных роботов ежегодно растёт на 10\u201315%, а внедрение роботов-манипуляторов становится ключевым фактором повышения производительности и качества продукции. Параллельно с промышленными решениями стоимостью в десятки тысяч долларов развивается сегмент доступных образовательных и исследовательских манипуляторов, построенных на базе серийных сервоприводов."),

  p("Сервоприводы серии ST3215 представляют собой компактные цифровые актуаторы с 12-битным позиционированием (4096 дискретных позиций), протоколом UART и диапазоном вращения 360 градусов. Они позволяют собрать полноценный 6-осевой манипулятор с достаточной точностью для образовательных и лёгких промышленных задач. Однако для эффективного использования такого манипулятора необходимо комплексное программное обеспечение, включающее кинематическую модель, алгоритмы обратной кинематики, систему управления моторами и удобный графический интерфейс."),

  p([{ text: "Целью дипломной работы ", bold: true }, { text: "является разработка многоплатформенного программного обеспечения для управления 6-осевым роботом-манипулятором на базе сервоприводов ST3215, охватывающего три независимых клиентских уровня (Desktop, Web, ROS2) с общим ядром кинематики и управления, а также набор высокоуровневых программ для типовых задач манипулятора." }]),

  p("Для достижения поставленной цели были сформулированы следующие задачи:"),

  p("\u2014 построить кинематическую модель 6-осевого робота по методу Денавита\u2013Хартенберга;", { noIndent: true }),
  p("\u2014 реализовать алгоритм обратной кинематики на основе метода демпфированных наименьших квадратов;", { noIndent: true }),
  p("\u2014 разработать систему управления сервоприводами ST3215 через протокол UART;", { noIndent: true }),
  p("\u2014 создать Desktop-приложение с GUI в стиле промышленных контроллеров FANUC (Tkinter);", { noIndent: true }),
  p("\u2014 разработать Web-интерфейс с REST API и WebSocket для удалённого управления (FastAPI);", { noIndent: true }),
  p("\u2014 реализовать ROS2-пакет с нодами управления, мониторинга и сервисом обратной кинематики;", { noIndent: true }),
  p("\u2014 создать набор программ для типовых задач: захват объекта, рисование траектории, калибровка, сканирование;", { noIndent: true }),
  p("\u2014 интегрировать симуляцию в среде MuJoCo для будущего обучения с подкреплением;", { noIndent: true }),
  p("\u2014 провести комплексное тестирование разработанного ПО.", { noIndent: true }),

  p([{ text: "Объектом исследования ", bold: true }, { text: "является 6-осевой робот-манипулятор, построенный на базе шести сервоприводов ST3215 с длинами звеньев L0\u2009=\u200919, L1\u2009=\u2009134, L2\u2009=\u200995, L3\u2009=\u200934, L4\u2009=\u200935, L5\u2009=\u20090 мм и максимальной досягаемостью 317 мм." }]),

  p([{ text: "Предметом исследования ", bold: true }, { text: "являются алгоритмы кинематики, методы численного решения обратной кинематической задачи и архитектура программного обеспечения для управления манипулятором." }]),

  p([{ text: "Практическая значимость ", bold: true }, { text: "работы состоит в создании готового к использованию многоплатформенного комплекса: Desktop-приложение обеспечивает полный локальный контроль, Web-интерфейс позволяет управлять роботом с любого устройства без установки ПО, ROS2-пакет открывает интеграцию с промышленными робototехническими системами, а библиотека задач (pick-and-place, рисование, калибровка, сканирование) демонстрирует практическое применение разработанных алгоритмов." }]),

  new Paragraph({ children: [new PageBreak()] })
);

// ===== ГЛАВА 1 =====
children.push(
  heading1("ГЛАВА 1. ТЕОРЕТИЧЕСКИЕ ОСНОВЫ"),

  heading2("1.1 Кинематика робота-манипулятора"),

  p("Робот-манипулятор \u2014 это механическое устройство, состоящее из последовательно соединённых звеньев (links), связанных между собой суставами (joints). Каждый сустав обеспечивает одну степень свободы (DOF \u2014 Degree of Freedom). Рассматриваемый робот имеет 6 вращательных суставов (revolute joints), что обеспечивает 6 степеней свободы \u2014 минимальное количество для произвольного позиционирования и ориентирования конечного эффектора (инструмента) в трёхмерном пространстве."),

  p([{ text: "Прямая кинематика (Forward Kinematics, FK) ", bold: true }, { text: "\u2014 это задача определения положения и ориентации конечного эффектора по заданным углам всех суставов. Для последовательного манипулятора решение FK всегда существует и единственно." }]),

  heading3("Метод Денавита\u2013Хартенберга"),

  p("Для систематического описания кинематики последовательных манипуляторов используется метод Денавита\u2013Хартенберга (DH), предложенный в 1955 году. Метод определяет систему координат для каждого звена с помощью четырёх параметров:"),

  p("\u2014 \u03B8\u1D62 (theta) \u2014 угол поворота вокруг оси Z\u1D62\u208B\u2081 (переменная для вращательных суставов);", { noIndent: true }),
  p("\u2014 d\u1D62 \u2014 смещение вдоль оси Z\u1D62\u208B\u2081;", { noIndent: true }),
  p("\u2014 a\u1D62 \u2014 длина звена (расстояние вдоль оси X\u1D62);", { noIndent: true }),
  p("\u2014 \u03B1\u1D62 (alpha) \u2014 угол закручивания между осями Z\u1D62\u208B\u2081 и Z\u1D62.", { noIndent: true }),

  p("Матрица однородного преобразования для i-го сустава имеет вид:"),

  formula("T\u1D62 = Rz(\u03B8\u1D62) \u00B7 Tz(d\u1D62) \u00B7 Tx(a\u1D62) \u00B7 Rx(\u03B1\u1D62)", "1.1"),

  p("В развёрнутом виде матрица 4\u00D74:"),

  formula("T\u1D62 = | cos\u03B8  \u2212sin\u03B8\u00B7cos\u03B1   sin\u03B8\u00B7sin\u03B1   a\u00B7cos\u03B8 |", "1.2"),
  new Paragraph({ spacing: { after: 40, line: 360 }, alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "     | sin\u03B8   cos\u03B8\u00B7cos\u03B1  \u2212cos\u03B8\u00B7sin\u03B1   a\u00B7sin\u03B8 |", font: FONT, size: 28, italics: true })] }),
  new Paragraph({ spacing: { after: 40, line: 360 }, alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "     |   0       sin\u03B1          cos\u03B1          d      |", font: FONT, size: 28, italics: true })] }),
  new Paragraph({ spacing: { after: 120, line: 360 }, alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "     |   0         0              0            1      |", font: FONT, size: 28, italics: true })] }),

  p("Полная трансформация от базы до конечного эффектора определяется как произведение всех шести матриц:"),
  formula("T\u2080\u2076 = T\u2081 \u00B7 T\u2082 \u00B7 T\u2083 \u00B7 T\u2084 \u00B7 T\u2085 \u00B7 T\u2086", "1.3"),

  p("Позиция конечного эффектора извлекается из последнего столбца результирующей матрицы:"),
  formula("x = T\u2080\u2076[0][3],   y = T\u2080\u2076[1][3],   z = T\u2080\u2076[2][3]", "1.4"),

  p("Для рассматриваемого робота DH-параметры приведены в таблице 1.1."),
  emptyLine(),
  tableCaption("Таблица 1.1 \u2014 DH-параметры 6-осевого робота"),
  makeTable(
    ["Сустав", "d (мм)", "a (мм)", "\u03B1 (рад)", "Описание"],
    [
      ["J1", "19", "0", "\u03C0/2", "База"],
      ["J2", "0", "134", "0", "Плечо 1"],
      ["J3", "0", "95", "0", "Плечо 2"],
      ["J4", "0", "34", "\u03C0/2", "Локоть"],
      ["J5", "0", "35", "\u2212\u03C0/2", "Кисть 1"],
      ["J6", "0", "0", "0", "Кисть 2"],
    ],
    [1400, 1200, 1200, 1200, 2000]
  ),
  emptyLine(),

  p("При нулевых углах всех суставов (\u03B8\u2081 = \u03B8\u2082 = ... = \u03B8\u2086 = 0\u00B0) конечный эффектор находится в точке (298.0, 0.0, 19.0) мм, что соответствует полностью выпрямленному положению робота вдоль оси X."),

  heading2("1.2 Обратная кинематика"),

  p([{ text: "Обратная кинематика (Inverse Kinematics, IK) ", bold: true }, { text: "\u2014 это задача определения углов суставов \u03B8\u2081...\u03B8\u2086, при которых конечный эффектор достигает заданной позиции (x, y, z) в пространстве. В отличие от FK, задача IK может не иметь решения (точка за пределами досягаемости) или иметь множество решений (различные конфигурации руки)." }]),

  heading3("Якобиан манипулятора"),

  p("Якобиан J \u2014 это матрица размерности 3\u00D76, связывающая малые изменения углов суставов \u03B4\u03B8 с малыми изменениями позиции конечного эффектора \u03B4p:"),
  formula("\u03B4p = J \u00B7 \u03B4\u03B8", "1.5"),

  p("Элементы якобиана вычисляются как частные производные позиции по углам:"),
  formula("J[i][j] = \u2202p\u1D62 / \u2202\u03B8\u2C7C, где i \u2208 {x, y, z}, j \u2208 {1...6}", "1.6"),

  p("В данной работе якобиан вычисляется численно методом центральных конечных разностей с шагом \u0394 = 0.5\u00B0:"),
  formula("J[i][j] \u2248 (p\u1D62(\u03B8\u2C7C + \u0394) \u2212 p\u1D62(\u03B8\u2C7C \u2212 \u0394)) / (2\u0394)", "1.7"),

  heading3("Метод демпфированных наименьших квадратов (DLS)"),

  p("Для решения IK используется метод Damped Least Squares (Levenberg\u2013Marquardt), который обеспечивает устойчивость вблизи сингулярных конфигураций. Обновление углов на каждой итерации:"),

  formula("\u03B4\u03B8 = J\u1D40 \u00B7 (J \u00B7 J\u1D40 + \u03BB\u00B2 \u00B7 I)\u207B\u00B9 \u00B7 e", "1.8"),

  p("где e = p\u209C\u2090\u1D63\u1D4D\u1D49\u209C \u2212 p\u209C\u1D58\u1D63\u1D63\u1D49\u2099\u209C \u2014 вектор ошибки позиции (3\u00D71), \u03BB = 1.0 \u2014 параметр демпфирования, I \u2014 единичная матрица 3\u00D73. По сравнению с простым методом псевдообратной матрицы (\u03BB = 0), DLS обеспечивает конечные значения \u03B4\u03B8 даже при вырождении якобиана."),

  heading3("Множественные начальные приближения"),

  p("Метод DLS является локальным и может сходиться к различным решениям в зависимости от начальной конфигурации. Для повышения надёжности алгоритм использует 11 предопределённых начальных приближений, покрывающих различные характерные позы робота: вытянутая, согнутая, повёрнутая и т.д. Угол J1 (база) для каждого приближения корректируется аналитически по формуле:"),
  formula("\u03B8\u2081 = atan2(y, x)", "1.9"),

  p("Из всех найденных решений выбирается то, которое обеспечивает минимальную ошибку позиционирования. Типичная точность составляет менее 1 мм при 300 итерациях."),

  heading2("1.3 Сервоприводы ST3215"),

  p("Feetech ST3215 \u2014 цифровой сервопривод с протоколом управления через шину UART (TTL, полудуплекс). Основные характеристики:"),

  p("\u2014 разрешение позиционирования: 12 бит (4096 дискретных позиций, 0\u20134095);", { noIndent: true }),
  p("\u2014 диапазон вращения: 360\u00B0;", { noIndent: true }),
  p("\u2014 максимальная скорость: 3400 шагов/с;", { noIndent: true }),
  p("\u2014 встроенные датчики: температура, напряжение, ток, нагрузка;", { noIndent: true }),
  p("\u2014 протокол: пакетный, бинарный, с контрольной суммой.", { noIndent: true }),

  p("Конвертация между углом в градусах и позицией мотора выполняется по формулам:"),
  formula("angle = (position / 4095) \u00D7 360 \u2212 180", "1.10"),
  formula("position = ((angle + 180) / 360) \u00D7 4095", "1.11"),

  p("Таким образом, позиция 0 соответствует углу \u2212180\u00B0, позиция 2048 \u2014 углу 0\u00B0, позиция 4095 \u2014 углу +180\u00B0."),

  p("Для некоторых суставов физическая установка мотора требует инверсии направления. В конфигурации задаётся флаг inverted: при инверсии позиция зеркалится по формуле:"),
  formula("position\u2032 = 4095 \u2212 position", "1.12"),

  heading2("1.4 Симуляция в MuJoCo"),

  p("MuJoCo (Multi-Joint dynamics with Contact) \u2014 высокопроизводительный физический движок, разработанный Е. Тодоровым (2012) для задач робототехники и обучения с подкреплением (Reinforcement Learning, RL). Ключевые особенности:"),

  p("\u2014 точная симуляция контактной динамики, трения и гравитации;", { noIndent: true }),
  p("\u2014 формат описания моделей MJCF (MuJoCo XML);", { noIndent: true }),
  p("\u2014 встроенный рендеринг RGB и Depth изображений с произвольных камер;", { noIndent: true }),
  p("\u2014 привязка Python через пакет mujoco.", { noIndent: true }),

  p("В рамках данной работы MuJoCo используется для создания виртуальной копии робота (digital twin) с точными геометрическими параметрами, двухпальцевым гриппером, объектами для захвата и камерами. Среда RobotEnv предоставляет Gym-подобный интерфейс (observation, action, reward) для будущей интеграции с алгоритмами RL."),

  new Paragraph({ children: [new PageBreak()] })
);

// ===== ГЛАВА 2 =====
children.push(
  heading1("ГЛАВА 2. АРХИТЕКТУРА ПРОГРАММНОГО ОБЕСПЕЧЕНИЯ"),

  heading2("2.1 Многоплатформенная архитектура системы"),

  p("Программный комплекс разработан по многоплатформенной архитектуре, разделяющей платформо-независимое ядро и три клиентских слоя: Desktop (локальный GUI), Web (браузерный интерфейс) и ROS2 (интеграция с роботизированной экосистемой). Такой подход позволяет использовать один и тот же алгоритмический код кинематики и управления моторами на любой платформе без дублирования."),

  emptyLine(),
  tableCaption("Таблица 2.1 \u2014 Многоплатформенная структура проекта"),
  makeTable(
    ["Слой", "Директория", "Назначение"],
    [
      ["Общий (shared)", "app/", "Модели данных, кинематика, контроллеры, сервисы, события"],
      ["Desktop",        "desktop/", "Tkinter GUI в стиле FANUC, локальное подключение по USB"],
      ["Web",            "web/",     "FastAPI REST API + WebSocket + HTML/JS браузерный клиент"],
      ["ROS2",           "ros2/",    "Пакет robot_control: три ноды для интеграции с ROS2"],
      ["Программы",      "programs/","Высокоуровневые задачи: захват, рисование, калибровка"],
    ],
    [2000, 2200, 4800]
  ),
  emptyLine(),

  p("Все платформы импортируют общий слой (app/) через пакет shared/, который реэкспортирует публичные символы. Такая схема позволяет в дальнейшем перенести общий код в отдельный pip-пакет без изменения клиентских слоёв. Поток данных в системе: платформа отправляет команды через MotorController \u2192 ST3215 UART \u2192 сервоприводы; телеметрия поступает обратно через MotorMonitor \u2192 EventBus \u2192 обработчики платформы."),

  heading2("2.2 Общий слой (shared)"),

  p("Общий слой реализован в директории app/ и содержит весь платформо-независимый код. Слой организован по принципу разделения ответственности (Separation of Concerns):"),

  p([{ text: "models/ ", bold: true }, { text: "\u2014 модели данных MotorData, JointState, RobotState, ProgramBlock. MotorData хранит состояние одного сервопривода: position (0\u20134095), temperature (\u00B0C), voltage, current, load; свойство status вычисляет статус OK/WARNING/ERROR по порогам. Kinematics содержит классы RobotKinematics6DOF и InverseKinematics6DOF с DH-параметрами реального робота." }]),

  p([{ text: "controllers/ ", bold: true }, { text: "\u2014 MotorController обеспечивает потокобезопасное управление сервоприводами через threading.Lock: connect/disconnect, scan_motors, move_joint, move_all_joints, emergency_stop, get_motor_data. MotorMonitor опрашивает все моторы каждые 0.5 секунды в фоновом потоке." }]),

  p([{ text: "services/ ", bold: true }, { text: "\u2014 KinematicsService кэширует результаты FK/IK и проверяет досягаемость. RobotService синхронизирует состояние робота. ProgramService управляет блочными программами." }]),

  p([{ text: "core/ ", bold: true }, { text: "\u2014 шина событий EventBus (паттерн publish\u2013subscribe), контейнер зависимостей DependencyContainer, абстрактный BaseService с жизненным циклом initialize \u2192 start \u2192 stop." }]),

  p([{ text: "utils/ ", bold: true }, { text: "\u2014 ConfigManager загружает/сохраняет JSON-конфигурацию с версионированием (до 5 резервных копий). Logger обеспечивает структурированное логирование. ProgramExecutor выполняет блочные программы в синхронном и асинхронном режимах." }]),

  heading2("2.3 Desktop приложение"),

  p("Desktop-слой (директория desktop/) предназначен для прямого управления роботом с компьютера оператора через USB-кабель. Точка входа desktop/main.py запускает главное окно RobotControlGUI."),

  p("GUI реализован на Tkinter с визуальной стилизацией под промышленные контроллеры FANUC: тёмная цветовая схема (#1a1a2e \u2014 фон, #16213e \u2014 панели, #00ff88 \u2014 статус OK, #ff9500 \u2014 предупреждения, #ff4444 \u2014 ошибки). Интерфейс содержит вкладки:"),

  p([{ text: "1. Ручное управление ", bold: true }, { text: "\u2014 выбор сустава (J1\u2013J6), кнопки хода, слайдер скорости (1\u2013100%), команды Home/Center/Torque ON\u2013OFF." }]),
  p([{ text: "2. 3D-кинематика ", bold: true }, { text: "\u2014 6 полей ввода углов, 3D-визуализация робота через Matplotlib, кнопка применения к реальным моторам." }]),
  p([{ text: "3. Блочное программирование ", bold: true }, { text: "\u2014 палитра блоков (движение, ожидание, управление моментом), холст для составления программы, запуск/пауза/стоп." }]),
  p([{ text: "4. Мониторинг ", bold: true }, { text: "\u2014 нижняя панель: позиция, температура, напряжение, ток, нагрузка, статус всех 6 моторов в реальном времени." }]),

  heading2("2.4 Web интерфейс"),

  p("Web-слой (директория web/) обеспечивает удалённый доступ к роботу через браузер без установки дополнительного ПО. Сервер реализован на FastAPI (Python 3.12+), что обеспечивает автоматическую генерацию OpenAPI-документации и высокую производительность благодаря асинхронной обработке запросов."),

  p("Архитектура web-слоя включает три компонента:"),

  p([{ text: "REST API (web/api/routes.py) ", bold: true }, { text: "\u2014 endpoints: GET /api/status (текущее состояние), POST /api/connect (подключение к порту), POST /api/disconnect, POST /api/move (команда движения), POST /api/stop (аварийная остановка), POST /api/ik (решение обратной кинематики по целевым координатам XYZ)." }]),

  p([{ text: "WebSocket (web/api/websocket.py) ", bold: true }, { text: "\u2014 endpoint WS /ws транслирует телеметрию моторов всем подключённым клиентам на частоте 5 Гц. Используется паттерн broadcast: каждое обновление MotorMonitor преобразуется в JSON и отправляется через asyncio всем активным соединениям." }]),

  p([{ text: "Веб-клиент (web/static/index.html) ", bold: true }, { text: "\u2014 одностраничное приложение на чистом HTML/JS без зависимостей. Содержит панель подключения, ручное управление суставами, форму IK, таблицу телеметрии в реальном времени и лог событий. Данные телеметрии обновляются через WebSocket без перезагрузки страницы." }]),

  heading2("2.5 ROS2 интеграция"),

  p("ROS2-слой (директория ros2/) реализован как стандартный пакет ament_python с именем robot_control. Пакет содержит три независимых ноды, запускаемых файлом ros2/launch/robot.launch.py:"),

  emptyLine(),
  tableCaption("Таблица 2.2 \u2014 ROS2 ноды пакета robot_control"),
  makeTable(
    ["Нода", "Топики/Сервисы", "Назначение"],
    [
      ["robot_node",       "/robot/joint_states, /robot/joint_cmd, /robot/stop", "Основное управление: публикует JointState, принимает команды движения"],
      ["monitor_node",     "/robot/diagnostics, /robot/temperature, /robot/alarms", "Мониторинг: публикует диагностику и сигналы тревоги на частоте 1 Гц"],
      ["ik_service_node",  "/robot/ik/request, /robot/ik/response", "Сервис IK: принимает JSON-запрос {x,y,z}, возвращает углы суставов"],
    ],
    [2400, 3200, 3400]
  ),
  emptyLine(),

  p("Нода robot_node принимает параметры ROS2: port (COM3 по умолчанию), baudrate (1\u2009000\u2009000), monitor_rate_hz (10.0). Состояния суставов публикуются в формате sensor_msgs/JointState с позициями в радианах. Команды движения принимаются в формате trajectory_msgs/JointTrajectoryPoint. Для экстренной остановки используется топик /robot/stop с пустым сообщением (std_msgs/Empty), что гарантирует мгновенную реакцию независимо от текущего состояния очереди."),

  heading2("2.6 Система программ для задач"),

  p("Директория programs/ содержит высокоуровневые программы для конкретных задач манипулятора. Все программы наследуют абстрактный класс BaseProgram, который инкапсулирует общую логику: управление остановкой через threading.Event, вспомогательные методы для движения (_move_joint, _move_all, _go_to_xyz, _go_home), ожидание с проверкой стоп-флага (_wait), логирование через callback on_step."),

  emptyLine(),
  tableCaption("Таблица 2.3 \u2014 Программы для задач робота"),
  makeTable(
    ["Программа", "Файл", "Описание"],
    [
      ["Wave Demo",      "programs/wave_demo.py",      "Синусоидальная волновая демонстрация на суставах плеча и основания"],
      ["Pick and Place", "programs/pick_and_place.py", "Захват объекта в точке pick и перемещение в точку place через IK"],
      ["Draw Square",    "programs/draw_square.py",    "Трассировка квадратной траектории в плоскости XY через IK"],
      ["Calibration",    "programs/calibration.py",   "Автоматическая калибровка: проверка диапазонов, измерение ошибки позиционирования"],
      ["Spiral Scan",    "programs/spiral_scan.py",   "Спиральное сканирование рабочей зоны для картографирования пространства"],
    ],
    [2400, 3200, 3400]
  ),
  emptyLine(),

  p("Каждая программа запускается как автономный скрипт с аргументами командной строки (argparse), так и программно через Python API: prog = PickAndPlace(controller, cycles=5); prog.on_step = print; prog.run(). Метод stop() устанавливает флаг прерывания, который программа проверяет между шагами, обеспечивая корректное завершение без обрыва движения на полуходу."),

  new Paragraph({ children: [new PageBreak()] })
);

// ===== ГЛАВА 3 =====
children.push(
  heading1("ГЛАВА 3. РЕАЛИЗАЦИЯ КЛЮЧЕВЫХ АЛГОРИТМОВ"),

  heading2("3.1 Реализация прямой кинематики"),

  p("Класс RobotKinematics6DOF реализует прямую кинематику через DH-матрицы. Инициализация DH-параметров:"),
  ...codeBlock([
    "class RobotKinematics6DOF:",
    "    L0, L1, L2, L3, L4, L5 = 19.0, 134.0, 95.0, 34.0, 35.0, 0.0",
    "",
    "    def __init__(self):",
    "        # DH: [d, a, alpha]",
    "        self.dh_params = [",
    "            (self.L0, 0.0, math.pi/2),   # J1: база",
    "            (0.0, self.L1, 0.0),          # J2: плечо 1",
    "            (0.0, self.L2, 0.0),          # J3: плечо 2",
    "            (0.0, self.L3, math.pi/2),    # J4: локоть",
    "            (0.0, self.L4, -math.pi/2),   # J5: кисть 1",
    "            (self.L5, 0.0, 0.0),          # J6: кисть 2",
    "        ]",
  ]),
  emptyLine(),

  p("Метод _dh_matrix формирует матрицу 4\u00D74 по формуле (1.2):"),
  ...codeBlock([
    "def _dh_matrix(self, theta, d, a, alpha):",
    "    ct, st = math.cos(theta), math.sin(theta)",
    "    ca, sa = math.cos(alpha), math.sin(alpha)",
    "    return [",
    "        [ct, -st*ca,  st*sa,  a*ct],",
    "        [st,  ct*ca, -ct*sa,  a*st],",
    "        [0,   sa,     ca,     d   ],",
    "        [0,   0,      0,      1   ]]",
  ]),
  emptyLine(),

  p("Прямая кинематика вычисляется последовательным умножением матриц:"),
  ...codeBlock([
    "def forward_kinematics(self, angles_deg):",
    "    theta = [math.radians(a) for a in angles_deg]",
    "    T = self._identity_matrix()",
    "    for i in range(6):",
    "        T_i = self._dh_matrix(theta[i], *self.dh_params[i])",
    "        T = self._matrix_multiply(T, T_i)",
    "        positions.append((T[0][3], T[1][3], T[2][3]))",
  ]),
  emptyLine(),

  p("Результаты расчёта для двух характерных конфигураций представлены в таблице 3.1."),
  emptyLine(),
  tableCaption("Таблица 3.1 \u2014 Позиции суставов при нулевых углах"),
  makeTable(
    ["Сустав", "X (мм)", "Y (мм)", "Z (мм)"],
    [
      ["База", "0.0", "0.0", "0.0"],
      ["J1", "0.0", "0.0", "19.0"],
      ["J2", "134.0", "0.0", "19.0"],
      ["J3", "229.0", "0.0", "19.0"],
      ["J4", "263.0", "0.0", "19.0"],
      ["J5", "298.0", "0.0", "19.0"],
      ["J6 (EE)", "298.0", "0.0", "19.0"],
    ],
    [1800, 1600, 1600, 1600]
  ),
  emptyLine(),

  heading2("3.2 Реализация обратной кинематики"),

  p("Класс InverseKinematics6DOF реализует IK методом Damped Least Squares. Алгоритм включает три этапа: проверку досягаемости, генерацию начальных приближений и численную оптимизацию."),

  p("Численное вычисление якобиана:"),
  ...codeBlock([
    "def _compute_jacobian(self, angles, delta=0.5):",
    "    J = np.zeros((3, 6))",
    "    for j in range(6):",
    "        a_plus, a_minus = list(angles), list(angles)",
    "        a_plus[j] += delta",
    "        a_minus[j] -= delta",
    "        p_plus = np.array(self.kinematics.get_end_effector_position(a_plus))",
    "        p_minus = np.array(self.kinematics.get_end_effector_position(a_minus))",
    "        J[:, j] = (p_plus - p_minus) / (2 * delta)",
    "    return J  # 3x6, единицы: мм/градус",
  ]),
  emptyLine(),

  p("Основной цикл оптимизации DLS:"),
  ...codeBlock([
    "def _numerical_solve(self, x, y, z, initial_angles, max_iter, tol):",
    "    angles = list(initial_angles)",
    "    damping = 1.0",
    "    for iteration in range(max_iter):",
    "        pos = self.kinematics.get_end_effector_position(angles)",
    "        error = np.array([x - pos[0], y - pos[1], z - pos[2]])",
    "        if np.linalg.norm(error) < tol:",
    "            return angles",
    "        J = self._compute_jacobian(angles)",
    "        JJT = J @ J.T",
    "        damped = JJT + (damping**2) * np.eye(3)",
    "        delta_theta = J.T @ np.linalg.solve(damped, error)",
    "        # delta_theta уже в градусах (якобиан в мм/градус)",
    "        for i in range(6):",
    "            angles[i] += delta_theta[i] * step",
    "            angles[i] = max(-179, min(179, angles[i]))",
  ]),
  emptyLine(),

  p("Результаты round-trip тестирования (FK \u2192 IK \u2192 FK) представлены в таблице 3.2."),
  emptyLine(),
  tableCaption("Таблица 3.2 \u2014 Результаты round-trip тестирования IK"),
  makeTable(
    ["Исходные углы (\u00B0)", "FK позиция (мм)", "Ошибка IK (мм)", "Результат"],
    [
      ["[0, 0, 0, 0, 0, 0]", "(298.0, 0.0, 19.0)", "0.50", "OK"],
      ["[45, 0, 0, 0, 0, 0]", "(210.7, 210.7, 19.0)", "0.50", "OK"],
      ["[0, 30, 0, 0, 0, 0]", "(258.1, 0.0, 168.0)", "0.50", "OK"],
      ["[0, 0, \u221230, 0, 0, 0]", "(276.0, 0.0, \u221263.0)", "0.49", "OK"],
      ["[30, \u221220, 15, \u221210, 5, 0]", "(250.1, 140.9, \u221252.9)", "0.50", "OK"],
      ["[\u221260, 10, \u221225, \u221215, 20, 10]", "(130.5, \u2212249.9, \u221215.8)", "0.40", "OK"],
      ["[90, \u221230, 20, \u221240, 0, 0]", "(0.0, 254.0, \u2212117.4)", "0.42", "OK"],
      ["[0, 45, \u221245, \u221230, 0, 0]", "(249.5, 0.0, 79.3)", "0.39", "OK"],
      ["[\u221245, \u221210, 30, \u221260, 45, \u221220]", "(170.8, \u2212205.8, \u22129.5)", "0.43", "OK"],
      ["[0, 0, 0, \u221230, 0, 0]", "(288.8, 0.0, \u221215.5)", "0.46", "OK"],
    ],
    [2500, 2600, 1300, 1000]
  ),
  emptyLine(),

  p("Все 10 конфигураций успешно решены с ошибкой менее 0.5 мм, что подтверждает корректность реализации алгоритма."),

  heading2("3.3 Управление моторами ST3215"),

  p("Взаимодействие с сервоприводами осуществляется через библиотеку st3215, предоставляющую класс ST3215. Подключение и основные операции:"),
  ...codeBlock([
    "from st3215 import ST3215",
    "",
    "servo = ST3215(device='COM3')      # подключение",
    "ids = servo.ListServos()            # сканирование шины",
    "servo.MoveTo(1, 2048, speed=100)    # движение мотора 1",
    "pos = servo.ReadPosition(1)         # чтение позиции",
    "servo.StopServo(1)                  # остановка",
  ]),
  emptyLine(),

  p("Маппинг суставов к моторам задаётся в конфигурации с поддержкой инверсии направления:"),
  emptyLine(),
  tableCaption("Таблица 3.3 \u2014 Маппинг суставов и моторов"),
  makeTable(
    ["Сустав", "Motor ID", "Название", "Инвертирован"],
    [
      ["J0", "1", "База", "Да"],
      ["J1", "2", "Плечо 1", "Нет"],
      ["J2", "4", "Плечо 2", "Да"],
      ["J3", "5", "Локоть", "Нет"],
      ["J4", "3", "Кисть 1", "Нет"],
      ["J5", "6", "Кисть 2", "Нет"],
    ],
    [1400, 1400, 2200, 2000]
  ),
  emptyLine(),

  heading2("3.4 Безопасный визуализатор"),

  p("Модуль SafeMotorVisualizer обеспечивает безопасное тестирование робота с ограничениями:"),

  p("\u2014 скорость ограничена до 100 шагов/с (4% от максимальной 2400);", { noIndent: true }),
  p("\u2014 углы ограничены безопасными диапазонами для предотвращения столкновений;", { noIndent: true }),
  p("\u2014 каждое движение требует подтверждения оператором;", { noIndent: true }),
  p("\u2014 кнопка экстренной остановки (StopServo для всех моторов).", { noIndent: true }),
  emptyLine(),

  tableCaption("Таблица 3.4 \u2014 Безопасные ограничения углов"),
  makeTable(
    ["Сустав", "Мин. (\u00B0)", "Макс. (\u00B0)", "Описание"],
    [
      ["J1 (База)", "\u2212120", "+120", "Предотвращение перекрута"],
      ["J2 (Плечо 1)", "\u221245", "+90", "Предотвращение столкновения"],
      ["J3 (Плечо 2)", "\u221290", "+45", "Предотвращение столкновения"],
      ["J4 (Локоть)", "\u2212120", "0", "Безопасный диапазон"],
      ["J5 (Кисть 1)", "\u221290", "+90", "Стандартный диапазон"],
      ["J6 (Кисть 2)", "\u221290", "+90", "Стандартный диапазон"],
    ],
    [2000, 1200, 1200, 2600]
  ),
  emptyLine(),

  p("Визуализатор поддерживает указание целевой точки в координатах (X, Y, Z) с автоматическим решением IK, клик по 3D-визуализации для выбора точки и систему маршрутных точек (waypoints) с последовательным обходом."),

  heading2("3.5 Симуляция в MuJoCo"),

  p("Модуль mujoco_robot_sim.py генерирует MJCF-модель робота программно на основе DH-параметров. Модель включает:"),

  p("\u2014 6 вращательных суставов с корректными осями и ограничениями;", { noIndent: true }),
  p("\u2014 двухпальцевый гриппер с индивидуальным управлением каждым пальцем;", { noIndent: true }),
  p("\u2014 4 объекта для захвата (кубики и цилиндр) с реалистичным трением;", { noIndent: true }),
  p("\u2014 рабочий стол как поверхность;", { noIndent: true }),
  p("\u2014 4 камеры: сверху, спереди, сбоку, на гриппере (eye-in-hand);", { noIndent: true }),
  p("\u2014 сенсоры: положения суставов, позиция конечного эффектора.", { noIndent: true }),

  p("Класс RobotEnv предоставляет Gym-подобный интерфейс для RL-обучения:"),
  ...codeBlock([
    "class RobotEnv:",
    "    def reset(self) -> Dict:   # сброс, возврат наблюдения",
    "    def step(self, action) -> Tuple[obs, reward, done, info]:",
    "        # action: [j0..j5, gripper] - углы + гриппер",
    "        # obs: {rgb, depth, joint_angles, ee_pos, ...}",
    "        # reward: -distance_to_object + grasp_bonus",
  ]),
  emptyLine(),

  new Paragraph({ children: [new PageBreak()] })
);

// ===== ГЛАВА 4 =====
children.push(
  heading1("ГЛАВА 4. РЕЗУЛЬТАТЫ И ТЕСТИРОВАНИЕ"),

  heading2("4.1 Тестирование прямой кинематики"),

  p("Для верификации FK модели были проведены тесты базовых вращений. Результаты представлены в таблице 4.1."),
  emptyLine(),
  tableCaption("Таблица 4.1 \u2014 Тестирование базовых вращений FK"),
  makeTable(
    ["Углы (\u00B0)", "Ожидаемый EE (мм)", "Фактический EE (мм)", "Результат"],
    [
      ["[0,0,0,0,0,0]", "(298, 0, 19)", "(298.0, 0.0, 19.0)", "OK"],
      ["[90,0,0,0,0,0]", "(0, 298, 19)", "(0.0, 298.0, 19.0)", "OK"],
      ["[\u221290,0,0,0,0,0]", "(0, \u2212298, 19)", "(0.0, \u2212298.0, 19.0)", "OK"],
      ["[180,0,0,0,0,0]", "(\u2212298, 0, 19)", "(\u2212298.0, 0.0, 19.0)", "OK"],
    ],
    [2000, 2200, 2200, 1000]
  ),
  emptyLine(),

  p("Все базовые тесты FK пройдены успешно. Вращение базы (J1) корректно поворачивает весь манипулятор вокруг вертикальной оси Z, вращение плеча (J2) корректно поднимает/опускает руку."),

  heading2("4.2 Тестирование обратной кинематики"),

  p("Тестирование IK проводилось в два этапа: round-trip (FK\u2192IK\u2192FK) и решение для произвольных точек в рабочем пространстве."),

  p("Результаты round-trip представлены в таблице 3.2 (все 10 конфигураций \u2014 ошибка < 0.5 мм). Результаты для произвольных точек \u2014 в таблице 4.2."),
  emptyLine(),
  tableCaption("Таблица 4.2 \u2014 Тестирование IK для произвольных точек"),
  makeTable(
    ["Целевая точка (мм)", "Описание", "Ошибка (мм)", "Результат"],
    [
      ["(100, 0, 150)", "перед собой, высоко", "0.7", "OK"],
      ["(150, 50, 100)", "вправо-вперёд", "0.2", "OK"],
      ["(200, 0, 50)", "далеко вперёд, низко", "0.2", "OK"],
      ["(50, 50, 200)", "близко, высоко", "0.5", "OK"],
      ["(100, 100, 100)", "диагональ", "0.9", "OK"],
      ["(0, 150, 100)", "точно вбок", "0.3", "OK"],
      ["(\u2212100, 0, 150)", "назад, высоко", "1.0", "OK"],
      ["(80, 0, 250)", "вверх", "0.7", "OK"],
      ["(250, 0, 19)", "далеко, уровень базы", "0.9", "OK"],
      ["(50, 0, 50)", "близко, низко", "0.7", "OK"],
    ],
    [2200, 2200, 1500, 1100]
  ),
  emptyLine(),

  p("Все 10 произвольных точек в рабочем пространстве успешно достигнуты с ошибкой менее 1 мм. Точки за пределами досягаемости (расстояние > 317 мм) корректно отклоняются с возвратом None."),

  heading2("4.3 Комплексное тестирование системы"),

  p("Комплексное тестирование включало:"),
  p("\u2014 подключение к 6 реальным моторам ST3215 через COM-порт \u2014 успешно;", { noIndent: true }),
  p("\u2014 сканирование шины (ListServos) \u2014 все 6 моторов обнаружены;", { noIndent: true }),
  p("\u2014 движение каждого сустава в безопасном режиме \u2014 соответствие визуализации;", { noIndent: true }),
  p("\u2014 3D-визуализация корректно отображает конфигурацию робота;", { noIndent: true }),
  p("\u2014 блочное программирование: последовательность из 4 блоков выполнена корректно;", { noIndent: true }),
  p("\u2014 MuJoCo симуляция: модель загружена (12 суставов, 8 актуаторов), гриппер работает, рендеринг RGB (640\u00D7480) и Depth выполнен успешно.", { noIndent: true }),

  p("Мониторинг в реальном времени подтвердил стабильную работу моторов: температура не превышала 45\u00B0C, напряжение стабильно 7.2В, нагрузка при движении не превышала 30%."),

  new Paragraph({ children: [new PageBreak()] })
);

// ===== ЗАКЛЮЧЕНИЕ =====
children.push(
  heading1("ЗАКЛЮЧЕНИЕ"),

  p("В результате выполнения дипломной работы было разработано комплексное программное обеспечение для управления 6-осевым роботом-манипулятором на базе сервоприводов ST3215. Основные результаты:"),

  p("1. Построена кинематическая модель робота по методу Денавита\u2013Хартенберга с длинами звеньев L0\u2009=\u200919, L1\u2009=\u2009134, L2\u2009=\u200995, L3\u2009=\u200934, L4\u2009=\u200935 мм и максимальной досягаемостью 317 мм. Прямая кинематика реализована как последовательное умножение DH-матриц трансформации."),

  p("2. Реализован алгоритм обратной кинематики на основе метода демпфированных наименьших квадратов (Damped Least Squares) с численным якобианом и 11 начальными приближениями. Достигнута точность позиционирования менее 0.5 мм на round-trip тестах и менее 1 мм для произвольных точек в рабочем пространстве."),

  p("3. Разработана система управления сервоприводами с поддержкой инверсии направления, безопасными ограничениями скорости (100 из 2400 шагов/с) и углов, асинхронным мониторингом температуры, напряжения, тока и нагрузки, а также кнопкой экстренной остановки."),

  p("4. Создан графический интерфейс оператора в стиле промышленных контроллеров FANUC с вкладками ручного управления, 3D-визуализации, блочного программирования и настройки маппинга моторов."),

  p("5. Реализована интеграция с физической средой MuJoCo: генерация MJCF-модели робота, двухпальцевый гриппер, камеры (включая eye-in-hand), объекты для захвата и Gym-подобный интерфейс RobotEnv для обучения с подкреплением."),

  p([{ text: "Перспективы развития: ", bold: true }, { text: "интеграция камеры реального времени для визуального позиционирования, обучение политики захвата объектов с помощью алгоритмов RL (PPO, SAC) в среде MuJoCo с последующим переносом на реальный робот (sim-to-real transfer), расширение блочного программирования для поддержки условных переходов и циклов." }]),

  new Paragraph({ children: [new PageBreak()] })
);

// ===== СПИСОК ИСТОЧНИКОВ =====
children.push(
  heading1("СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ"),

  p("1. Denavit J., Hartenberg R.S. A Kinematic Notation for Lower-Pair Mechanisms Based on Matrices // ASME Journal of Applied Mechanics. \u2014 1955. \u2014 Vol. 22. \u2014 P. 215\u2013221.", { noIndent: true }),
  p("2. Craig J.J. Introduction to Robotics: Mechanics and Control. \u2014 4th ed. \u2014 Pearson, 2017. \u2014 400 p.", { noIndent: true }),
  p("3. Siciliano B., Khatib O. Springer Handbook of Robotics. \u2014 2nd ed. \u2014 Springer, 2016. \u2014 2227 p.", { noIndent: true }),
  p("4. Siciliano B., Sciavicco L., Villani L., Oriolo G. Robotics: Modelling, Planning and Control. \u2014 Springer, 2009. \u2014 632 p.", { noIndent: true }),
  p("5. Todorov E., Erez T., Tassa Y. MuJoCo: A physics engine for model-based control // Proceedings of IROS. \u2014 IEEE, 2012. \u2014 P. 5026\u20135033.", { noIndent: true }),
  p("6. Wampler C.W. Manipulator Inverse Kinematic Solutions Based on Vector Formulations and Damped Least-Squares Methods // IEEE Trans. on Systems, Man, and Cybernetics. \u2014 1986. \u2014 Vol. 16(1). \u2014 P. 93\u2013101.", { noIndent: true }),
  p("7. Feetech. ST3215 Digital Servo Datasheet and Communication Protocol. \u2014 Feetech RC Model Co., 2023.", { noIndent: true }),
  p("8. Python Software Foundation. Python 3.12 Documentation [Электронный ресурс]. \u2014 URL: https://docs.python.org/3.12/ (дата обращения: 01.04.2026).", { noIndent: true }),
  p("9. Hunter J.D. Matplotlib: A 2D Graphics Environment // Computing in Science & Engineering. \u2014 2007. \u2014 Vol. 9(3). \u2014 P. 90\u201395.", { noIndent: true }),
  p("10. Harris C.R. et al. Array programming with NumPy // Nature. \u2014 2020. \u2014 Vol. 585. \u2014 P. 357\u2013362.", { noIndent: true }),
  p("11. International Federation of Robotics. World Robotics 2025: Industrial Robots. \u2014 IFR, 2025.", { noIndent: true }),
  p("12. Corke P. Robotics, Vision and Control: Fundamental Algorithms in Python. \u2014 3rd ed. \u2014 Springer, 2023. \u2014 818 p.", { noIndent: true }),
);

// ========== BUILD DOCUMENT ==========
const doc = new Document({
  styles: {
    default: {
      document: {
        run: { font: FONT, size: 28 }
      }
    },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: FONT },
        paragraph: { spacing: { before: 360, after: 240 }, alignment: AlignmentType.CENTER, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: FONT },
        paragraph: { spacing: { before: 280, after: 200 }, outlineLevel: 1 } },
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 }, // A4
        margin: { top: 1134, bottom: 1134, left: 1701, right: 851 } // 2cm top/bot, 3cm left, 1.5cm right
      }
    },
    headers: {
      default: new Header({ children: [new Paragraph({ children: [] })] })
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 24 })]
        })]
      })
    },
    children
  }]
});

const outPath = "C:/Users/SahaA/Documents/GitHub/diplome/docs/diploma_robotics.docx";
Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(outPath, buffer);
  console.log("Document created: " + outPath);
  console.log("Size: " + (buffer.length / 1024).toFixed(1) + " KB");
}).catch(err => {
  console.error("Error:", err);
  process.exit(1);
});
