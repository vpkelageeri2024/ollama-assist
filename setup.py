from setuptools import setup, find_packages

setup(
    name='ollama-assistant',
    version='0.1.0',
    description='An AI assistant CLI tool powered by local Ollama models',
    author='You',
    packages=find_packages(),
    install_requires=[
        'ollama>=0.2.0',
        'rich>=13.0.0',
        'prompt_toolkit>=3.0.0',
        'ddgs>=9.14.0',
        'pyyaml>=6.0',
        'pyperclip>=1.8.0',
        'pygments>=2.15.0',
        'psutil>=5.9.0',
        'black>=23.0.0',
        'chromadb>=0.4.0',
        'requests>=2.20.0',
    ],
    entry_points={
        'console_scripts': [
            'ollama-assist=ollama_assistant.cli:main',
        ],
    },
)
