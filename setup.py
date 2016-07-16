import os
import setuptools
import sys

# Written according to the docs at
# https://packaging.python.org/en/latest/distributing.html

project_root = os.path.dirname(__file__)
peru_sh_path = os.path.join(project_root, 'peru.sh')
module_root = os.path.join(project_root, 'peru')
version_file = os.path.join(module_root, 'VERSION')


def get_version():
    with open(version_file) as f:
        return f.read().strip()


def get_all_resources_filepaths():
    resources_paths = ['VERSION']
    resources_dir = os.path.join(module_root, 'resources')
    for dirpath, dirnames, filenames in os.walk(resources_dir):
        relpaths = [os.path.relpath(os.path.join(dirpath, f),
                                    start=module_root)
                    for f in filenames]
        resources_paths.extend(relpaths)
    return resources_paths


def get_install_requires():
    dependencies = ['docopt', 'PyYAML', 'watchdog']
    # Python 3.3 needs extra libs that aren't installed by default.
    if sys.version_info < (3, 3):
        raise RuntimeError('The minimum supported Python version is 3.3.')
    elif (3, 3) <= sys.version_info < (3, 4):
        dependencies.extend(['asyncio', 'pathlib'])
    return dependencies


setuptools.setup(
    name='peru',
    description='A tool for fetching code',
    version=get_version(),
    url='https://github.com/buildinspace/peru',
    author="Jack O'Connor <oconnor663@gmail.com>, "
           "Sean Olson <olson.sean.k@gmail.com>",
    license='MIT',
    packages=['peru'],
    package_data={'peru': get_all_resources_filepaths()},
    entry_points={
        'console_scripts': [
            'peru=peru.main:main',
        ]
    },
    install_requires=get_install_requires(),
)
