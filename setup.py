import os
import setuptools
import sys

# Importing fastentrypoints monkey-patches setuptools to avoid generating slow
# executables from the entry_points directive. See
# https://github.com/ninjaaron/fast-entry_points.
import fastentrypoints

# Written according to the docs at
# https://packaging.python.org/en/latest/distributing.html

project_root = os.path.dirname(__file__)
readme_file = os.path.join(project_root, 'README.md')
module_root = os.path.join(project_root, 'peru')
version_file = os.path.join(module_root, 'VERSION')


def get_version():
    with open(version_file) as f:
        return f.read().strip()


def get_all_resources_filepaths():
    resources_paths = ['VERSION']
    resources_dir = os.path.join(module_root, 'resources')
    for dirpath, dirnames, filenames in os.walk(resources_dir):
        relpaths = [
            os.path.relpath(os.path.join(dirpath, f), start=module_root)
            for f in filenames
        ]
        resources_paths.extend(relpaths)
    return resources_paths


def get_install_requires():
    dependencies = ['docopt', 'PyYAML']
    if sys.version_info < (3, 5):
        raise RuntimeError('The minimum supported Python version is 3.5.')
    return dependencies


def readme_text():
    with open(readme_file) as f:
        return f.read().strip()


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
    entry_points={'console_scripts': [
        'peru=peru.main:main',
    ]},
    install_requires=get_install_requires(),
    long_description=readme_text(),
    long_description_content_type='text/markdown',
)
