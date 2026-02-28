# webgrabber/setup.py

from setuptools import setup, find_packages

setup(
    name='webgrabber',
    version='1.0.0',
    description='Intelligent Website Source Code Downloader',
    packages=find_packages(),
    install_requires=[
        'click>=8.1.0',
        'playwright>=1.40.0',
        'aiohttp>=3.9.0',
        'aiofiles>=24.0.0',
        'requests>=2.31.0',
        'beautifulsoup4>=4.12.0',
        'cssutils>=2.7.0',
        'tenacity>=8.2.0',
        'pygit2>=1.13.0',
        'cryptography>=41.0.0',
        'browser-cookie3>=0.19.1',
        'lupa>=2.0.0',
    ],
    entry_points={
        'console_scripts': [
            'webgrabber = webgrabber.cli.commands:main',
        ],
    },
    python_requires='>=3.9',
)