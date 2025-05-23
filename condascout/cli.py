import subprocess
from packaging.version import Version
from packaging.requirements import Requirement
from condascout.parser import parse_args
from condascout.return_codes import ReturnCode
from typing import List, Union, Tuple

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


def main():
    args = parse_args()
    # print(f"Arguments received: {args}")

    requirements = []
    for package in args.have:
        requirements.append(Requirement(package))
    print(requirements)

    print(check_conda_installed())
    print(get_conda_envs())
    print(get_packages_in_env('base'))

if __name__ == '__main__':
    main()