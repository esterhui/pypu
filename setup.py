from pypu.version import VERSION
from distutils.core import setup

setup(
    name='pypu',
    version=VERSION,
    packages=['pypu',],
    scripts=["bin/pypu"],
    author='Stephan Esterhuizen',
    author_email='esterhui@gmail.com',
    url='http://github.com/esterhui/pypu',
    license='GPLv2',
    long_description=open('README.rst').read(),
    install_requires=[
        "facebook_sdk",
        "flickrapi",
        "python-wordpress-xmlrpc",
        "pygeocoder",
        "exifread",
        "pillow",
    ],
)
