/**
 * СПИСОК ЛИТЕРАТУРЫ
 *
 * Содержание: библиографические ссылки [1]–[17]
 * Целевой объём: ~2 страницы (страницы 22–23 ВКР)
 */
module.exports = function (h) {
  const { Paragraph, TextRun, AlignmentType } = h;
  const FONT = h.FONT;

  const c = [];

  c.push(h.heading1("СПИСОК ЛИТЕРАТУРЫ"));

  const refs = [
    "1.\tGeeng C., Roesner F. Who's In Control?: Interactions In Multi-User Smart Homes // CHI Conference on Human Factors in Computing Systems Proceedings (CHI 2019). – Glasgow, Scotland UK : ACM, 2019. – P. 1–13. – DOI: https://doi.org/10.1145/3290605.3300498.",
    "2.\thttps://www.intelvision.ru/blog/what-is-smarthome",
    "3.\thttps://www.itworkroom.com/smart-house/",
    "4.\thttps://www.cta.ru/articles/soel/2021/2021-4/137533/",
    "5.\thttps://smarthomeguidekz.com/technologies.html",
    "6.\thttps://www.kaspersky.ru/blog/smart-home-zigbee-thread-matter-advice/34761/",
    "7.\tWolniak R., Grebski W. The Usage of Smart Voice Assistant in Smart Home // Management Papers. – 2024.",
    "8.\tHow Siri, Alexa and Google Assistant Lost the A.I. Race. – Аналитическая статья о проблемах развития современных голосовых ассистентов и ограничениях их архитектуры.",
    "9.\tEdu J. S., Such J. M., Suarez-Tangil G. Smart Home Personal Assistants: A Security and Privacy Review // ACM Computing Surveys. – 2020. – Vol. 53. – No. 6. – Article 116. – 36 p. – DOI: 10.1145/3412383.",
    "10.\tМультизадачность – Справка Яндекс Станции [Электронный ресурс]. URL: https://alice.yandex.ru/support/ru/station/multitasking.",
    "11.\tSharma O., Rathee G., Kerrache C. A., Herrera-Tapia J. Two-Stage Optimal Task Scheduling for Smart Home Environment Using Fog Computing Infrastructures // Applied Sciences. – 2023. – Vol. 13. – No. 5. – Article 2939. – DOI: 10.3390/app13052939.",
    "12.\tЛихолетова М. В., Устюгов В. А. Обзор современных решений для построения микролокальных сетей // Juvenis scientia. – 2017. – № 4. – С. 8.",
    "13.\tDing S., Liu J., Yue M. The Use of ZigBee Wireless Communication Technology in Industrial Automation Control // Wireless Communications and Mobile Computing. – 2021. – Vol. 2021. – Article ID 8317862. – 11 p. – DOI: 10.1155/2021/8317862.",
    "14.\tArava Suman Kumar Reddy, P. Srinivasula, A. Siva Phani Krishna Sharma. The Z-Wave Home Automation Protocol and Its Security Flaws // Advanced Engineering Science. – 2023.",
    "15.\tNoura M., Heil S., Gaedke M. Natural Language Goal Understanding for Smart Home Environments // Proceedings of the 10th International Conference on the Internet of Things (IoT '20). – Malmö, Sweden, 2020. – DOI: 10.1145/3410992.3410996.",
    "16.\tЦитульский А. М., Иванников А. В., Рогов И. С. NLP – обработка естественных языков (Natural Language Processing) // StudNet : научно-образовательный журнал для студентов и преподавателей. – 2020. – № 6. – С. 468–473.",
    "17.\tБарщевский Е. Г. Что такое NLU (What is NLU) // Труды университета. – 2024. – С. 1–3.",
  ];

  refs.forEach(ref => {
    c.push(new Paragraph({
      spacing: { line: 360, after: 120 },
      alignment: AlignmentType.JUSTIFIED,
      children: [new TextRun({ text: ref, font: FONT, size: 28 })]
    }));
  });

  return c;
};
