import os
import os.path as osp
import json

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
            return json.load(f)
    except Exception as e:
        return None