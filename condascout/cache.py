import os
import os.path as osp
import json
from rich.console import Console

console = Console()

def get_and_create_cache_path():
    cache_dir = osp.expanduser('~/.cache/condascout')
    os.makedirs(cache_dir, exist_ok=True)
    path = osp.join(cache_dir, 'conda_env_details.json')
    return path

def write_cache(envs):
    with open(get_and_create_cache_path(), 'w') as f:
        json.dump(envs, f, indent=4)

def get_cache():
    try:
        with open(get_and_create_cache_path(), 'r') as f:
            console.print('[bold]Running using cache. If there are changes to your conda environments since the last time you run this command, try running with --no-cache[/bold]')
            return json.load(f)
    except Exception as e:
        console.print('[bold yellow]Cache not found or invalid. Running without cache, this may take a while[/bold yellow]')
        return None