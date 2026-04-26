#!/usr/bin/env python3
from rich.console import Console
from rich.table import Table

c = Console()
c.print("[bold green]Rich is working![/bold green]")

table = Table(title="Joints")
table.add_column("Name")
table.add_column("Position")
table.add_row("joint_1", "0.000")
table.add_row("joint_2", "0.500")
c.print(table)
