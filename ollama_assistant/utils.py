
from rich.table import Table
from rich.console import Console
from rich.align import Align
console = Console()

def get_model_name(m):
    return (
        getattr(m, "model", None)
        or getattr(m, "name", None)
        or (m.get("model") if isinstance(m, dict) else None)
        or (m.get("name") if isinstance(m, dict) else str(m))
    )

def print_models_table(models_list, title="Available Local Models"):
    from rich import box
    table = Table(
        show_header=True, 
        header_style="bold magenta", 
        expand=True,
        box=box.ROUNDED,
        border_style="cyan"
    )
    table.add_column("No.", style="dim", width=4, justify="center")
    table.add_column("🧠 Model Name", style="bold cyan")
    table.add_column("⚙️ Parameters", style="green", justify="right")
    table.add_column("💾 Size", style="yellow", justify="right")
    table.add_column("⚡ Quantization", style="blue", justify="right")

    for i, m in enumerate(models_list):
        name = get_model_name(m)
        details = getattr(m, "details", None)
        if not details and isinstance(m, dict):
            details = m.get("details", {})
        param_size = str(getattr(details, "parameter_size", None) or (details.get("parameter_size") if isinstance(details, dict) else "-"))
        quant = str(getattr(details, "quantization_level", None) or (details.get("quantization_level") if isinstance(details, dict) else "-"))
        size_bytes = getattr(m, "size", None) or (m.get("size") if isinstance(m, dict) else 0)
        size_gb = f"{(size_bytes / (1024**3)):.2f} GB" if size_bytes else "-"
        table.add_row(str(i + 1), name, param_size, size_gb, quant)

    console.print()
    console.print(Align.center(table))
    console.print()
