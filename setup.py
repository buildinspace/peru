import os
import setuptools

# Written according to the docs at
# https://packaging.python.org/en/latest/distributing.html

# Get the list of all filepaths under ./peru/resources/, relative to ./peru/.
peru_module_dir = os.path.join(os.path.dirname(__file__), 'peru')
resources_dir = os.path.join(peru_module_dir, 'resources')
resources_paths = []
for dirpath, dirnames, filenames in os.walk(resources_dir):
    relpaths = [os.path.relpath(os.path.join(dirpath, f),
                                start=peru_module_dir)
                for f in filenames]
    resources_paths.extend(relpaths)

setuptools.setup(
    name='peru',
    version='0.1.0',
    url='https://github.com/buildinspace/peru',
    author="Jack O'Connor <oconnor663@gmail.com>, "
           "Sean Olson <olson.sean.k@gmail.com>",
    license='MIT',
    packages=['peru'],
    package_data={'peru': resources_paths},
    scripts=['bin/peru'],
    install_requires=[
        'docopt',
        'PyYAML',
    ],
)
