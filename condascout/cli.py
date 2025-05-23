import subprocess
import sys
from rich import box
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn, SpinnerColumn
from rich.console import Console
from rich.table import Table
from packaging.version import Version
from packaging.requirements import Requirement, InvalidRequirement
from condascout.parser import parse_args
from condascout.codes import ReturnCode, PackageCode
from typing import List, Union, Tuple

console = Console()

def run_shell_command(command: List[str]) -> Tuple[ReturnCode, Union[subprocess.CompletedProcess, Exception]]:
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        return (ReturnCode.EXECUTED, result)
    except FileNotFoundError as e:
        return (ReturnCode.COMMAND_NOT_FOUND, e)
    except Exception as e:
        return (ReturnCode.UNHANDLED_ERROR, e)

def check_conda_installed():
    result = run_shell_command(['conda', '--version'])
    if result[0] == ReturnCode.EXECUTED:
        return result[1].returncode == 0
    return False

def get_conda_envs() -> List[str]:
    result = run_shell_command(['conda', 'env', 'list'])
    if result[0] != ReturnCode.EXECUTED:
        return []

    envs = []
    for line in result[1].stdout.splitlines():
        if line != '' and not line.startswith('#'):
            env = line.split(' ')[0]
            if env != '':
                envs.append(env)
    return envs

def try_get_version(version: str) -> bool:
    try:
        return Version(version)
    except Exception:
        return None

def check_packages_in_env(env: str, requirements: List[Requirement]) -> Tuple[int, int, List]:
    result = run_shell_command(['conda', 'list', '-n', env])
    if result[0] != ReturnCode.EXECUTED:
        return []

    package_status = {x.name: (PackageCode.MISSING, x.specifier) for x in requirements}
    total_found = 0
    installed_packages = result[1].stdout.splitlines()
    
    try:
        for line in installed_packages:
            if line != '' and not line.startswith('#'):
                line = [x for x in line.split(' ') if x != '']
                package, version = line[0], line[1]
                if package == '':
                    continue
                
                version = try_get_version(version)

                for req in requirements:
                    if req.name == package:
                        if version is None:
                            package_status[req.name] = (PackageCode.VERSION_INVALID, f'Expected "{req.specifier}", found "{version}". Version is not in PEP 440 format.')
                        elif req.specifier == '' or req.specifier.contains(version):
                            package_status[req.name] = (PackageCode.FOUND, version)
                            total_found += 1
                        else:
                            package_status[req.name] = (PackageCode.VERSION_MISMATCH, f'Expected "{req.specifier}", found "{version}"')
                
                if total_found == len(requirements):
                    break
    except Exception as e:
        console.print(f'[red]Unhandled Error in processing "{env}":[/red] {str(e)}')
        sys.exit(1)

    score = sum([x[0].value for x in package_status.values()])
    return score, len(installed_packages), [(package, status) for package, status in package_status.items()]

def can_execute_in_env(env: str, command: str) -> Tuple[bool, str]:
    result = run_shell_command(['conda', 'run', '-n', env, *command.split(' ')])
    if result[0] != ReturnCode.EXECUTED:
        return False, ''
    
    if result[1].returncode == 0:
        return True, result[1].stdout
    else:
        return False, result[1].stderr

def main():
    args = parse_args()

    console.print('[bold]Initial checks[/bold]')
    if check_conda_installed():
        console.print('[green]:heavy_check_mark: Conda is installed[/green] ')
    else:
        console.print('[red]:x: Conda is not installed or not found in PATH[/red]')
        sys.exit(1)

    requirements = []
    for package in args.have:
        try:
            req = Requirement(package)
            requirements.append(req)
        except InvalidRequirement as e:
            console.print(f':x:[red] Invalid requirement "{package}"[/red]')
            sys.exit(1)
    console.print(f'[green]:heavy_check_mark: Requirements parsed successfully[/green]')
    for req in requirements:
        console.print(f' [green] - {req.name}{req.specifier}[/green]')

    console.print('[bold]Finding valid environments[/bold]')
    conda_envs = get_conda_envs()
    filtered_envs = []
    with Progress(
        SpinnerColumn(),
        TextColumn('[bold blue]{task.description}'),
        BarColumn(),
        '[progress.percentage]{task.percentage:>3.0f}%',
        TimeRemainingColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task('Checking conda environments', total=len(conda_envs))
        
        for env in conda_envs:
            progress.update(task, description=f'Checking "{env}"')
            missing_packages = (env, *check_packages_in_env(env, requirements))
            filtered_envs.append(missing_packages)
            progress.advance(task)
    filtered_envs.sort(key=lambda x: (x[1], x[2]))

    table = Table(title='Result Summary', box=box.MINIMAL_HEAVY_HEAD, show_lines=True)
    table.add_column('Environment', style='cyan')
    table.add_column('Total packages installed', style='magenta')
    table.add_column('Info', justify='left')
    for env in filtered_envs:
        info = []
        for package, (status, detail) in env[3]:
            if status == PackageCode.MISSING:
                info.append(f':x: [red]{package}: missing[/red]')
            elif status == PackageCode.VERSION_INVALID or status == PackageCode.VERSION_MISMATCH:
                info.append(f'⚠️  [yellow]{package}: {detail}[/yellow]')
            elif status == PackageCode.FOUND:
                info.append(f'✅ [green]{package}=={detail}[/green]')
        table.add_row(env[0], str(env[2]), '\n'.join(info))

    console.print(table)


if __name__ == '__main__':
    main()