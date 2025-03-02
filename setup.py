from setuptools import setup, find_packages

setup(
    name="chessy",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "flask>=2.0.0",
        "requests>=2.25.0",
        "python-dotenv>=0.15.0",
        "python-chess>=1.5.0",
        "pandas>=1.2.0",
        "plotly>=5.0.0",
        "stockfish>=3.19.0",
    ],
    entry_points={
        "console_scripts": [
            "chessy-server=chessy.server:main",
        ],
    },
    python_requires=">=3.8",
    
    # Metadata
    author="Chess.com Game Analyzer",
    author_email="your.email@example.com",
    description="A web application for analyzing Chess.com games",
    keywords="chess, analysis, stockfish, flask",
    url="https://github.com/yourusername/chessy",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Games/Entertainment :: Board Games",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
)
