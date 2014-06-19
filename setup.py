#! /usr/bin/env python3

from setuptools import find_packages
from setuptools import setup

setup(
    name='peru',
    description='a modular build tool',
    version='0.0-alpha',
    author='Jack O\'Connor',
    author_email='oconnor663@gmail.com',
    url='https://github.com/oconnor663/peru',
    license='MIT',
    keywords='build fetch sync dependency version history',
    packages=find_packages(exclude=['*.test']),  # peru
    classifiers=[],
    install_requires='pyyaml>=3.10',
    test_suite='peru.test',
)
