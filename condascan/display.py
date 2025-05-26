from rich import box
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn, SpinnerColumn
from rich.table import Table
from typing import List, Tuple, Dict, Union
from condascan.codes import PackageCode

console = Console()

def get_progress_bar(console: Console) -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn('[bold blue]{task.description}'),
        BarColumn(),
        '[progress.percentage]{task.percentage:>3.0f}%',
        TimeRemainingColumn(),
        console=console,
        transient=True,
    )

def display_have_output(filtered_envs: Tuple, limit: int = -1, verbose: bool = False, first: bool = False) -> Table:
    if verbose:
        table = Table(box=box.MINIMAL_HEAVY_HEAD, show_lines=True)
        table.add_column('Environment', style='cyan', justify='left')
        table.add_column('Python Version', style='blue', justify='left')
        table.add_column('Total Packages Installed', style='magenta', justify='left')
        table.add_column('Info', justify='left')

        if limit != -1:
            console.print(f'[bold]Limiting output to {limit} environments[/bold]')
            filtered_envs = filtered_envs[:limit]
        for env in filtered_envs:
            info = []
            for package, (status, detail) in env[2]:
                if status == PackageCode.MISSING:
                    info.append(f'[red]:x: {package}: missing[/red]')
                elif status == PackageCode.VERSION_INVALID or status == PackageCode.VERSION_MISMATCH:
                    info.append(f'[yellow]:warning: {package}: {detail}[/yellow]')
                elif status == PackageCode.FOUND:
                    info.append(f'[green]:heavy_check_mark: {package}=={detail}[/green]')
                elif status == PackageCode.ERROR:
                    info.append(f'[red]:exclamation: {package}: {detail}[/red]')
            table.add_row(env[0], str(env[3]), str(env[1][3]), '\n'.join(info))

        console.print(table)
    else:
        filtered_envs = [x for x in filtered_envs if x[-1]]
        if len(filtered_envs) == 0:
            console.print('[red]No environments found with all required packages. To see the details, run with --verbose[/red]')
        else:
            if first:
                text = '[green]Found the first environment with all required packages:[/green]'
            else:
                if limit == -1:
                    text = f'[green]Found {len(filtered_envs)} environments with all required packages:[/green]'
                else:
                    filtered_envs = filtered_envs[:limit]
                    text = f'[green]Found {len(filtered_envs)} environments with all required packages (output limited to {limit}):[/green]'
            
            console.print(text)
            for env in filtered_envs:
                console.print(f'[green]- {env[0]}[/green]')
