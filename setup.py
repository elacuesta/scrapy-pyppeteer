import setuptools


setuptools.setup(
    name="scrapy-pyppeteer",
    version="0.0.1",
    license="BSD",
    description="Pyppeteer integration for Scrapy",
    author="Eugenio Lacuesta",
    author_email="eugenio.lacuesta@gmail.com",
    url="https://github.com/elacuesta/scrapy-pyppeteer",
    packages=["scrapy_pyppeteer"],
    classifiers=[
        "Development Status :: 1 - Planning",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Framework :: Scrapy",
        "Intended Audience :: Developers",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    install_requires=["scrapy>=2.0.0", "pyppeteer>=0.0.25"],
)
