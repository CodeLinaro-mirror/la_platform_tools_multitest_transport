# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Setup for mtt cli."""
import setuptools

VERSION = '0.0'

setuptools.setup(
    name='Android_Test_Station_CLI',
    description='CLI for Android Test Station.',
    url='https://source.android.com/compatibility/tests/development/android-test-station/ats-user-guide',
    version=VERSION,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
    ],
    packages=setuptools.find_packages(),
    package_data={
        'multitest_transport.cli': ['seccomp.json'],
    },
    # The package works for 3.10 and up, but not for python 4 yet.
    python_requires='~=3.10',
    entry_points={
        'console_scripts': ['mtt=multitest_transport.cli.cli:Main'],
    },
    install_requires=[
        'ansible-base',
        'appengine-python-standard >= 1.0.0',
        'attrs',
        'fabric',
        'google-api-core',
        'google-api-python-client',
        'google-auth',
        'google-cloud-core',
        'google-cloud-logging',
        'google-cloud-secret-manager',
        'google-cloud-storage',
        'grpcio',
        'grpcio-status',
        'packaging',
        'packaging-legacy',
        'protobuf',
        'pyOpenSSL',
        'python-dateutil',
        'pytz',
        'requests',
        'SecretStorage',
        'six',
        'strictyaml',
        'urllib3',
    ],
)
