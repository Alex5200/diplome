import * as Blockly from "blockly";

export function registerBlocks() {
  Blockly.Blocks["move_joint"] = {
    init(this: Blockly.Block) {
      this.appendDummyInput()
        .appendField("Двигать сустав")
        .appendField(
          new Blockly.FieldDropdown([
            ["J1", "1"], ["J2", "2"], ["J3", "3"],
            ["J4", "4"], ["J5", "5"], ["J6", "6"],
          ]),
          "JOINT"
        )
        .appendField("на угол")
        .appendField(new Blockly.FieldNumber(0, -180, 180), "ANGLE")
        .appendField("° скорость")
        .appendField(new Blockly.FieldNumber(2400, 100, 3400), "SPEED");
      this.setPreviousStatement(true, null);
      this.setNextStatement(true, null);
      this.setColour(160);
      this.setTooltip("Перемещение сустава на заданный угол");
    },
  };

  Blockly.Blocks["move_ik"] = {
    init(this: Blockly.Block) {
      this.appendDummyInput()
        .appendField("Двигать в точку")
        .appendField("X")
        .appendField(new Blockly.FieldNumber(150), "X")
        .appendField("Y")
        .appendField(new Blockly.FieldNumber(0), "Y")
        .appendField("Z")
        .appendField(new Blockly.FieldNumber(100), "Z");
      this.setPreviousStatement(true, null);
      this.setNextStatement(true, null);
      this.setColour(210);
      this.setTooltip("Перемещение по обратной кинематике (IK)");
    },
  };

  Blockly.Blocks["wait_seconds"] = {
    init(this: Blockly.Block) {
      this.appendDummyInput()
        .appendField("Пауза")
        .appendField(new Blockly.FieldNumber(1, 0.1, 30), "SECONDS")
        .appendField("сек");
      this.setPreviousStatement(true, null);
      this.setNextStatement(true, null);
      this.setColour(40);
      this.setTooltip("Задержка выполнения");
    },
  };

  Blockly.Blocks["move_home"] = {
    init(this: Blockly.Block) {
      this.appendDummyInput().appendField("В начальную позицию");
      this.setPreviousStatement(true, null);
      this.setNextStatement(true, null);
      this.setColour(120);
      this.setTooltip("Все суставы в 0°");
    },
  };

  Blockly.Blocks["repeat_times"] = {
    init(this: Blockly.Block) {
      this.appendDummyInput()
        .appendField("Повторить")
        .appendField(new Blockly.FieldNumber(3, 1, 100), "TIMES")
        .appendField("раз");
      this.appendStatementInput("DO").appendField("делать");
      this.setPreviousStatement(true, null);
      this.setNextStatement(true, null);
      this.setColour(260);
      this.setTooltip("Цикл повторения");
    },
  };
}
