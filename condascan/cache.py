import os
import os.path as osp
import json
from rich.console import Console
from enum import Enum

class CacheType(Enum):
    PACKAGES = 'conda_env_packages.json'
    COMMANDS = 'conda_env_commands.json'

console = Console()

def get_and_create_cache_path(cache_type: CacheType, cache_dir: str = '~/.cache/condascan'):
    cache_dir = osp.expanduser(cache_dir)
    os.makedirs(cache_dir, exist_ok=True)
    path = osp.join(cache_dir, cache_type.value)
    return path

def write_cache(envs, cache_type: CacheType):
    with open(get_and_create_cache_path(cache_type), 'w') as f:
        json.dump(envs, f, indent=4)

def get_cache(cache_type: CacheType):
    try:
        with open(get_and_create_cache_path(cache_type), 'r') as f:
            console.print('[bold]Running using cache. If there are changes to your conda environments since the last time you run this command, try running with --no-cache[/bold]')
            return json.load(f)
    except Exception as e:
        console.print('[bold yellow]Cache not found or invalid. Running without cache, this may take a while[/bold yellow]')
        return {}